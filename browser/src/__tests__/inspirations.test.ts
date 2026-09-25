import { describe, expect, it } from "vitest";
import {
  inspirations,
  validateInspirationCoverage,
} from "../data/inspirations";

describe("public inspiration inventory", () => {
  it("groups every retained study once and keeps stable, sourced product routes", () => {
    expect(validateInspirationCoverage()).toEqual([]);
    expect(new Set(inspirations.map((entry) => entry.slug)).size).toBe(
      inspirations.length,
    );
    for (const entry of inspirations) {
      expect(entry.slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
      expect(entry.opening.length).toBeGreaterThan(80);
      expect(entry.source.href).toMatch(/^https:\/\//);
      expect(
        entry.studyIds.length + (entry.evidence?.length ?? 0),
      ).toBeGreaterThan(0);
    }
    expect(
      inspirations.find((entry) => entry.slug === "halo")?.source.href,
    ).toBe("https://github.com/whitecircle/halo");
  });
});
