#!/usr/bin/env node

import { capture } from "./code-health-files.mjs";

// Accepted legacy advisories are tracked in PostTrainLLM/posttrainllm#104.
//
// This is one workspace (pnpm-workspace.yaml), so there is one dependency
// graph and one audit. Auditing per package directory would just re-report the
// same workspace-wide graph three times.
//
// The 2026-09 maintenance update moved Blume from 1.0.4 to 1.5.3. That removed
// three accepted undici advisories and reduced the full audit from 24 findings
// to 13. Blume's image-size dependency is now locked to patched 2.0.4, so its
// former parser DoS exceptions are removed. The path-to-regexp advisory remains
// inside Blume's unused Vercel adapter path; this site builds statically and
// does not ship that server adapter.
const scopes = [
  {
    name: "workspace",
    directory: ".",
    acceptedHigh: new Set([
      // surfaced by workspace dedupe, 2026-08
      "1101846", // path-to-regexp
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
