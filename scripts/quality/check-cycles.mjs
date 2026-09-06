#!/usr/bin/env node

import { capture } from "./code-health-files.mjs";

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

// pycycle==0.0.8 seeds its traversal from whichever file os.walk() lists
// first, an order that depends on the filesystem/checkout rather than the
// code, and flags any node reached twice as a cycle -- so a plain fan-in
// (e.g. train.py and sample.py both importing model.py) is misreported as
// circular purely depending on that order. A real `git clone` checkout
// reproduced a false-positive 10/10 runs in the 2026-09-06 investigation
// for a graph that a manual trace shows is a DAG. check_python_cycles.py
// re-implements the same check with a deterministic white/gray/black DFS.
const python = capture("python3", [
  "scripts/quality/check_python_cycles.py",
  "python_ref",
]);
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
