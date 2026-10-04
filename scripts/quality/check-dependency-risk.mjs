#!/usr/bin/env node

import { capture } from "./code-health-files.mjs";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import {
  TEMPORARY_ADVISORY,
  qualifyAuditFinding,
} from "./temporary-static-astro-qualification.mjs";

// Accepted legacy advisories are tracked in PostTrainLLM/posttrainllm#104.
// The separate static Astro exception is tracked in #190 and expires on
// 2026-10-18; pnpm audit continues to report it on every run.
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
const evidencePath = process.env.RUNNER_TEMP
  ? `${process.env.RUNNER_TEMP}/temporary-static-astro-qualification.json`
  : "/tmp/temporary-static-astro-qualification.json";
let qualificationEvidence;
try {
  qualificationEvidence = JSON.parse(readFileSync(evidencePath, "utf8"));
} catch {
  qualificationEvidence = null;
}
const expectedCommit = execFileSync("git", ["rev-parse", "HEAD"], {
  encoding: "utf8",
}).trim();
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
  const temporary = high.find(([id]) => id === TEMPORARY_ADVISORY.id);
  const temporaryCheck = temporary
    ? qualifyAuditFinding({
        id: temporary[0],
        advisory: temporary[1],
        context: {
          repoRoot: process.cwd(),
          evidence: qualificationEvidence,
          expectedCommit,
        },
        now: new Date().toISOString(),
      })
    : { qualified: false, reason: "advisory not present" };
  const unexpectedHigh = high.filter(
    ([id]) =>
      !scope.acceptedHigh.has(id) &&
      !(id === TEMPORARY_ADVISORY.id && temporaryCheck.qualified),
  );
  const resolvedHigh = [...scope.acceptedHigh].filter(
    (id) => !high.some(([current]) => current === id),
  );
  const counts = report.metadata?.vulnerabilities ?? {};
  console.log(
    `${scope.name}: ${critical.length} critical, ${high.length} high, ${counts.moderate ?? 0} moderate, ` +
      `${counts.low ?? 0} low.`,
  );
  if (temporary) {
    if (temporaryCheck.qualified) {
      console.log(
        `${scope.name}: temporary build-only qualification passed for ${TEMPORARY_ADVISORY.ghsa} through ${TEMPORARY_ADVISORY.expiresAt}.`,
      );
    } else {
      console.error(
        `${scope.name}: ${TEMPORARY_ADVISORY.id} qualification rejected: ${temporaryCheck.reason}.`,
      );
    }
  }
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
