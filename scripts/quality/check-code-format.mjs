#!/usr/bin/env node

import { changedFiles, commandWithUvx, run } from "./code-health-files.mjs";

if (process.env.CODE_HEALTH_SKIP_SWIFT !== "1") {
  run("swiftformat", ["--lint", "native-mac/Sources", "native-mac/Tests"]);
}

const pythonFiles = changedFiles([".py"]);
if (pythonFiles.length > 0) {
  const ruff = commandWithUvx("ruff", ["ruff==0.16.2"]);
  run(ruff.command, [...ruff.prefix, "format", "--check", ...pythonFiles]);
}

// Compiler outputs guarded byte-for-byte by a drift smoke. Reformatting them
// would make the two gates contradict each other: prettier demands its own
// style, the drift check demands exactly what the generator emits.
//
//   browser/public/report-cards/   fine-tune report-card drift smoke
//   evals/everyday-benchmark/      render_everyday_benchmark_report.py --check
const prettierFiles = changedFiles([
  ".js",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".astro",
  ".json",
]).filter(
  (file) =>
    !file.startsWith("browser/public/report-cards/") &&
    !file.startsWith("evals/everyday-benchmark/"),
);
if (prettierFiles.length > 0) {
  run("pnpm", [
    "exec",
    "prettier",
    "--plugin",
    "prettier-plugin-astro",
    "--check",
    ...prettierFiles,
  ]);
}

console.log(
  `Format: Swift ${process.env.CODE_HEALTH_SKIP_SWIFT === "1" ? "covered by the macOS lane" : "passed"}; ` +
    `${pythonFiles.length} changed Python and ${prettierFiles.length} changed web/config files passed.`,
);
