const SEVERITIES = ["info", "low", "moderate", "high", "critical"];
const DEPENDENCY_COUNTS = [
  "dependencies",
  "devDependencies",
  "optionalDependencies",
  "totalDependencies",
];

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function invalid(reason) {
  return {
    valid: false,
    passed: false,
    reason,
  };
}

export function classifyAuditResult(result, acceptedHigh = new Set()) {
  if (!isRecord(result)) return invalid("audit process result is missing");
  if (result.error)
    return invalid(`audit process failed to start: ${result.error.message}`);
  if (result.signal)
    return invalid(`audit process was terminated by ${result.signal}`);
  if (result.status !== 0 && result.status !== 1)
    return invalid(
      `audit process exited unexpectedly with status ${result.status}`,
    );
  if (typeof result.stdout !== "string")
    return invalid("audit process returned no text output");

  let report;
  try {
    report = JSON.parse(result.stdout);
  } catch {
    return invalid("pnpm audit did not return valid JSON");
  }
  if (!isRecord(report)) return invalid("pnpm audit report is not an object");
  if (Object.hasOwn(report, "error"))
    return invalid("pnpm audit returned an error payload");
  if (!Array.isArray(report.actions) || !Array.isArray(report.muted))
    return invalid("pnpm audit report is missing actions or muted arrays");
  if (!isRecord(report.advisories))
    return invalid("pnpm audit report is missing its advisories object");
  if (!isRecord(report.metadata) || !isRecord(report.metadata.vulnerabilities))
    return invalid("pnpm audit report is missing vulnerability metadata");

  const counts = report.metadata.vulnerabilities;
  for (const severity of SEVERITIES) {
    if (!Number.isSafeInteger(counts[severity]) || counts[severity] < 0)
      return invalid(`pnpm audit vulnerability count '${severity}' is invalid`);
  }
  for (const key of DEPENDENCY_COUNTS) {
    if (!Number.isSafeInteger(report.metadata[key]) || report.metadata[key] < 0)
      return invalid(`pnpm audit dependency count '${key}' is invalid`);
  }

  const advisories = Object.entries(report.advisories);
  const advisoryCounts = Object.fromEntries(
    SEVERITIES.map((severity) => [severity, 0]),
  );
  for (const [id, advisory] of advisories) {
    if (!id || !isRecord(advisory))
      return invalid("pnpm audit contains an invalid advisory entry");
    if (!SEVERITIES.includes(advisory.severity))
      return invalid(`pnpm audit advisory '${id}' has an invalid severity`);
    if (
      typeof advisory.module_name !== "string" ||
      !advisory.module_name.trim()
    )
      return invalid(`pnpm audit advisory '${id}' has no package name`);
    advisoryCounts[advisory.severity]++;
  }

  for (const severity of SEVERITIES) {
    if (counts[severity] > 0 !== advisoryCounts[severity] > 0)
      return invalid(
        `pnpm audit ${severity} metadata does not match its advisories`,
      );
  }
  if (
    result.status === 1 &&
    SEVERITIES.every((severity) => counts[severity] === 0)
  )
    return invalid("pnpm audit exited 1 without vulnerability data");

  const critical = advisories.filter(
    ([, advisory]) => advisory.severity === "critical",
  );
  const high = advisories.filter(
    ([, advisory]) => advisory.severity === "high",
  );
  const unexpectedHigh = high.filter(([id]) => !acceptedHigh.has(id));
  const resolvedHigh = [...acceptedHigh].filter(
    (id) => !high.some(([current]) => current === id),
  );

  return {
    valid: true,
    passed:
      critical.length === 0 &&
      unexpectedHigh.length === 0 &&
      resolvedHigh.length === 0,
    counts,
    critical,
    high,
    unexpectedHigh,
    resolvedHigh,
  };
}
