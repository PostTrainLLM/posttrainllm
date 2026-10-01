import { describe, it, expect } from "vitest";
import { LESSON_TTL, parseLesson, type Lesson } from "../kitchen/session";
const state: Lesson = {
  version: 2,
  savedAt: 10000000,
  selected: ["explanation", "dairy", "weather"],
  chopText: "café",
  chopped: true,
  prepared: true,
  checkpoint: "sft",
  choice: "b",
  simulated: true,
  garnished: true,
  cookStep: 3,
};
describe("lesson continuity", () => {
  it("retains teaching decisions without storing a corpus or chat transcript", () => {
    const parsed = parseLesson(
      JSON.stringify({
        ...state,
        chat: [{ content: "private" }],
        preparedText: "untrusted",
      }),
      state.savedAt,
    );
    expect(parsed).toEqual(state);
    expect(Object.keys(parsed!)).not.toContain("chat");
  });
  it("rejects stale, malformed or out-of-bounds state", () => {
    for (const change of [
      { version: 1 },
      { savedAt: state.savedAt + 1 },
      { savedAt: state.savedAt - LESSON_TTL - 1 },
      { selected: ["unknown"] },
      { selected: ["code", "code"] },
      { chopText: "a".repeat(81) },
      { cookStep: 4 },
      { cookStep: -1 },
      { choice: "c" },
      { choice: null, simulated: true },
      { checkpoint: "unknown" },
      { prepared: "yes" },
    ])
      expect(
        parseLesson(JSON.stringify({ ...state, ...change }), state.savedAt),
      ).toBeNull();
    expect(parseLesson("{")).toBeNull();
    expect(parseLesson("a".repeat(2049))).toBeNull();
  });
});
