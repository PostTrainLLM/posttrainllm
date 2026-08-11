#!/usr/bin/env node

import { changedFiles, commandWithUvx, run } from "./code-health-files.mjs";

run("pnpm", ["--dir", "browser", "run", "typecheck"]);

const pythonFiles = changedFiles([".py"]);
if (pythonFiles.length > 0) {
  const ruff = commandWithUvx("ruff", ["ruff==0.16.2"]);
  run(ruff.command, [...ruff.prefix, "check", ...pythonFiles]);
}

const rustFiles = changedFiles([".rs"]);
if (rustFiles.length > 0)
  run("rustfmt", ["--edition", "2024", "--check", ...rustFiles]);

for (const file of changedFiles([".js", ".mjs", ".cjs"]))
  run("node", ["--check", file]);
console.log(
  `Lint: browser typecheck and changed files passed (${pythonFiles.length} Python, ${rustFiles.length} Rust).`,
);
