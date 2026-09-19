import { describe, expect, it } from "vitest";
import {
  applyCheckpoint,
  completeRecall,
  createCheckpoint,
  dueRecalls,
  emptyLearningState,
  makeBackup,
  mergeLearningState,
  parseBackup,
  selectLearningModule,
  statusForModule,
} from "../learning/state";

const started = new Date("2026-09-19T10:00:00.000Z");

function answeredState() {
  const state = emptyLearningState(started);
  state.draft = {
    actualWork: "m=2, b=1; predictions 1,3,5,7,9",
    explanation: "Inputs and targets stay fixed. Parameters change.",
    repoConnection: "weights in model.py",
    openQuestions: "",
  };
  return state;
}

describe("learning state", () => {
  it("schedules recall two and seven calendar days after an immediate pass", () => {
    const state = answeredState();
    const checkpoint = createCheckpoint(state, "pass", started);
    expect(checkpoint.recalls.map((recall) => recall.dueDate)).toEqual([
      "2026-09-21",
      "2026-09-26",
    ]);
    expect(applyCheckpoint(state, checkpoint, started).status).toBe("applied");
  });

  it("does not mark a module verified until both recalls pass", () => {
    const checkpoint = createCheckpoint(answeredState(), "pass", started);
    let state = applyCheckpoint(answeredState(), checkpoint, started);
    state = completeRecall(
      state,
      checkpoint.id,
      "plus-2",
      "first answer",
      "pass",
      new Date("2026-09-21T10:00:00Z"),
    );
    expect(state.status).toBe("applied");
    state = completeRecall(
      state,
      checkpoint.id,
      "plus-7",
      "second answer",
      "pass",
      new Date("2026-09-26T10:00:00Z"),
    );
    expect(state.status).toBe("verified");
  });

  it("returns to reading when a recall needs repair", () => {
    const checkpoint = createCheckpoint(answeredState(), "pass", started);
    const state = completeRecall(
      applyCheckpoint(answeredState(), checkpoint, started),
      checkpoint.id,
      "plus-2",
      "I confused inputs and parameters",
      "needs-repair",
      new Date("2026-09-21T10:00:00Z"),
    );
    expect(state.status).toBe("reading");
    expect(state.checkpoints[0].recalls).toHaveLength(1);
  });

  it("exposes only due pending recalls", () => {
    const checkpoint = createCheckpoint(answeredState(), "pass", started);
    const state = applyCheckpoint(answeredState(), checkpoint, started);
    expect(dueRecalls(state, new Date("2026-09-20T10:00:00Z"))).toHaveLength(0);
    expect(dueRecalls(state, new Date("2026-09-21T10:00:00Z"))).toHaveLength(1);
    expect(dueRecalls(state, new Date("2026-09-27T10:00:00Z"))).toHaveLength(2);
  });
});

describe("learning backup and module selection", () => {
  it("round-trips a valid backup and rejects unrelated JSON", () => {
    const state = answeredState();
    expect(
      parseBackup(JSON.stringify(makeBackup(state, started))).state,
    ).toEqual(state);
    expect(() => parseBackup('{"hello":"world"}')).toThrow(
      "not a PostTrainLLM learning backup",
    );
  });

  it("merges checkpoint history without duplicate IDs", () => {
    const first = answeredState();
    const checkpoint = createCheckpoint(first, "pass", started);
    const withCheckpoint = applyCheckpoint(first, checkpoint, started);
    const merged = mergeLearningState(
      withCheckpoint,
      withCheckpoint,
      new Date("2026-09-20T10:00:00Z"),
    );
    expect(merged.checkpoints).toHaveLength(1);
  });

  it("moves to another module while retaining the prior checkpoint and recalls", () => {
    const first = answeredState();
    const checkpoint = createCheckpoint(first, "pass", started);
    const selected = selectLearningModule(
      applyCheckpoint(first, checkpoint, started),
      "loss-gradient-descent",
      new Date("2026-09-19T11:00:00Z"),
    );
    expect(selected.currentModuleId).toBe("loss-gradient-descent");
    expect(selected.status).toBe("reading");
    expect(selected.draft.actualWork).toBe("");
    expect(selected.checkpoints[0].recalls).toHaveLength(2);
  });

  it("keeps the active module status when completing an older module recall", () => {
    const first = answeredState();
    const checkpoint = createCheckpoint(first, "pass", started);
    let state = selectLearningModule(
      applyCheckpoint(first, checkpoint, started),
      "loss-gradient-descent",
    );
    state = completeRecall(
      state,
      checkpoint.id,
      "plus-2",
      "closed-book answer",
      "pass",
      new Date("2026-09-21T10:00:00Z"),
    );
    expect(state.status).toBe("reading");
    expect(statusForModule(state.checkpoints, first.currentModuleId)).toBe(
      "applied",
    );
  });

  it("uses the active module's own delayed-recall prompts", () => {
    const selected = selectLearningModule(
      answeredState(),
      "loss-gradient-descent",
    );
    selected.draft.actualWork = "MSE values and one update";
    selected.draft.explanation = "Loss and gradients guide the update";
    const checkpoint = createCheckpoint(selected, "pass", started);
    expect(checkpoint.recalls[0].prompt).toContain("compute MSE");
    expect(checkpoint.recalls[1].prompt).toContain("loss curves");
    expect(checkpoint.recalls[0].prompt).not.toContain("mx + b");
  });

  it("rejects a backup that selects a module outside the curriculum", () => {
    const backup = makeBackup(answeredState(), started);
    backup.state.currentModuleId = "missing-module";
    expect(() => parseBackup(JSON.stringify(backup))).toThrow("unsupported");
  });
});
