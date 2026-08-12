#!/usr/bin/env node

import { capture, commandWithUvx } from "./code-health-files.mjs";

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
const baseline = {
  warnings: 308,
  maxNloc: 795,
  maxCcn: 113,
  maxTokens: 2512,
  maxParams: 39,
  maxLength: 796,
};

const lizard = commandWithUvx("lizard", ["--from", "lizard==1.23.0", "lizard"]);
const result = capture(lizard.command, [
  ...lizard.prefix,
  ...paths,
  "-x",
  "scripts/archive/*",
  "--csv",
]);
const rows = result.stdout
  .trim()
  .split("\n")
  .map((line) => line.match(/^(\d+),(\d+),(\d+),(\d+),(\d+),/u))
  .filter(Boolean)
  .map((match) => match.slice(1).map(Number));

const observed = {
  functions: rows.length,
  nloc: rows.reduce((sum, row) => sum + row[0], 0),
  warnings: rows.filter((row) => row[1] > 15 || row[4] > 100 || row[3] > 7)
    .length,
  maxNloc: Math.max(...rows.map((row) => row[0])),
  maxCcn: Math.max(...rows.map((row) => row[1])),
  maxTokens: Math.max(...rows.map((row) => row[2])),
  maxParams: Math.max(...rows.map((row) => row[3])),
  maxLength: Math.max(...rows.map((row) => row[4])),
};
console.log(
  `Complexity: ${observed.functions} functions, ${observed.nloc} NLOC, ${observed.warnings} threshold violations; ` +
    `max CCN ${observed.maxCcn}, max length ${observed.maxLength}.`,
);

const regressions = Object.entries(baseline).filter(
  ([key, maximum]) => observed[key] > maximum,
);
if (regressions.length > 0) {
  for (const [key, maximum] of regressions) {
    console.error(
      `Complexity ${key} regressed: ${observed[key]} > ${maximum}.`,
    );
  }
  process.exit(1);
}
if (
  Object.entries(baseline).some(([key, maximum]) => observed[key] < maximum)
) {
  console.log(
    "Complexity improved; lower the checked-in baseline in the next intentional update.",
  );
}
