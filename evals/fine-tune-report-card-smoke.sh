#!/usr/bin/env bash
# No-GPU smoke for the Fine-Tune Report Card contract.
#
# Proves, without loading a model, training, evaluating, or touching the network:
#   1. the Python unit suite passes (schema, states, decisions, rendering);
#   2. every fixture outcome class compiles, and every `bad-` case fails closed
#      without writing a publishable artifact;
#   3. the emitted JSON decodes and validates through the typed Swift
#      contract in TinyGPTIO — so the Python and Swift schemas cannot drift;
#   4. the committed public cohort has not drifted from a fresh compile;
#   5. the published cards pass the publication gate and their static pages
#      pass the accessibility/contract checks.
#
# Swift is compiled with bare `swiftc` over the pure IO sources (no MLX, no
# package resolve, no network), the same way factory-run-assemble-smoke.sh does.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

BUILD="$ROOT/scripts/build_fine_tune_report_card.py"
CHECK="$ROOT/scripts/check_fine_tune_report_card.py"
FIXTURES="$ROOT/tests/report_card_fixtures.py"

echo "== [1/5] python unit suite =="
python3 "$ROOT/tests/test_fine_tune_report_card.py" | tail -1

echo
echo "== [2/5] every outcome class compiles; bad cases fail closed =="
for case in $(python3 "$FIXTURES" --list); do
  src="$WORK/src/$case"
  out="$WORK/out/$case"
  python3 "$FIXTURES" "$case" "$src" >/dev/null

  # `historical` is a specialist package; everything else is a run folder.
  if [ "$case" = "historical" ]; then
    args=(--specialist "$src")
  else
    args=(--run "$src")
  fi
  # Only the honest-blockers case may use the report-only escape hatch.
  [ "$case" = "report-only" ] && args+=(--allow-report-only)

  if [[ "$case" == bad-* ]]; then
    if python3 "$BUILD" "${args[@]}" --out "$out" >/dev/null 2>"$WORK/err"; then
      fail "$case: expected the publication gate to reject this card"
    fi
    grep -q "^FAIL" "$WORK/err" || fail "$case: rejection printed no diagnostic"
    [ -e "$out/report-card.json" ] && fail "$case: wrote an artifact despite failing"
    printf '  %-30s rejected: %s\n' "$case" "$(sed -n '2s/^ *- //p' "$WORK/err")"
  else
    python3 "$BUILD" "${args[@]}" --out "$out" >/dev/null \
      || fail "$case: compile failed"
    python3 "$CHECK" --allow-report-only "$out/report-card.json" >/dev/null \
      || fail "$case: published card failed validation"
    label="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['decision']['outcome_label'])" "$out/report-card.json")"
    printf '  %-30s ok (%s)\n' "$case" "$label"
  fi
done

echo
echo "== [3/5] emitted JSON validates through the typed Swift contract =="
mkdir -p "$WORK/swift"
cat >"$WORK/swift/main.swift" <<'SWIFT'
import Foundation

func assertTrue(_ condition: @autoclosure () -> Bool, _ msg: String) {
    if !condition() {
        fputs("SMOKE FAIL: \(msg)\n", stderr)
        exit(1)
    }
}

// argv: <verified-ship.json> <routed-ship.json> <report-only.json> <historical.json>
let paths = CommandLine.arguments.dropFirst().map { URL(fileURLWithPath: $0) }
assertTrue(paths.count == 4, "expected four report cards")

let verified = try FineTuneReportCard.validate(at: paths[0])
assertTrue(verified.decision.decision == .ship, "verified: decision is ship")
assertTrue(verified.decision.outcomeLabel == .shippedSpecialist, "verified: label")
assertTrue(verified.decision.verified, "verified: card claims a verified ship")
assertTrue(verified.decision.verificationBlockers.isEmpty, "verified: no blockers")
assertTrue(verified.primaryGate != nil, "verified: primary gate present")
assertTrue(verified.primaryGate?.baseline.state == .measured, "verified: measured baseline")
assertTrue(verified.evalValidity.leakage.value?.text == "no-overlap", "verified: leakage")
assertTrue(!verified.evalValidity.overlapDetected, "verified: no overlap")
assertTrue(verified.performance.trainingCostUsd.hasValue, "verified: cost recorded")

// A routed ship must disclose its envelope and keep the failing gate visible.
let routed = try FineTuneReportCard.validate(at: paths[1])
assertTrue(routed.decision.outcomeLabel == .routedShip, "routed: label")
assertTrue(routed.subject.artifact.routingConstraint.hasValue, "routed: constraint disclosed")
assertTrue(routed.regressedGates.count == 1, "routed: failing gate is visible")

// A report-only card is strict by default and never reads as shipped.
let reportOnly = try FineTuneReportCard.read(from: paths[2])
assertTrue(reportOnly.decision.outcomeLabel == .reportOnly, "report-only: label")
assertTrue(!reportOnly.decision.outcomeLabel.claimsShip, "report-only: never claims a ship")
assertTrue(!reportOnly.subject.artifact.shipped, "report-only: not marked shipped")
do {
    try reportOnly.validate()
    fputs("SMOKE FAIL: report-only card with blockers passed strict validation\n", stderr)
    exit(1)
} catch {}
try reportOnly.validate(allowReportOnly: true)

// Historical imports can never present a verified ship.
let historical = try FineTuneReportCard.read(from: paths[3])
assertTrue(!historical.decision.verified, "historical: not verified")
assertTrue(!historical.decision.verificationBlockers.isEmpty, "historical: blockers listed")
assertTrue(historical.primaryGate?.baseline.state == .historical, "historical: state")
assertTrue(historical.primaryGate?.baseline.isWeak == true, "historical: weak provenance")
assertTrue(historical.primaryGate?.baseline.note?.isEmpty == false, "historical: caveat note")

// Field-level rules mirror the Python validator.
do {
    try FineTuneReportCard.Field(state: .measured, value: .number(1)).validate("f")
    fputs("SMOKE FAIL: measured field without a source was accepted\n", stderr)
    exit(1)
} catch {}
do {
    try FineTuneReportCard.Field(state: .missing, value: .number(0), note: "n").validate("f")
    fputs("SMOKE FAIL: missing field carrying a value was accepted\n", stderr)
    exit(1)
} catch {}
do {
    try FineTuneReportCard.Field(state: .missing).validate("f")
    fputs("SMOKE FAIL: missing field without a note was accepted\n", stderr)
    exit(1)
} catch {}

// Cross-contract: the report card reuses FactoryRun's decision vocabulary.
assertTrue(FactoryRun.Decision.allCases.count == 6, "decision vocabulary size")
assertTrue(FineTuneReportCard.schemaVersion == verified.schemaVersion, "schema version")

print("SMOKE OK: typed Swift contract validates the compiler's real output")
SWIFT

swiftc \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRun.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift" \
  "$WORK/swift/main.swift" \
  -o "$WORK/report-card-smoke"

"$WORK/report-card-smoke" \
  "$WORK/out/ship-verified/report-card.json" \
  "$WORK/out/routed-ship/report-card.json" \
  "$WORK/out/report-only/report-card.json" \
  "$WORK/out/historical/report-card.json"

echo
echo "== [4/5] committed public cohort has not drifted =="
python3 "$ROOT/scripts/publish_report_cards.py" --check

echo
echo "== [5/5] published cards pass the publication gate =="
python3 "$CHECK" --allow-report-only "$ROOT"/browser/public/report-cards/*.json

echo
echo "fine-tune-report-card-smoke: all checks passed"
