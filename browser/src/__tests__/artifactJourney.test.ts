import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import artifactJourney from "../../../docs/learn/artifact-journey.json";
import pathRegistry from "../../../docs/learn/path-registry.json";

const root = resolve(import.meta.dirname, "../../..");

describe("buildable artifact journey", () => {
  it("covers every learning path with a finite ordered stage", () => {
    expect(artifactJourney.stages).toHaveLength(9);
    expect(artifactJourney.stages.map((stage) => stage.order)).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9,
    ]);
    expect(
      new Set(artifactJourney.stages.map((stage) => stage.path_id)),
    ).toEqual(new Set(pathRegistry.paths.map((path) => path.id)));
  });

  it("gives every artifact the full build-to-package contract", () => {
    const artifacts = artifactJourney.stages.flatMap(
      (stage) => stage.artifacts,
    );
    expect(artifacts).toHaveLength(13);
    expect(new Set(artifacts.map((artifact) => artifact.id)).size).toBe(13);

    for (const artifact of artifacts) {
      for (const action of [
        artifact.build,
        artifact.modify,
        artifact.tune,
        artifact.evaluate,
        artifact.package,
      ]) {
        expect(action.label.length).toBeGreaterThan(20);
        expect(action.href.length).toBeGreaterThan(1);
        if (
          !action.href.startsWith("/") &&
          !action.href.startsWith("https://")
        ) {
          expect(existsSync(resolve(root, action.href))).toBe(true);
        }
      }
      for (const anchor of artifact.anchors) {
        expect(existsSync(resolve(root, anchor))).toBe(true);
      }
    }
  });

  it("renders the machine-readable contract on the public learning page", () => {
    const learnPage = readFileSync(
      resolve(root, "browser/src/pages/learn.astro"),
      "utf8",
    );
    expect(learnPage).toContain("../../../docs/learn/artifact-journey.json");
    expect(learnPage).toContain("artifactStages");
    expect(learnPage).toContain("artifact-actions");
    for (const action of ["Build", "Modify", "Tune", "Prove", "Package"]) {
      expect(learnPage).toContain(`name: "${action}"`);
    }
  });
});
