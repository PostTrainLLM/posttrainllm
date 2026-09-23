import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import attemptPayload from "../../../docs/attempts.json";
import artifactJourney from "../../../docs/learn/artifact-journey.json";
import pathRegistry from "../../../docs/learn/path-registry.json";
import recipeRegistry from "../../../docs/recipes/registry.json";
import studyRegistry from "../../../docs/studies/registry.json";
import {
  allKnowledgeRecords,
  experimentRecords,
  knowledgeWordCount,
  learningArtifactRecords,
  learningPathRecords,
  recipeRecords,
  studyRecords,
} from "../data/knowledgeGraph";

const root = resolve(import.meta.dirname, "../../..");

describe("canonical knowledge graph", () => {
  it("gives every source object exactly one canonical route", () => {
    expect(experimentRecords).toHaveLength(attemptPayload.attempts.length);
    expect(recipeRecords).toHaveLength(recipeRegistry.recipes.length);
    expect(learningPathRecords).toHaveLength(pathRegistry.paths.length);
    expect(learningArtifactRecords).toHaveLength(
      artifactJourney.stages.flatMap((stage) => stage.artifacts).length,
    );
    expect(studyRecords).toHaveLength(studyRegistry.studies.length);

    const routes = allKnowledgeRecords.map((record) => record.canonicalPath);
    expect(new Set(routes).size).toBe(routes.length);
  });

  it("keeps metadata, provenance, and relationships substantive and unique", () => {
    const titles = new Set<string>();
    const descriptions = new Set<string>();
    for (const record of allKnowledgeRecords) {
      expect(record.title.length, record.canonicalPath).toBeGreaterThan(3);
      expect(record.description.length, record.canonicalPath).toBeGreaterThan(
        69,
      );
      expect(titles.has(record.title), record.title).toBe(false);
      expect(descriptions.has(record.description), record.title).toBe(false);
      titles.add(record.title);
      descriptions.add(record.description);

      expect(
        record.sections.length,
        record.canonicalPath,
      ).toBeGreaterThanOrEqual(3);
      expect(record.sources.length, record.canonicalPath).toBeGreaterThan(0);
      expect(record.relations.length, record.canonicalPath).toBeGreaterThan(0);
      expect(knowledgeWordCount(record), record.canonicalPath).toBeGreaterThan(
        90,
      );
      expect(existsSync(resolve(root, record.sourceRecord))).toBe(true);
    }
  });

  it("keeps the study registry in lockstep with both tracked study ledgers", () => {
    const reviews = readFileSync(
      resolve(root, "docs/external-products-reviewed.md"),
      "utf8",
    );
    const reviewTable = reviews
      .split("## Reviewed Sources")[1]
      .split("## Gaps Exposed By Reviews")[0]
      .split("\n")
      .filter(
        (line) => /^\|[^-]/u.test(line) && !line.startsWith("| Source |"),
      );
    const roadmap = readFileSync(
      resolve(root, "docs/industry_learning_roadmap.md"),
      "utf8",
    );
    const caseStudies = [...roadmap.matchAll(/^## Case study - /gmu)];

    expect(studyRegistry.studies).toHaveLength(
      reviewTable.length + caseStudies.length,
    );
  });

  it("keeps every dynamic route wired to the shared evidence dossier", () => {
    for (const routeFile of [
      "browser/src/pages/studies/[slug].astro",
      "browser/src/pages/experiments/[id].astro",
      "browser/src/pages/recipes/[id].astro",
      "browser/src/pages/learn/paths/[id].astro",
      "browser/src/pages/learn/artifacts/[id].astro",
    ]) {
      const source = readFileSync(resolve(root, routeFile), "utf8");
      expect(source, routeFile).toContain("EvidenceDossier");
      expect(source, routeFile).toContain("getStaticPaths");
    }
  });
});
