/** Bounded same-tab lesson continuity. Stores teaching choices, never chat messages.
 * Guide: docs/learn/llm-kitchen.md. Prepared data is regenerated from known fixtures.
 */
import { checkpoints, ingredients } from "./model";
export const LESSON_KEY = "posttrainllm.kitchen.lesson.v2";
export const LESSON_TTL = 60 * 60 * 1000;
export type Lesson = {
  version: 2;
  savedAt: number;
  selected: string[];
  chopText: string;
  chopped: boolean;
  prepared: boolean;
  checkpoint: string;
  choice: "a" | "b" | null;
  simulated: boolean;
  garnished: boolean;
  cookStep: number;
};
export function parseLesson(
  raw: string | null,
  now = Date.now(),
): Lesson | null {
  if (!raw || raw.length > 2048) return null;
  try {
    const s = JSON.parse(raw);
    if (
      !s ||
      s.version !== 2 ||
      !Number.isFinite(s.savedAt) ||
      s.savedAt > now ||
      now - s.savedAt > LESSON_TTL ||
      !Array.isArray(s.selected) ||
      s.selected.length > ingredients.length ||
      new Set(s.selected).size !== s.selected.length ||
      s.selected.some((id: unknown) => !ingredients.some((i) => i.id === id)) ||
      typeof s.chopText !== "string" ||
      s.chopText.length > 80 ||
      !checkpoints.some((c) => c.id === s.checkpoint) ||
      ![null, "a", "b"].includes(s.choice) ||
      ![s.chopped, s.prepared, s.simulated, s.garnished].every(
        (v) => typeof v === "boolean",
      ) ||
      (s.simulated && s.choice === null) ||
      !Number.isInteger(s.cookStep) ||
      s.cookStep < 0 ||
      s.cookStep > 3
    )
      return null;
    return {
      version: 2,
      savedAt: s.savedAt,
      selected: s.selected,
      chopText: s.chopText,
      chopped: s.chopped,
      prepared: s.prepared,
      checkpoint: s.checkpoint,
      choice: s.choice,
      simulated: s.simulated,
      garnished: s.garnished,
      cookStep: s.cookStep,
    };
  } catch {
    return null;
  }
}
