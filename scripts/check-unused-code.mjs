#!/usr/bin/env node

import { capture, commandWithUvx } from "./code-health-files.mjs";

const knipBaseline = { exports: 0, types: 3 };
const knip = capture("pnpm", [
  "exec",
  "knip",
  "--directory",
  "browser",
  "--config",
  "knip.json",
  "--reporter",
  "json",
  "--no-exit-code",
  "--no-progress",
]);
const report = JSON.parse(knip.stdout);
const counts = {};
for (const issue of report.issues) {
  for (const [kind, entries] of Object.entries(issue)) {
    if (Array.isArray(entries))
      counts[kind] = (counts[kind] ?? 0) + entries.length;
  }
}

let failed = false;
for (const [kind, count] of Object.entries(counts)) {
  const maximum = knipBaseline[kind] ?? 0;
  if (count > maximum) {
    console.error(`Knip ${kind} regressed: ${count} > ${maximum}.`);
    failed = true;
  }
}
for (const [kind, maximum] of Object.entries(knipBaseline)) {
  if ((counts[kind] ?? 0) < maximum)
    console.log(`Knip ${kind} improved; lower the baseline from ${maximum}.`);
}

const vultureTool = commandWithUvx("vulture", ["vulture==2.16"]);
const vulture = capture(
  vultureTool.command,
  [
    ...vultureTool.prefix,
    "python_ref",
    "scripts",
    "--exclude",
    "*/archive/*",
    "--min-confidence",
    "100",
    "--sort-by-size",
  ],
  { allowFailure: true },
);
const vultureFindings = vulture.stdout.split("\n").filter(Boolean);
console.log(
  `Unused code: Knip exports=${counts.exports ?? 0}, types=${counts.types ?? 0}; ` +
    `Vulture high-confidence findings=${vultureFindings.length}.`,
);
if (vultureFindings.length > 0) {
  process.stdout.write(vulture.stdout);
  console.error("Vulture findings exceed the accepted baseline of 0.");
  failed = true;
}
if (failed) process.exit(1);
