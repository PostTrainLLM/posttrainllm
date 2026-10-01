/** Bounded teaching recipe and trainer-compatible export. No runtime math here.
 * Guide: docs/learn/llm-kitchen.md.
 */
import type { RunConfig } from "../types";
import recipe from "../../../configs/llm-kitchen.json";
export const kitchenConfig: RunConfig = { ...recipe, backend: "wasm" };
// Repeated tiny corpus is intentional: this is an overfitting demonstration,
// not a held-out generalization benchmark. Preserve every selected sample.
export function cookingCorpus(text: string): string {
  const batch = text.trim();
  if (!batch) throw new Error("Prepare a non-empty batch first.");
  return Array.from(
    {
      length: Math.max(
        2,
        Math.ceil(2048 / new TextEncoder().encode(batch).length),
      ),
    },
    () => batch,
  ).join("\n\n");
}
export function kitchenModelFile(
  config: RunConfig,
  state: ArrayBuffer,
  corpus: string,
): Blob {
  // v1 is the existing trainer's canonical full-state format (Adam included).
  const header = new TextEncoder().encode(
    JSON.stringify({
      config,
      corpus,
      includesOptimizerState: true,
      savedAt: new Date().toISOString(),
      source: "llm-kitchen",
      stateByteLength: state.byteLength,
    }),
  );
  const prefix = new ArrayBuffer(12);
  new Uint8Array(prefix, 0, 4).set(new TextEncoder().encode("TGPT"));
  new DataView(prefix).setUint32(4, 1, true);
  new DataView(prefix).setUint32(8, header.length, true);
  return new Blob([prefix, header, state], {
    type: "application/octet-stream",
  });
}
