/** Kitchen lesson state: real data preparation, illustrative post-training.
 * Guide: docs/learn/llm-kitchen.md. Never performs model optimization.
 */
import { encode } from "../tokenizer";

export const dinnerPrompt =
  "Suggest a three-ingredient dinner without dairy. Keep the answer brief.";

export const ingredients = [
  {
    id: "explanation",
    title: "Rice, beans and tomatoes",
    text: "Cook rice, warm beans, and add chopped tomatoes. A three-ingredient dinner without dairy.",
    keep: false,
  },
  {
    id: "duplicate",
    title: "Another recipe note",
    text: "Cook rice, warm beans, and add chopped tomatoes. A three-ingredient dinner without dairy.",
    keep: false,
  },
  {
    id: "broken",
    title: "An imported recipe note",
    text: "Dinner\u0000\uFFFD",
    keep: false,
  },
  {
    id: "conversation",
    title: "A dinner conversation",
    text: "User: Suggest a three-ingredient dinner without dairy.\nAssistant: Make a bowl with rice, beans, and tomatoes. Cook, warm, and combine.",
    keep: false,
  },
  {
    id: "code",
    title: "A recipe in code",
    text: 'ingredients = ["rice", "beans", "tomatoes"]\nassert len(ingredients) == 3',
    keep: false,
  },
  {
    id: "dairy",
    title: "Creamy rice with cheese",
    text: "Cook rice with butter, then stir in cheese. A creamy three-ingredient dinner.",
    keep: false,
  },
  {
    id: "weather",
    title: "Tomorrow’s forecast",
    text: "Tomorrow: sunny, 24°C, with a light breeze. Rain is expected on Friday.",
    keep: false,
  },
] as const;

export const checkpoints = [
  {
    id: "base",
    title: "Base model",
    kitchen: "Develop the base recipe",
    method: "Pre-training",
    output:
      "Three ingredients for dinner. Dinner is a meal often served in the evening…",
    evidence:
      "Raw text → predict the next token → update weights. A base model may continue text rather than follow an instruction.",
    changed: "Weights during pre-training",
  },
  {
    id: "sft",
    title: "After SFT",
    kitchen: "Learn from a worked recipe",
    method: "Post-training / supervised fine-tuning",
    output:
      "Make a rice, beans, and tomato bowl. Cook the rice and warm the beans, then add the tomatoes.",
    evidence: `Demonstration\nUser: ${dinnerPrompt}\nAssistant: Make a rice, beans, and tomato bowl. Cook, warm, and combine.`,
    changed: "Trainable weights or adapter weights",
  },
  {
    id: "preference",
    title: "After preference training",
    kitchen: "Use tasting feedback to revise",
    method: "Post-training / preference optimization",
    output: "Rice, beans, tomatoes: cook, warm, and combine. Dairy-free.",
    evidence:
      "Chosen: Rice, beans, tomatoes: cook, warm, and combine. Dairy-free.\nRejected: Make creamy rice with cheese and beans.\nA later optimization step uses preference data; collecting the pair alone does not train anything.",
    changed: "Trainable weights or adapter weights",
  },
] as const;

export const tasteResponses = {
  a: "Make creamy rice with cheese and beans.",
  b: "Rice, beans, tomatoes: cook, warm, and combine. Dairy-free.",
};
export type TasteChoice = keyof typeof tasteResponses;

export function preferencePair(choice: TasteChoice) {
  return {
    prompt: dinnerPrompt,
    chosen: tasteResponses[choice],
    rejected: tasteResponses[choice === "a" ? "b" : "a"],
  };
}

export function prepareIngredients(ids: readonly string[]) {
  const selected = ingredients.filter((sample) => ids.includes(sample.id));
  const unique = new Set<string>();
  const rejected: string[] = [];
  let duplicates = 0;
  for (const sample of selected) {
    const text = sample.text.trim();
    if (!text || /[\u0000\uFFFD]/u.test(text)) {
      rejected.push(sample.title);
    } else if (unique.has(text)) {
      duplicates++;
    } else {
      unique.add(text);
    }
  }
  const text = [...unique].join("\n\n");
  return {
    text,
    tokens: encode(text),
    selected: selected.length,
    kept: unique.size,
    duplicates,
    rejected,
  };
}

export const HANDOFF_KEY = "posttrainllm.kitchen.batch.v1";
export const MAX_BATCH_BYTES = 32_768;
export const HANDOFF_TTL = 60 * 60 * 1000;
export interface KitchenBatch {
  version: 1;
  source: "llm-kitchen";
  text: string;
  createdAt: number;
}

export function createBatch(text: string, now = Date.now()): KitchenBatch {
  if (
    !text.trim() ||
    encode(text).length > MAX_BATCH_BYTES ||
    /[\u0000\uFFFD]/u.test(text)
  ) {
    throw new Error("Choose a nonempty, valid batch no larger than 32 KB.");
  }
  return { version: 1, source: "llm-kitchen", text, createdAt: now };
}

export function parseBatch(
  raw: string | null,
  now = Date.now(),
): KitchenBatch | null {
  if (!raw || raw.length > MAX_BATCH_BYTES * 6 + 200) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    const batch = value as Partial<KitchenBatch>;
    if (
      batch.version !== 1 ||
      batch.source !== "llm-kitchen" ||
      typeof batch.text !== "string" ||
      typeof batch.createdAt !== "number" ||
      !Number.isFinite(batch.createdAt) ||
      batch.createdAt > now ||
      now - batch.createdAt > HANDOFF_TTL
    )
      return null;
    createBatch(batch.text, batch.createdAt);
    return batch as KitchenBatch;
  } catch {
    return null;
  }
}
