import { describe, expect, it } from "vitest";
import {
  cookingCorpus,
  kitchenConfig,
  kitchenModelFile,
} from "../kitchen/cook-model";
describe("actual cooking contract", () => {
  it("repeats only selected prepared text for the tiny overfit lesson", () => {
    expect(() => cookingCorpus(" ")).toThrow();
    const text = "café beans";
    const corpus = cookingCorpus(text);
    expect(new TextEncoder().encode(corpus).length).toBeGreaterThanOrEqual(
      2048,
    );
    expect(corpus.split("\n\n").every((part) => part === text)).toBe(true);
  });
  it("exports the existing trainer format with the exact weights and corpus", async () => {
    const state = new Uint8Array([3, 0, 0, 0, 17, 31]).buffer;
    const buf = await kitchenModelFile(
      kitchenConfig,
      state,
      "picked batch",
    ).arrayBuffer();
    const view = new DataView(buf);
    expect(new TextDecoder().decode(new Uint8Array(buf, 0, 4))).toBe("TGPT");
    expect(view.getUint32(4, true)).toBe(1);
    const length = view.getUint32(8, true);
    const header = JSON.parse(
      new TextDecoder().decode(new Uint8Array(buf, 12, length)),
    );
    expect(header.config).toEqual(kitchenConfig);
    expect(header.corpus).toBe("picked batch");
    expect(new Uint8Array(buf.slice(12 + length))).toEqual(
      new Uint8Array(state),
    );
  });
});
