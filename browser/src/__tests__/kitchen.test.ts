import { describe, expect, it } from "vitest";
import {
  createBatch,
  HANDOFF_TTL,
  MAX_BATCH_BYTES,
  parseBatch,
  preferencePair,
  prepareIngredients,
} from "../kitchen/model";
import { decode } from "../tokenizer";

describe("kitchen data preparation", () => {
  it("deduplicates exact repeats and excludes broken bytes without dropping code or conversations", () => {
    const batch = prepareIngredients([
      "explanation",
      "duplicate",
      "broken",
      "conversation",
      "code",
    ]);
    expect(batch.kept).toBe(3);
    expect(batch.duplicates).toBe(1);
    expect(batch.rejected).toEqual(["An imported recipe note"]);
    expect(batch.text).toContain("User:");
    expect(batch.text).toContain("assert len(ingredients)");
    expect(decode(batch.tokens)).toBe(batch.text);
  });
  it("does not silently remove clean examples that conflict with the learning goal", () => {
    const batch = prepareIngredients(["explanation", "dairy", "weather"]);
    expect(batch.kept).toBe(3);
    expect(batch.text).toContain("cheese");
    expect(batch.text).toContain("24°C");
    expect(batch.rejected).toEqual([]);
  });
  it("does not invent a batch for an empty or invalid selection", () => {
    for (const ids of [[], ["unknown"], ["broken"]]) {
      const batch = prepareIngredients(ids);
      expect(batch.text).toBe("");
      expect(batch.tokens.length).toBe(0);
    }
  });
  it("creates data from a taste choice, including a poor preference, without implying training", () => {
    const good = preferencePair("b");
    const poor = preferencePair("a");
    expect(good.chosen).toContain("Dairy-free");
    expect(poor.chosen).toContain("cheese");
    expect(poor.rejected).toBe(good.chosen);
    expect(Object.keys(good)).toEqual(["prompt", "chosen", "rejected"]);
  });
});

describe("bounded trainer handoff", () => {
  const now = 10_000_000;
  it("roundtrips byte-valid text with explicit source and version", () => {
    const batch = createBatch("Rice, café, 米", now);
    expect(parseBatch(JSON.stringify(batch), now)).toEqual(batch);
  });
  it("rejects malformed, oversized, expired, future, or unknown-version imports", () => {
    const good = createBatch("Rice", now);
    const invalid = [
      null,
      "{",
      JSON.stringify([]),
      JSON.stringify({ ...good, version: 2 }),
      JSON.stringify({ ...good, source: "other" }),
      JSON.stringify({ ...good, text: "" }),
      JSON.stringify({ ...good, text: "a\u0000b" }),
      JSON.stringify({ ...good, text: "a".repeat(MAX_BATCH_BYTES + 1) }),
      JSON.stringify({ ...good, createdAt: now + 1 }),
      JSON.stringify({ ...good, createdAt: now - HANDOFF_TTL - 1 }),
      JSON.stringify({ ...good, createdAt: null }),
    ];
    for (const raw of invalid) expect(parseBatch(raw, now)).toBeNull();
  });
  it("bounds UTF-8 bytes rather than JavaScript character count", () => {
    expect(() => createBatch("米".repeat(MAX_BATCH_BYTES / 2), now)).toThrow();
    expect(
      parseBatch(
        JSON.stringify(createBatch("a".repeat(MAX_BATCH_BYTES), now)),
        now,
      )?.text.length,
    ).toBe(MAX_BATCH_BYTES);
  });
});
