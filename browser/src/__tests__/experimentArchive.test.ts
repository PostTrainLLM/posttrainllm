import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import pathRegistry from "../../../docs/learn/path-registry.json";
import attemptPayload from "../../../docs/attempts.json";
import { artifacts } from "../artifacts";
import {
  experimentLearningHref,
  experimentMatches,
  experimentPublicHref,
  experimentRecipeHref,
  learningPathByFamily,
} from "../data/experimentArchive";

describe("experiment archive navigation", () => {
  it("classifies the evidence behind every public headline metric", () => {
    const evidenceClasses = new Set([
      "measured",
      "historical",
      "derived",
      "observed",
      "not-measured",
    ]);

    for (const artifact of artifacts) {
      expect(artifact.metrics.length, artifact.slug).toBeGreaterThan(0);
      for (const metric of artifact.metrics) {
        expect(evidenceClasses, `${artifact.slug}:${metric.label}`).toContain(
          metric.evidence,
        );
      }
    }

    const artifactPage = readFileSync(
      resolve(import.meta.dirname, "../pages/artifacts/[slug].astro"),
      "utf8",
    );
    expect(artifactPage).toContain("data-evidence={metric.evidence}");
    expect(artifactPage).toContain("not-measured = an explicit evidence gap");
  });

  it("maps every retained family to a specific learning path", () => {
    const families = new Set(
      attemptPayload.attempts.map((attempt) => attempt.family),
    );
    expect(new Set(Object.keys(learningPathByFamily))).toEqual(families);
    const pathHrefs = new Set(
      pathRegistry.paths.map((path) => `/learn#path-${path.id}`),
    );
    for (const attempt of attemptPayload.attempts) {
      expect(pathHrefs).toContain(experimentLearningHref(attempt));
      const recipeHref = experimentRecipeHref(attempt);
      expect(recipeHref).toMatch(/^\//u);
      if (recipeHref.startsWith("/docs/")) {
        expect(
          existsSync(resolve(import.meta.dirname, `../../..${recipeHref}.md`)),
        ).toBe(true);
      }
    }
  });

  it("sends Needle and Parakeet experiments to their public artifacts", () => {
    const byId = Object.fromEntries(
      attemptPayload.attempts.map((attempt) => [attempt.id, attempt]),
    );
    expect(experimentPublicHref(byId["needle2-task-catalog-ablation"])).toBe(
      "/artifacts/needle2-tool-selection",
    );
    expect(experimentRecipeHref(byId["needle2-task-catalog-ablation"])).toBe(
      "/docs/techniques/needle2-baseline-review",
    );
    expect(experimentPublicHref(byId["parakeet-wgsl-browser-asr-smoke"])).toBe(
      "/artifacts/parakeet-wgsl-browser-asr",
    );

    const artifactHrefs = new Set(
      artifacts.map((artifact) => `/artifacts/${artifact.slug}`),
    );
    for (const attempt of attemptPayload.attempts) {
      const href = experimentPublicHref(attempt);
      if (href.startsWith("/artifacts/")) expect(artifactHrefs).toContain(href);
    }
  });

  it("combines query, family, and outcome filters", () => {
    const candidate = {
      search: "needle catalog selection",
      family: "pace-planner",
      status: "worked-with-caveat",
    };
    expect(
      experimentMatches(
        candidate,
        "needle",
        "pace-planner",
        "worked-with-caveat",
      ),
    ).toBe(true);
    expect(experimentMatches(candidate, "sql", "", "")).toBe(false);
    expect(experimentMatches(candidate, "", "sql", "")).toBe(false);
    expect(experimentMatches(candidate, "", "", "failed")).toBe(false);
  });
});
