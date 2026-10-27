import attemptPayload from "../../../docs/attempts.json";
type Attempt = (typeof attemptPayload.attempts)[number];

export const attempts = attemptPayload.attempts as Attempt[];
export const statusOrder = [
  "worked",
  "worked-with-caveat",
  "failed",
  "regressed",
  "inconclusive",
  "superseded",
  "rejected",
  "blocked",
] as const;
export const labels: Record<string, string> = {
  worked: "worked",
  "worked-with-caveat": "worked · caveat",
  failed: "failed",
  regressed: "regressed",
  inconclusive: "inconclusive",
  superseded: "superseded",
  rejected: "rejected",
  blocked: "blocked",
};
export const confidenceLabels: Record<string, string> = {
  exact: "direct evidence",
  inferred: "inferred cause",
  "missing-evidence": "evidence gap",
  "not-applicable": "no failure claim",
};
export const counts = Object.fromEntries(
  statusOrder.map((status) => [
    status,
    attempts.filter((attempt) => attempt.status === status).length,
  ]),
);
export const families = [
  ...new Set(attempts.map((attempt) => attempt.family)),
].sort();
export const exact = attempts.filter(
  (attempt) => attempt.failure_reason_confidence === "exact",
).length;
