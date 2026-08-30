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

// Report-card JSON/HTML are compiler outputs guarded byte-for-byte by the
// fine-tune report-card drift smoke. Reformatting them would make the two
// publication gates contradict each other.
const prettierFiles = changedFiles([
  ".js",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".astro",
  ".json",
]).filter((file) => !file.startsWith("browser/public/report-cards/"));
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
