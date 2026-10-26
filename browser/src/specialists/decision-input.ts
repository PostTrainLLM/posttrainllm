/** Strict local Qwen package and selected-label input contract. */
import { object, type Json } from "./forecast-input";

export const decisionFiles = [
  "model.onnx",
  "model.onnx.data",
  "tokenizer.json",
  "tokenizer_config.json",
] as const;
export type DecisionManifest = {
  format: string;
  model_identity: string;
  source_identity: string;
  files: Record<string, { sha256: string; bytes: number }>;
  max_tokens: number;
  template: {
    prefix: string;
    suffix: string;
    vectors: { text: string; ids: number[] }[];
  };
  probes: {
    item: Json;
    tokens: number[];
    label_ids: number[];
    logits: number[];
  }[];
};
const sha = (value: unknown) =>
  typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
export function decisionManifest(value: unknown): DecisionManifest {
  const data = object(value),
    files = object(data.files),
    template = object(data.template);
  if (
    data.format !== "posttrainllm-qwen3-affine-f32-v1" ||
    !sha(data.model_identity) ||
    !sha(data.source_identity)
  )
    throw Error("Unsupported or unidentified portable Qwen artifact.");
  if (
    !Number.isInteger(data.max_tokens) ||
    Number(data.max_tokens) < 64 ||
    Number(data.max_tokens) > 512
  )
    throw Error("Portable Qwen requires an explicit 64–512 token limit.");
  validateFiles(files);
  validateTemplate(template);
  validateProbes(data);
  return data as unknown as DecisionManifest;
}
function validateFiles(files: Json) {
  if (Object.keys(files).sort().join() !== [...decisionFiles].sort().join())
    throw Error("Portable Qwen requires exactly four named local files.");
  for (const name of decisionFiles) {
    const file = object(files[name]);
    const limit =
      name === "model.onnx.data" ? 1280 * 1024 ** 2 : 64 * 1024 ** 2;
    if (
      !sha(file.sha256) ||
      !Number.isSafeInteger(file.bytes) ||
      Number(file.bytes) < 1 ||
      Number(file.bytes) > limit
    )
      throw Error(`Invalid local artifact size or checksum: ${name}`);
  }
}
function validateTemplate(template: Json) {
  if (
    typeof template.prefix !== "string" ||
    typeof template.suffix !== "string" ||
    template.prefix.length + template.suffix.length > 16384 ||
    !Array.isArray(template.vectors) ||
    template.vectors.length < 2 ||
    template.vectors.length > 64
  )
    throw Error("Missing bounded Python tokenizer/template vectors.");
  for (const raw of template.vectors) {
    const vector = object(raw);
    if (typeof vector.text !== "string" || vector.text.length > 32768)
      throw Error("Invalid tokenizer vector.");
    tokenIds(vector.ids, 8192);
  }
}
function validateProbes(data: Json) {
  if (!Array.isArray(data.probes) || data.probes.length !== 3)
    throw Error("Three Python selected-logit probes are required.");
  for (const raw of data.probes) {
    const probe = object(raw),
      item = decisionItem(probe.item);
    tokenIds(probe.tokens, Number(data.max_tokens));
    tokenIds(probe.label_ids, 26);
    if (
      !Array.isArray(probe.logits) ||
      probe.logits.length !== Object.keys(item.options as Json).length ||
      probe.logits.some((v) => typeof v !== "number" || !Number.isFinite(v))
    )
      throw Error("Invalid Python selected-logit probe.");
  }
}
export function tokenIds(value: unknown, maximum: number): number[] {
  if (
    !Array.isArray(value) ||
    !value.length ||
    value.length > maximum ||
    value.some((v) => !Number.isSafeInteger(v) || v < 0 || v >= 200000)
  )
    throw Error("Invalid or over-limit token IDs.");
  return value;
}
export function decisionItem(value: unknown): Json {
  const item = object(value),
    options = object(item.options),
    labels = Object.keys(options);
  const blank =
    /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]*$/u;
  if (
    typeof item.question !== "string" ||
    blank.test(item.question) ||
    item.question.length > 32768 ||
    labels.length < 2 ||
    labels.length > 26 ||
    invalidOptions(labels, options)
  )
    throw Error(
      "Provide a nonempty question and 2–26 nonempty label/text pairs.",
    );
  if (
    labels.some(
      (label) =>
        /^(0|[1-9][0-9]{0,9})$/.test(label) && Number(label) < 2 ** 32 - 1,
    )
  )
    throw Error(
      "Integer-index labels reorder in browser JSON; use labels such as A, B, C.",
    );
  if (
    item.answer !== undefined &&
    (typeof item.answer !== "string" || !Object.hasOwn(options, item.answer))
  )
    throw Error("Answer must name an option.");
  return item;
}
export function decisionPrompt(meta: DecisionManifest, item: Json): string {
  const options = object(item.options);
  const text = `${item.question}\n${Object.keys(options)
    .map((label) => `${label}. ${options[label]}`)
    .join("\n")}\nAnswer with exactly one option label.\nAnswer:`;
  return meta.template.prefix + text + meta.template.suffix;
}
export function selectedPrediction(
  labels: string[],
  logits: number[],
  threshold: unknown = 0,
) {
  if (
    typeof threshold !== "number" ||
    !Number.isFinite(threshold) ||
    threshold < 0 ||
    threshold > 1 ||
    logits.length !== labels.length ||
    logits.some((v) => !Number.isFinite(v))
  )
    throw Error("Invalid selected logits or probability threshold.");
  const maximum = Math.max(...logits),
    values = logits.map((v) => Math.exp(v - maximum));
  const sum = values.reduce((a, b) => a + b, 0),
    probabilities = values.map((v) => v / sum);
  const index = probabilities.indexOf(Math.max(...probabilities));
  return {
    label: probabilities[index] >= threshold ? labels[index] : null,
    probabilities: Object.fromEntries(
      labels.map((label, i) => [label, probabilities[i]]),
    ),
    calibration: "uncalibrated",
    temperature: 1,
  };
}
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object")
    return `{${Object.entries(value)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, child]) => `${JSON.stringify(key)}:${canonical(child)}`)
      .join(",")}}`;
  return JSON.stringify(value);
}

function invalidOptions(labels: string[], options: Json) {
  return labels.some(
    (label) =>
      !label ||
      label.length > 128 ||
      typeof options[label] !== "string" ||
      !options[label] ||
      String(options[label]).length > 16384,
  );
}
