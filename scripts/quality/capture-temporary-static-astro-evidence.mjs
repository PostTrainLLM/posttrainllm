#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { createQualificationEvidence } from "./temporary-static-astro-qualification.mjs";

const outputPath = process.argv[2];
if (!outputPath) {
  console.error(
    "Usage: node scripts/quality/capture-temporary-static-astro-evidence.mjs <output.json>",
  );
  process.exit(2);
}

const repoRoot = process.cwd();
const commit = execFileSync("git", ["rev-parse", "HEAD"], {
  encoding: "utf8",
}).trim();
const evidence = await createQualificationEvidence(repoRoot, commit);
const target = resolve(outputPath);
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, `${JSON.stringify(evidence, null, 2)}\n`, {
  mode: 0o600,
});
console.log(`Temporary static Astro evidence captured for ${commit}.`);
