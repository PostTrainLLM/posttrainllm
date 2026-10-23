import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  copyFileSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

// Exercise the real CLI against an isolated build, without Astro dependencies.
function check(href) {
  const root = mkdtempSync(join(tmpdir(), "posttrain-links-"));
  try {
    mkdirSync(join(root, "scripts"));
    mkdirSync(join(root, "dist"));
    copyFileSync(
      new URL("./check-built-links.mjs", import.meta.url),
      join(root, "scripts/check-built-links.mjs"),
    );
    const routes = [
      "index",
      "experiments",
      "recipes",
      "learn",
      "artifacts",
      "studies",
      "studies/trainloop-ai",
      "inspiration",
      "inspiration/halo",
      "experiments/sql-toy-sft-r4",
      "recipes/distillation",
      "learn/paths/post-training",
      "learn/artifacts/byte-tinygpt",
      "docs/cli-reference",
    ];
    for (const route of routes) {
      const file = join(root, "dist", `${route}.html`);
      mkdirSync(join(file, ".."), { recursive: true });
      writeFileSync(
        file,
        `<title>Test</title><a href="#main">Skip</a><main id="main"><h1>Test</h1>${route === "index" ? `<a href="${href}">Target</a>` : ""}</main>`,
      );
    }
    writeFileSync(
      join(root, "dist/404.html"),
      '<meta name="robots" content="noindex"><h1>Not found</h1>',
    );
    return spawnSync(
      process.execPath,
      [join(root, "scripts/check-built-links.mjs")],
      { encoding: "utf8" },
    );
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

for (const href of [
  "/missing",
  "https://posttrainllm.com/missing",
  "//posttrainllm.com/missing",
  "https://posttrainllm.com/recipes#missing",
]) {
  test(`rejects broken internal href ${href}`, () => {
    const result = check(href);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /BROKEN LINK/);
  });
}
for (const href of [
  "/recipes#main",
  "https://posttrainllm.com/recipes#main",
  "//posttrainllm.com/recipes#main",
  "https://example.com/missing",
  "mailto:hello@example.com",
]) {
  test(`accepts valid or external href ${href}`, () => {
    const result = check(href);
    assert.equal(result.status, 0, result.stderr);
  });
}
