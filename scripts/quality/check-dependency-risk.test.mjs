import assert from "node:assert/strict";
import test from "node:test";
import { classifyAuditResult } from "./dependency-audit-report.mjs";

const accepted = new Set(["1101846"]);

function report(advisories = {}) {
  const vulnerabilities = {
    info: 0,
    low: 0,
    moderate: 0,
    high: 0,
    critical: 0,
  };
  for (const advisory of Object.values(advisories))
    vulnerabilities[advisory.severity]++;

  return {
    actions: [],
    advisories,
    muted: [],
    metadata: {
      vulnerabilities,
      dependencies: 12,
      devDependencies: 0,
      optionalDependencies: 0,
      totalDependencies: 12,
    },
  };
}

function result(value, status = 0) {
  return { status, signal: null, stdout: JSON.stringify(value), stderr: "" };
}

const acceptedPathToRegexp = {
  module_name: "path-to-regexp",
  severity: "high",
};

test("valid pnpm status 1 with the accepted #104 high finding remains valid", () => {
  const assessment = classifyAuditResult(
    result(report({ 1101846: acceptedPathToRegexp }), 1),
    accepted,
  );
  assert.equal(assessment.valid, true);
  assert.equal(assessment.passed, true);
  assert.equal(assessment.high.length, 1);
});

test("registry error JSON is rejected even when the process exits 0", () => {
  const assessment = classifyAuditResult(
    result({ error: { code: "ERR_PNPM_AUDIT_FETCH" } }),
    accepted,
  );
  assert.equal(assessment.valid, false);
  assert.match(assessment.reason, /error payload/);
});

test("invalid JSON and non-object report payloads are rejected", () => {
  for (const stdout of ["not-json", "null", "[]", "{}"])
    assert.equal(
      classifyAuditResult(
        { status: 0, signal: null, stdout, stderr: "" },
        accepted,
      ).valid,
      false,
    );
});

test("spawn failures, signals, and unexpected exit statuses are rejected", () => {
  const valid = result(report());
  for (const input of [
    { ...valid, error: new Error("registry unavailable") },
    { ...valid, signal: "SIGTERM" },
    { ...valid, status: 2 },
    { ...valid, status: null, signal: null },
  ]) {
    assert.equal(classifyAuditResult(input, accepted).valid, false);
  }
});

test("missing or invalid advisory and metadata structures fail closed", () => {
  const valid = report();
  const cases = [
    { ...valid, advisories: undefined },
    { ...valid, advisories: [] },
    { ...valid, metadata: undefined },
    { ...valid, metadata: { ...valid.metadata, vulnerabilities: { high: 0 } } },
    {
      ...valid,
      metadata: {
        ...valid.metadata,
        vulnerabilities: { ...valid.metadata.vulnerabilities, high: "0" },
      },
    },
    {
      ...valid,
      advisories: {
        bad: { module_name: "broken-package", severity: "urgent" },
      },
    },
  ];
  for (const invalidReport of cases)
    assert.equal(
      classifyAuditResult(result(invalidReport), accepted).valid,
      false,
    );

  const inconsistent = report({
    9999991: { module_name: "new-high", severity: "high" },
  });
  inconsistent.metadata.vulnerabilities.high = 0;
  assert.equal(
    classifyAuditResult(result(inconsistent), accepted).valid,
    false,
  );
});

test("new high and any critical advisory fail while accepted #104 is retained", () => {
  const withNewHigh = classifyAuditResult(
    result(
      report({
        1101846: acceptedPathToRegexp,
        9999991: { module_name: "new-high", severity: "high" },
      }),
      1,
    ),
    accepted,
  );
  assert.equal(withNewHigh.valid, true);
  assert.equal(withNewHigh.passed, false);
  assert.deepEqual(
    withNewHigh.unexpectedHigh.map(([id]) => id),
    ["9999991"],
  );

  const withCritical = classifyAuditResult(
    result(
      report({
        1101846: acceptedPathToRegexp,
        9999992: { module_name: "critical-package", severity: "critical" },
      }),
      1,
    ),
    accepted,
  );
  assert.equal(withCritical.passed, false);
  assert.equal(withCritical.critical.length, 1);
});

test("a resolved accepted high allowance is surfaced for removal", () => {
  const assessment = classifyAuditResult(result(report()), accepted);
  assert.equal(assessment.valid, true);
  assert.equal(assessment.passed, false);
  assert.deepEqual(assessment.resolvedHigh, ["1101846"]);
});

test("status 1 without vulnerability data is not treated as a clean audit", () => {
  const assessment = classifyAuditResult(result(report(), 1), accepted);
  assert.equal(assessment.valid, false);
  assert.match(assessment.reason, /without vulnerability data/);
});
