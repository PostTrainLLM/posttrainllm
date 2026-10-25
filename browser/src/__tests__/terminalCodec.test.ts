import { describe, it, expect } from "vitest";
import {
  allowed,
  applyDelta,
  eventTokens,
  screen,
  snapshot,
  T,
} from "../specialists/terminal-codec";
import { validateConfig } from "../specialists/terminal-shapes";

describe("portable terminal codec", () => {
  it("rejects excessive activation memory before allocating a runtime", () => {
    const cfg = {
      vocab_size: 333,
      context_length: 2048,
      d_model: 64,
      n_heads: 4,
      n_layers: 2,
      d_mlp: 128,
      dropout: 0,
    };
    expect(validateConfig(cfg).length).toBe(36);
    expect(() =>
      validateConfig({
        ...cfg,
        d_model: 256,
        n_heads: 256,
        n_layers: 1,
        d_mlp: 256,
      }),
    ).toThrow();
    expect(() =>
      validateConfig({ ...cfg, n_heads: 16, n_layers: 8, d_model: 256 }),
    ).toThrow(/allocation/);
  });
  const original = screen({
    lines: ["one     ", "two     ", "        "],
    cursor_row: 0,
    cursor_col: 3,
    visible: true,
  });
  it("copies from the old frame atomically and applies a text span", () => {
    const tokens = [
      T.OUTPUT,
      T.ROW,
      T.COPY,
      1,
      T.ROW_END,
      T.ROW + 1,
      T.COPY,
      0,
      T.ROW_END,
      T.ROW + 2,
      T.TEXT,
      2,
      65,
      66,
      T.ROW_END,
      T.CURSOR,
      2,
      4,
      0,
      T.OUTPUT_END,
    ];
    expect(allowed(tokens, original)).toEqual([]);
    expect(applyDelta(original, tokens)).toEqual({
      lines: ["two     ", "one     ", "  AB    "],
      cursor_row: 2,
      cursor_col: 4,
      visible: false,
    });
  });
  it("rejects incomplete updates, repeated rows, invalid text and cursors", () => {
    for (const tokens of [
      [],
      [T.OUTPUT, T.CURSOR, 0, 0, 1],
      [T.OUTPUT, T.ROW, T.COPY, 0, T.ROW_END, T.ROW],
      [T.OUTPUT, T.ROW, T.TEXT, 0, 9],
      [T.OUTPUT, T.CURSOR, 3, 0, 1, T.OUTPUT_END],
    ])
      expect(() => applyDelta(original, tokens)).toThrow();
  });
  it("preserves special ids and raw-key versus wait boundaries", () => {
    expect(eventTokens({ keys: [27, 91, 68] })).toEqual([324, 27, 91, 68, 325]);
    expect(eventTokens({ wait_ms: 1000 })).toEqual([329, 3, 232, 325]);
    expect(
      snapshot(
        screen({
          lines: ["$       "],
          cursor_row: 0,
          cursor_col: 2,
          visible: true,
        }),
      ),
    ).toEqual([
      320, 321, 1, 8, 256, 330, 36, 32, 32, 32, 32, 32, 32, 32, 331, 323, 0, 2,
      1, 322,
    ]);
    for (const event of [
      { wait_ms: -1 },
      { keys: [333] },
      { keys: [] },
      { keys: [1], wait_ms: 1 },
    ])
      expect(() => eventTokens(event)).toThrow();
  });
});
