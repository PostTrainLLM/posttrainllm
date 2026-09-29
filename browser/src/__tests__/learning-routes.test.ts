import { describe, expect, it } from "vitest";
import { inferenceSessions } from "../learning/inference-content";
import { inferenceWeeks } from "../learning/inference-weeks";
import { learningUnits } from "../learning/content";
import {
  learningRoutes,
  resolveSessionUrl,
  routeForSession,
} from "../learning/routes";

describe("inference course definition", () => {
  it("has seven complete ordered Week 1 lessons with valid next links", () => {
    const ordered = learningRoutes["inference-systems-13w"].orderedSessionIds;
    expect(inferenceSessions.map((session) => session.id)).toEqual(ordered);
    for (const [index, session] of inferenceSessions.entries()) {
      expect(session.readiness).toBe("ready");
      expect(session.minutes).toBe(index < 5 ? 120 : 300);
      expect(session.sections.length).toBeGreaterThan(0);
      expect(session.workedExample.length).toBeGreaterThan(0);
      expect(session.predictionPrompt).toBeTruthy();
      expect(session.exercise).toBeTruthy();
      expect(session.answerGuide.length).toBeGreaterThan(0);
      expect(session.checks.length).toBeGreaterThan(0);
      expect(session.evidence.length).toBeGreaterThan(0);
      expect(session.recallPrompts).toHaveLength(2);
      expect(session.nextSessionId).toBe(ordered[index + 1] ?? null);
    }
  });

  it("preserves all foundation IDs and labels later daily lessons planned", () => {
    expect(learningRoutes["ground-up"].orderedSessionIds).toEqual(
      learningUnits.map((unit) => unit.id),
    );
    expect(inferenceWeeks).toHaveLength(13);
    expect(inferenceWeeks[0].readiness).toBe("ready");
    expect(
      inferenceWeeks
        .slice(1)
        .every(
          (week) =>
            week.readiness === "planned" &&
            week.prerequisites &&
            week.progression &&
            week.artifact &&
            week.passCriterion &&
            week.boundary,
        ),
    ).toBe(true);
  });

  it("resolves explicit URLs without treating invalid combinations as a selection", () => {
    expect(resolveSessionUrl("")).toEqual({
      routeId: null,
      sessionId: null,
      error: null,
    });
    expect(
      resolveSessionUrl(
        "?route=inference-systems-13w&session=inference-w01-d01",
      ),
    ).toEqual({
      routeId: "inference-systems-13w",
      sessionId: "inference-w01-d01",
      error: null,
    });
    expect(routeForSession("functions-data-parameters")).toBe("ground-up");
    expect(
      resolveSessionUrl("?route=ground-up&session=inference-w01-d01").error,
    ).toMatch(/does not belong/);
    expect(resolveSessionUrl("?route=missing").error).toMatch(/Unknown/);
  });
});
