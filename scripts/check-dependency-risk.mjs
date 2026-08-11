#!/usr/bin/env node

import { capture } from "./code-health-files.mjs";

// Accepted legacy advisories are tracked in PostTrainLLM/posttrainllm#104.
const scopes = [
  { name: "root", directory: ".", acceptedHigh: new Set() },
  {
    name: "browser",
    directory: "browser",
    acceptedHigh: new Set(["1120912", "1120917", "1124066"]),
  },
  {
    name: "docs",
    directory: "docs-site",
    acceptedHigh: new Set([
      "1124064",
      "1130589",
      "1130591",
      "1130717",
      "1130720",
      "1130722",
      "1130734",
      "1130736",
      "1138114",
      "1138115",
      "1138813",
    ]),
  },
];

let failed = false;
for (const scope of scopes) {
  const result = capture("pnpm", ["audit", "--json"], {
    cwd: scope.directory,
    allowFailure: true,
  });
  let report;
  try {
    report = JSON.parse(result.stdout);
  } catch {
    process.stderr.write(result.stderr);
    console.error(`${scope.name}: pnpm audit did not return valid JSON.`);
    failed = true;
    continue;
  }
  const advisories = Object.entries(report.advisories ?? {});
  const critical = advisories.filter(
    ([, advisory]) => advisory.severity === "critical",
  );
  const high = advisories.filter(
    ([, advisory]) => advisory.severity === "high",
  );
  const unexpectedHigh = high.filter(([id]) => !scope.acceptedHigh.has(id));
  const resolvedHigh = [...scope.acceptedHigh].filter(
    (id) => !high.some(([current]) => current === id),
  );
  const counts = report.metadata?.vulnerabilities ?? {};
  console.log(
    `${scope.name}: ${critical.length} critical, ${high.length} high, ${counts.moderate ?? 0} moderate, ` +
      `${counts.low ?? 0} low.`,
  );
  if (resolvedHigh.length > 0) {
    console.error(
      `${scope.name}: remove resolved high advisory IDs: ${resolvedHigh.join(", ")}.`,
    );
    failed = true;
  }
  for (const [id, advisory] of [...critical, ...unexpectedHigh]) {
    console.error(
      `${scope.name}: unaccepted ${advisory.severity} advisory ${id} in ${advisory.module_name}.`,
    );
    failed = true;
  }
}
if (failed) process.exit(1);
console.log(
  "Dependency risk: no critical or unaccepted high JavaScript advisories.",
);
