#!/usr/bin/env node

import { capture, commandWithUvx } from "./code-health-files.mjs";

const knip = capture("pnpm", [
  "exec",
  "knip",
  "--directory",
  "browser",
  "--config",
  "knip.json",
  "--cycles",
  "--reporter",
  "json",
  "--no-exit-code",
  "--no-progress",
]);
const browserCycles = JSON.parse(knip.stdout).issues.flatMap(
  (issue) => issue.cycles ?? [],
);
if (browserCycles.length > 0) {
  console.error(`Browser dependency cycles detected: ${browserCycles.length}.`);
  process.exit(1);
}

const pycycle = commandWithUvx("pycycle", ["pycycle==0.0.8"]);
const python = capture(pycycle.command, [...pycycle.prefix, "--here"], {
  cwd: "python_ref",
});
if (!python.stdout.includes("No worries, no cycles here!")) {
  process.stdout.write(python.stdout);
  console.error("Python cycle analysis did not produce a clean result.");
  process.exit(1);
}

for (const manifest of [
  "scripts/humaneval-sandbox/Cargo.toml",
  "scripts/tokenizer-trainer/Cargo.toml",
  "scripts/hf-downloader/Cargo.toml",
  "scripts/parquet-decoder/Cargo.toml",
]) {
  capture("cargo", [
    "metadata",
    "--no-deps",
    "--format-version",
    "1",
    "--manifest-path",
    manifest,
  ]);
}
if (process.env.CODE_HEALTH_SKIP_SWIFT !== "1") {
  capture("swift", ["package", "dump-package"], { cwd: "native-mac" });
}
console.log(
  `Cycles: browser and Python graphs are acyclic; all four Cargo manifests resolve structurally; ` +
    (process.env.CODE_HEALTH_SKIP_SWIFT === "1"
      ? "SwiftPM is covered by the macOS native job."
      : "SwiftPM resolves structurally."),
);
