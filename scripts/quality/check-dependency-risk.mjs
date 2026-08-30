#!/usr/bin/env node

import { capture } from "./code-health-files.mjs";

// Accepted legacy advisories are tracked in PostTrainLLM/posttrainllm#104.
//
// This is one workspace (pnpm-workspace.yaml), so there is one dependency
// graph and one audit. Auditing per package directory would just re-report the
// same workspace-wide graph three times.
//
// Moving to a workspace changed resolution: shared transitive deps now dedupe
// to single versions instead of one copy per package. Net effect was 14 high
// advisories down to 7. Ten of the old docs-site entries (brace-expansion,
// fast-uri, js-yaml, tar, ip-address, undici 1130717) resolved themselves and
// are gone. Four became newly visible and are accepted here pending #104:
// path-to-regexp 1101846 and undici 1114638 / 1114640 / 1121245.
const scopes = [
  {
    name: "workspace",
    directory: ".",
    acceptedHigh: new Set([
      // carried over, still present
      "1124066", // sharp
      "1139377", // astro
      "1139378", // astro
      // surfaced by workspace dedupe, 2026-08
      "1101846", // path-to-regexp
      "1114638", // undici
      "1114640", // undici
      "1121245", // undici
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
