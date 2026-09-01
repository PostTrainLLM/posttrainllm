#!/usr/bin/env node

import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { capture } from "./code-health-files.mjs";

// Re-baselined after the 2026-09 maintenance cleanup. The scripts regrouping
// and the completed CLI catalog plus artifact journey expanded the measured
// corpus without adding clone groups, so the exact ratio improved again:
//
//   before  4255 / 137,207 = 3.1012%, 271 clone groups
//   CLI     4255 / 138,445 = 3.0734%, 271 clone groups
//   after   4255 / 138,634 = 3.0692%, 271 clone groups
//
// Tracked in PostTrainLLM/posttrainllm#104.
const baseline = {
  duplicatedLines: 4255,
  percentage: 3.069232655769869,
  clones: 271,
};
const outputDirectory = mkdtempSync(join(tmpdir(), "posttrainllm-jscpd-"));
const paths = [
  "native-mac/Sources",
  "python_ref",
  "scripts",
  "browser/src",
  "browser/functions",
  "wasm",
  "webgpu",
  "scripts/humaneval-sandbox/src",
  "scripts/tokenizer-trainer/src",
  "scripts/hf-downloader/src",
  "scripts/parquet-decoder/src",
];
capture("pnpm", [
  "exec",
  "jscpd",
  ...paths,
  "--format",
  "swift,python,typescript,javascript,cpp,cpp-header,rust",
  "--min-lines",
  "8",
  "--min-tokens",
  "60",
  "--mode",
  "strict",
  "--ignore",
  "**/archive/**,**/fixtures/**,**/node_modules/**,**/.build/**,**/Generated/**,**/generated/**",
  "--reporters",
  "json",
  "--output",
  outputDirectory,
  "--silent",
  "--no-tips",
]);

const observed = JSON.parse(
  readFileSync(join(outputDirectory, "jscpd-report.json"), "utf8"),
).statistics.total;
console.log(
  `Duplication: ${observed.duplicatedLines}/${observed.lines} lines (${observed.percentage.toFixed(4)}%), ` +
    `${observed.clones} clone groups across ${observed.sources} files.`,
);
if (
  observed.duplicatedLines > baseline.duplicatedLines ||
  observed.percentage > baseline.percentage ||
  observed.clones > baseline.clones
) {
  console.error(
    "Duplication exceeds the accepted baseline tracked in PostTrainLLM/posttrainllm#104.",
  );
  process.exit(1);
}
if (
  observed.duplicatedLines < baseline.duplicatedLines ||
  observed.percentage < baseline.percentage ||
  observed.clones < baseline.clones
) {
  console.log(
    "Duplication improved; lower the checked-in baseline in the next intentional update.",
  );
}
