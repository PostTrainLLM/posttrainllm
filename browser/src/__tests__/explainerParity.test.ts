import { readFileSync, readdirSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { EXPLAINERS } from "../explainers";

const sourceRoot = resolve(import.meta.dirname, "..");

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      return entry.name === "__tests__" ? [] : sourceFiles(path);
    }
    return [".astro", ".ts"].includes(extname(path)) ? [path] : [];
  });
}

describe("popover explainer parity", () => {
  it("defines every statically referenced explainer key", () => {
    const referenced = new Set<string>();
    const patterns = [
      /data-explain=["']([A-Za-z][A-Za-z0-9]*)["']/g,
      /dataset\.explain\s*=\s*["']([A-Za-z][A-Za-z0-9]*)["']/g,
    ];

    for (const file of sourceFiles(sourceRoot)) {
      const source = readFileSync(file, "utf8");
      for (const pattern of patterns) {
        for (const match of source.matchAll(pattern)) referenced.add(match[1]);
      }
    }

    expect([...referenced].sort()).not.toHaveLength(0);
    for (const key of referenced) {
      expect(EXPLAINERS, `missing explainer for data-explain=${key}`).toHaveProperty(
        key,
      );
    }
  });
});
