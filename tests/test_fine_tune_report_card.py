#!/usr/bin/env python3
"""Unit tests for the Fine-Tune Report Card contract.

Covers the `add-fine-tune-report-card` spec requirements:

- canonical factory-run ingestion, and incomplete runs marking fields missing
  without inferring a measurement;
- honest measurement states (absent performance is `missing`, never zero;
  legacy imports are `historical` with a visible caveat);
- before/after evaluation, including target-improves-but-breadth-regresses;
- eval validity and leakage disclosure;
- decision semantics for ship / routed ship / reject;
- stable machine and public outputs (byte-identical rebuilds);
- the publication gate failing closed and exiting non-zero;
- dogfood coverage over every supported outcome class.

Run: ``python3 tests/test_fine_tune_report_card.py``
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rc = _load_module("fine_tune_report_card", ROOT / "scripts/factory/fine_tune_report_card.py")
build = _load_module("build_fine_tune_report_card", ROOT / "scripts/factory/build_fine_tune_report_card.py")
check = _load_module("check_fine_tune_report_card", ROOT / "scripts/factory/check_fine_tune_report_card.py")
fixtures = _load_module("report_card_fixtures", ROOT / "tests/report_card_fixtures.py")

FAILURES: list[str] = []
PASSED = 0


def check_that(condition: bool, message: str) -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILURES.append(message)


def section(name: str) -> None:
    print(f"\n== {name}")


class Workspace:
    """Temp directory that builds fixture cases on demand."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="report-card-tests-"))
        self._cache: dict[str, dict] = {}

    def source(self, case: str) -> Path:
        dest = self.root / "src" / case
        if not dest.exists():
            fixtures.build(case, dest)
        return dest

    def card(self, case: str) -> dict:
        """Compile fixture `case` and return the payload (never written to disk)."""
        if case not in self._cache:
            src = self.source(case)
            if case in fixtures.SPECIALIST_CASES:
                self._cache[case] = build.compile_from_specialist(src)
            else:
                self._cache[case] = build.compile_from_run(src)
        return json.loads(json.dumps(self._cache[case]))

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, cwd=ROOT
    )


ws = Workspace()

# ---------------------------------------------------------------------------
# Requirement: honest measurement states
# ---------------------------------------------------------------------------

section("measurement states")

for state in rc.VALUED_STATES:
    errors: list[str] = []
    rc.validate_field({"state": state, "value": None, "sources": ["x"]}, "f", errors)
    check_that(errors, f"state `{state}` with a null value must be rejected")

for state in rc.UNVALUED_STATES:
    errors = []
    rc.validate_field({"state": state, "value": 0, "sources": [], "note": "n"}, "f", errors)
    check_that(errors, f"state `{state}` carrying a value must be rejected")
    errors = []
    rc.validate_field({"state": state, "value": None, "sources": []}, "f", errors)
    check_that(errors, f"state `{state}` without a note must be rejected")

errors = []
rc.validate_field({"state": "measured", "value": 1, "sources": []}, "f", errors)
check_that(errors, "a measured value with no source must be rejected")

errors = []
rc.validate_field({"state": "historical", "value": 1, "sources": ["s"]}, "f", errors)
check_that(errors, "a historical value with no caveat note must be rejected")

errors = []
rc.validate_field(
    {"state": "derived", "value": 1, "sources": ["s"], "derived_from": []}, "f", errors
)
check_that(errors, "a derived value with no derived_from must be rejected")

errors = []
rc.validate_field({"state": "invented", "value": 1, "sources": ["s"]}, "f", errors)
check_that(errors, "an unknown measurement state must be rejected")

# A delta is never zero-filled when an input is absent: "no change measured"
# and "change not measurable" are different claims.
absent = rc.missing("no value", ["a"])
present = rc.measured(0.5, ["b"])
check_that(
    rc.delta_field(absent, present, "a", "b")["state"] == "missing",
    "delta with an absent baseline must be missing, not 0",
)
check_that(
    rc.delta_field(present, absent, "a", "b")["value"] is None,
    "delta with an absent candidate must carry no value",
)
d = rc.delta_field(rc.measured(0.2, ["a"]), rc.measured(0.7, ["b"]), "a", "b")
check_that(d["state"] == "derived" and abs(d["value"] - 0.5) < 1e-9, "delta must be derived")
weak = rc.delta_field(
    rc.historical(0.2, ["a"], note="legacy"), rc.measured(0.7, ["b"]), "a", "b"
)
check_that(
    "provenance" in (weak.get("note") or ""),
    "a delta derived from a weak input must disclose the inherited provenance",
)

# ---------------------------------------------------------------------------
# Requirement: canonical factory-run ingestion
# ---------------------------------------------------------------------------

section("factory-run ingestion")

card = ws.card("ship-verified")
check_that(card["compiled_from"]["source_kind"] == "factory-run", "source kind is recorded")
check_that(
    card["compiled_from"]["compiler"] == rc.COMPILER,
    "the compiler records its own identity",
)
primary = rc.primary_gate(card)
check_that(primary is not None, "a primary gate is compiled from the run config")
check_that(
    primary["baseline"]["sources"] == ["eval-baseline.json#score"],
    "every reported field records its source file identity",
)
check_that(
    bool(card["compiled_from"]["dataset_hashes"]),
    "dataset hashes are carried from provenance.json",
)
check_that(
    all(len(h["sha256"]) == 64 for h in card["compiled_from"]["dataset_hashes"]),
    "dataset hashes are sha256 digests",
)

# Incomplete run: a removed fragment marks fields missing without inferring.
incomplete_src = ws.root / "src" / "incomplete"
shutil.copytree(ws.source("ship-verified"), incomplete_src, dirs_exist_ok=True)
(incomplete_src / "slice-metrics.json").unlink()
(incomplete_src / "cost.json").unlink()
incomplete = build.compile_from_run(incomplete_src)
check_that(incomplete["slices"] == [], "a missing slice fragment yields no slices")
check_that(
    incomplete["performance"]["training_cost_usd"]["state"] == "missing",
    "a missing cost fragment leaves cost missing",
)
check_that(
    incomplete["performance"]["training_cost_usd"]["value"] is None,
    "a missing cost is never inferred as a number",
)
check_that(
    rc.primary_gate(incomplete)["sample_size"]["state"] == "missing",
    "sample size is missing when no slice can supply it",
)

# ---------------------------------------------------------------------------
# Requirement: performance absent -> missing, never zero
# ---------------------------------------------------------------------------

section("performance evidence")

report_only = ws.card("report-only")
for key in ("latency_ms", "peak_rss_mb", "tokens_per_second"):
    field = report_only["performance"][key]
    check_that(field["state"] == "missing", f"absent {key} is marked missing")
    check_that(field["value"] is None, f"absent {key} renders no number")
    check_that(bool(field.get("note")), f"absent {key} explains itself")

verified = ws.card("ship-verified")
check_that(
    verified["performance"]["training_cost_usd"]["state"] == "measured"
    and verified["performance"]["training_cost_usd"]["value"] == 0,
    "a genuinely recorded zero cost stays measured",
)

# ---------------------------------------------------------------------------
# Requirement: historical import carries a visible caveat
# ---------------------------------------------------------------------------

section("historical evidence")

hist = ws.card("historical")
hist_primary = rc.primary_gate(hist)
check_that(hist["compiled_from"]["source_kind"] == "specialist-package", "specialist adapter used")
check_that(hist_primary["baseline"]["state"] == "historical", "legacy scores are historical")
check_that(
    "current run provenance" in hist_primary["baseline"]["note"],
    "a historical value states why its provenance is weaker",
)
check_that(
    rc.is_weak(hist_primary["baseline"]),
    "historical counts as weaker than a measurement",
)
hist_html = rc.render_html(hist)
check_that('data-state="historical"' in hist_html, "the public page labels historical values")
check_that(
    hist_primary["baseline"]["note"] in hist_html
    or hist_primary["baseline"]["note"].replace("&", "&amp;") in hist_html,
    "the historical caveat is visible in the public output",
)

# ---------------------------------------------------------------------------
# Requirement: before-and-after evaluation
# ---------------------------------------------------------------------------

section("before and after")

routed = ws.card("routed-ship")
gates = {g["name"]: g for g in routed["gates"]}
depth, breadth = gates["fixture-gate"], gates["fixture-breadth"]
check_that(depth["passed"]["value"] is True, "the primary target passes")
check_that(breadth["passed"]["value"] is False, "the regression gate fails")
check_that(
    depth["role"] == "primary" and breadth["role"] == "regression",
    "target and regression gates are reported independently",
)
check_that(
    [g["name"] for g in rc.failing_gates(routed, ("regression", "breadth"))] == ["fixture-breadth"],
    "a failing regression gate is detectable",
)
for key in ("baseline", "candidate", "delta", "threshold", "passed", "sample_size"):
    check_that(key in depth, f"the primary gate reports {key}")
check_that(depth["eval_identity"]["suite"], "the gate records its eval identity")
routed_html = rc.render_html(routed)
check_that(
    "does not present an unconditional win" in routed_html,
    "the public page refuses to present a regressing candidate as an outright win",
)

# Slices: per-slice before/after, and a candidate-only slice stays honest.
sql_slices = {s["name"]: s for s in ws.card("ship-verified")["slices"]}
check_that("fixture_gate_rows" in sql_slices, "slice metrics are compiled")
check_that(
    sql_slices["fixture_gate_rows"]["sample_size"]["value"] == 20,
    "each slice reports its sample size",
)
check_that(
    sql_slices["fixture_hard_slice"]["baseline"]["state"] == "missing"
    and sql_slices["fixture_hard_slice"]["delta"]["state"] == "missing",
    "a candidate-only slice does not fabricate a baseline or a delta",
)

# A hand-typed delta that contradicts the measurements is rejected.
tampered = ws.card("ship-verified")
rc.primary_gate(tampered)["delta"]["value"] = 99.0
check_that(
    any("does not equal candidate" in e for e in rc.validate(tampered)),
    "a delta inconsistent with its inputs is rejected",
)

# ---------------------------------------------------------------------------
# Requirement: eval validity and leakage disclosure
# ---------------------------------------------------------------------------

section("eval validity and leakage")

check_that(
    verified["eval_validity"]["frontier_ceiling"]["state"] == "measured",
    "a recorded frontier ceiling is measured",
)
check_that(
    verified["eval_validity"]["leakage"]["value"] == "no-overlap",
    "a passing overlap check is recorded",
)

unverified = ws.card("retry")
no_frontier = ws.root / "src" / "no-frontier"
shutil.copytree(ws.source("retry"), no_frontier, dirs_exist_ok=True)
validity = json.loads((no_frontier / "eval-validity.json").read_text(encoding="utf-8"))
del validity["frontier"]
(no_frontier / "eval-validity.json").write_text(json.dumps(validity), encoding="utf-8")
without = build.compile_from_run(no_frontier)
check_that(
    without["eval_validity"]["frontier_ceiling"]["state"] == "missing",
    "an unvalidated benchmark is identified as unverified",
)
check_that(
    any("frontier-ceiling" in b for b in without["decision"]["verification_blockers"]),
    "a missing frontier ceiling blocks a verified label",
)
check_that(
    any(
        "frontier-ceiling" in lim
        for lim in without["eval_validity"]["known_limitations"]
    ),
    "the missing frontier ceiling is listed as a known limitation",
)

# A frontier model that cannot ace the benchmark is a broken ruler.
broken_ruler = ws.card("ship-verified")
broken_ruler["gates"][0]["frontier_ceiling"]["value"] = 0.12
broken_ruler = rc.finalize(broken_ruler)
check_that(
    not broken_ruler["decision"]["verified"]
    and any(
        "frontier-ceiling gate" in b
        for b in broken_ruler["decision"]["verification_blockers"]
    ),
    "a benchmark frontier cannot ace fails the frontier-ceiling gate",
)

# Leakage: publication is blocked, but the measurements are not hidden.
leaky = build.compile_from_run(ws.source("bad-leakage"))
leak_errors = rc.validate(leaky)
check_that(
    any("overlap-detected" in e for e in leak_errors),
    "detected train/eval overlap blocks publication",
)
check_that(
    any("held-out prompts appear in train" in (e or "") for e in leak_errors),
    "the leakage failure names what overlapped",
)
check_that(
    rc.primary_gate(leaky)["candidate"]["value"] == 0.99,
    "a leakage failure does not hide the candidate measurements",
)

# ---------------------------------------------------------------------------
# Requirement: decision semantics
# ---------------------------------------------------------------------------

section("decision semantics")

check_that(verified["decision"]["outcome_label"] == "shipped-specialist", "clean ship label")
check_that(routed["decision"]["outcome_label"] == "routed-ship", "routed ship label")
check_that(report_only["decision"]["outcome_label"] == "report-only", "report-only label")
rejected = ws.card("reject")
check_that(rejected["decision"]["outcome_label"] == "rejected", "reject label")
check_that(
    rejected["decision"]["failure_reason"] and rejected["decision"]["lesson"],
    "a reject keeps its failure reason and lesson",
)
check_that(
    rc.primary_gate(rejected)["candidate"]["state"] == "measured",
    "a reject retains the measurements that informed it",
)
rejected_html = rc.render_html(rejected)
check_that(
    rejected["decision"]["reason"] in rejected_html,
    "a reject prominently shows why the candidate did not ship",
)

for decision in rc.DECISIONS:
    if decision == "ship":
        continue
    check_that(
        not rc.outcome_label(decision, rc.missing("none", ["x"])) in rc.SHIP_LABELS,
        f"decision `{decision}` can never produce a ship label",
    )

# A non-ship card may not be relabeled as shipped.
mislabeled = ws.card("report-only")
mislabeled["decision"]["outcome_label"] = "shipped-specialist"
check_that(
    any("claims a ship" in e for e in rc.validate(mislabeled, allow_report_only=True)),
    "a report-only artifact cannot be labeled as a shipped specialist",
)

# Routing constraints sit beside the ship decision.
check_that(
    rc.has_value(routed["subject"]["artifact"]["routing_constraint"]),
    "a routed ship records its task envelope",
)
check_that(
    "not a general replacement" in routed_html,
    "a routed ship is not described as a general replacement",
)

# ---------------------------------------------------------------------------
# Requirement: verification honesty
# ---------------------------------------------------------------------------

section("verification status")

check_that(verified["decision"]["verified"] is True, "a complete ship chain verifies")
check_that(
    verified["decision"]["verification_blockers"] == [],
    "a verified ship lists no blockers",
)
check_that(hist["decision"]["verified"] is False, "a historical import never verifies")
check_that(
    any("historical" in b for b in hist["decision"]["verification_blockers"]),
    "the historical provenance is named as a verification blocker",
)
contradiction = ws.card("report-only")
contradiction["decision"]["verified"] = True
check_that(
    any("contradicts" in e for e in rc.validate(contradiction, allow_report_only=True)),
    "verified=true with open blockers is rejected",
)

# ---------------------------------------------------------------------------
# Requirement: publication gate fails closed
# ---------------------------------------------------------------------------

section("publication gate")

for case in fixtures.GOOD_CASES:
    payload = ws.card(case)
    allow = case in fixtures.NEEDS_REPORT_ONLY
    errors = rc.validate(payload, allow_report_only=allow)
    check_that(not errors, f"fixture `{case}` must validate (got {errors[:2]})")

for case in fixtures.BAD_CASES:
    payload = build.compile_from_run(ws.source(case))
    check_that(
        bool(rc.validate(payload, allow_report_only=True)),
        f"fixture `{case}` must fail validation even in report-only mode",
    )

incomplete_ship = build.compile_from_run(ws.source("bad-missing-evidence-ship"))
check_that(
    any("fails closed" in e for e in rc.validate(incomplete_ship)),
    "an incomplete ship claim fails closed",
)
undisclosed = build.compile_from_run(ws.source("bad-undisclosed-routed-ship"))
check_that(
    any("routing_constraint" in e for e in rc.validate(undisclosed)),
    "a regressing ship without a routing constraint is rejected",
)

# A report-only candidate with complete evidence publishes without being
# labeled shipped.
check_that(
    not rc.validate(report_only, allow_report_only=True),
    "a report-only candidate with an honest decision can publish",
)
check_that(
    rc.validate(report_only) and report_only["subject"]["artifact"]["shipped"] is False,
    "report-only publication must be explicit and is never marked shipped",
)

# Private payload field names can never reach the public surface.
leaked = ws.card("ship-verified")
leaked["subject"]["eval_prompt"] = "PRIVATE PROMPT"
check_that(
    any("denylisted" in e for e in rc.validate(leaked)),
    "a private payload field name is rejected",
)

# ---------------------------------------------------------------------------
# Requirement: stable machine and public outputs
# ---------------------------------------------------------------------------

section("determinism and rendering")

for case in ("ship-verified", "routed-ship", "historical"):
    first = ws.card(case)
    src = ws.source(case)
    second = (
        build.compile_from_specialist(src)
        if case in fixtures.SPECIALIST_CASES
        else build.compile_from_run(src)
    )
    check_that(rc.dumps(first) == rc.dumps(second), f"`{case}` JSON is byte-stable")
    check_that(
        rc.render_html(first) == rc.render_html(second), f"`{case}` HTML is byte-stable"
    )

page = rc.render_html(verified)
check_that("http://" not in page.replace("http://www.w3.org", ""), "no plaintext external asset")
check_that(
    "<script" not in page and "<link" not in page,
    "the public report is self-contained: no script or external stylesheet",
)
published_url = "https://posttrainllm.com/report-cards/example.html"
published_page = rc.render_html(verified, canonical_url=published_url)
check_that(
    f'<link rel="canonical" href="{published_url}">' in published_page,
    "a published report identifies its exact canonical URL",
)
check_that(
    '<meta property="og:type" content="article">' in published_page
    and '<script type="application/ld+json">' in published_page,
    "a published report includes social and structured discovery metadata",
)
published_description = published_page.split('<meta name="description" content="', 1)[1].split('">', 1)[0]
check_that(
    70 <= len(published_description) <= 160,
    "a published report keeps its search description within the supported range",
)
check_that(
    verified["decision"]["reason"] in published_page,
    "discovery metadata does not replace the canonical decision evidence",
)
html_errors = check.check_html(page, verified)
check_that(not html_errors, f"the rendered page passes accessibility checks: {html_errors[:3]}")
published_html_errors = check.check_html(published_page, verified)
check_that(
    not published_html_errors,
    f"the published page metadata preserves structural checks: {published_html_errors[:3]}",
)

for case in fixtures.GOOD_CASES + fixtures.SPECIALIST_CASES:
    payload = ws.card(case)
    errs = check.check_html(rc.render_html(payload), payload)
    check_that(not errs, f"`{case}` page passes structural checks: {errs[:2]}")

# The page must not read better than the payload. `historical` is unverified,
# so a page claiming otherwise has to fail the contract check.
sneaky = ws.card("historical")
check_that(sneaky["decision"]["verified"] is False, "the sneaky-page fixture is unverified")
bad_page = rc.render_html(sneaky).replace('data-verified="false"', 'data-verified="true"')
check_that(
    bool(check.check_html(bad_page, sneaky)),
    "a page that hides its unverified status fails the contract check",
)

# HTML escaping: source text cannot inject markup.
injected = ws.card("report-only")
injected["decision"]["reason"] = "<script>alert('x')</script>"
check_that(
    "<script>alert" not in rc.render_html(injected),
    "source text is escaped, not injected as markup",
)

# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------

section("CLI")

out_dir = ws.root / "cli-out"
proc = run_cli(
    [
        "scripts/factory/build_fine_tune_report_card.py",
        "--run",
        str(ws.source("ship-verified")),
        "--out",
        str(out_dir),
    ]
)
check_that(proc.returncode == 0, f"build CLI succeeds: {proc.stderr[-400:]}")
check_that((out_dir / "report-card.json").is_file(), "build CLI writes the JSON payload")
check_that((out_dir / "report-card.html").is_file(), "build CLI writes the static report")

proc = run_cli(["scripts/factory/check_fine_tune_report_card.py", str(out_dir / "report-card.json")])
check_that(proc.returncode == 0, f"check CLI accepts a valid card: {proc.stderr[-400:]}")

bad_out = ws.root / "cli-bad"
proc = run_cli(
    [
        "scripts/factory/build_fine_tune_report_card.py",
        "--run",
        str(ws.source("bad-leakage")),
        "--out",
        str(bad_out),
    ]
)
check_that(proc.returncode != 0, "build CLI exits non-zero on an invalid card")
check_that(
    not (bad_out / "report-card.json").exists(),
    "no publishable artifact is produced when validation fails",
)
check_that("FAIL" in proc.stderr, "local diagnostic output is preserved on failure")

proc = run_cli(
    [
        "scripts/factory/build_fine_tune_report_card.py",
        "--run",
        str(ws.source("report-only")),
        "--print",
    ]
)
check_that(proc.returncode != 0, "a blocked non-ship card is strict by default")
proc = run_cli(
    [
        "scripts/factory/build_fine_tune_report_card.py",
        "--run",
        str(ws.source("report-only")),
        "--allow-report-only",
        "--print",
    ]
)
check_that(proc.returncode == 0, "--allow-report-only permits an honest blocked card")
check_that(
    json.loads(proc.stdout)["decision"]["outcome_label"] == "report-only",
    "--print emits the payload on stdout",
)

# ---------------------------------------------------------------------------
# Requirement: dogfood coverage over the real committed cohort
# ---------------------------------------------------------------------------

section("dogfood cohort")

PUBLISHED = ROOT / "browser/public/report-cards"
if PUBLISHED.is_dir():
    published = sorted(PUBLISHED.glob("*.json"))
    check_that(bool(published), "at least one report card is published")
    labels = set()
    for path in published:
        payload = json.loads(path.read_text(encoding="utf-8"))
        errs = rc.validate(payload, allow_report_only=True)
        check_that(not errs, f"published `{path.name}` validates: {errs[:2]}")
        page = path.with_suffix(".html")
        check_that(page.is_file(), f"published `{path.name}` has a static report")
        if page.is_file():
            errs = check.check_html(page.read_text(encoding="utf-8"), payload)
            check_that(not errs, f"published `{page.name}` passes checks: {errs[:2]}")
        labels.add(payload["decision"]["outcome_label"])
    check_that(
        {"routed-ship", "report-only"} <= labels,
        f"the published cohort spans shipped and non-shipped outcomes (got {sorted(labels)})",
    )
else:  # pragma: no cover - published cohort is committed alongside this test
    FAILURES.append("browser/public/report-cards is missing")

# ---------------------------------------------------------------------------
# Regressions found by adversarial review. Each of these once produced a
# confidently mislabeled card, which is the exact failure this format exists to
# prevent — so each keeps a test.
# ---------------------------------------------------------------------------

section("review regressions")

# (1) A ship whose PRIMARY gate is recorded as failing was labeled
# `shipped-specialist` and rendered "Fully verified". Recording a failure as
# *measured* is not the same as passing it.
failed_primary_src = ws.root / "src" / "failed-primary"
shutil.copytree(ws.source("ship-verified"), failed_primary_src, dirs_exist_ok=True)
cand = json.loads((failed_primary_src / "eval-candidate.json").read_text(encoding="utf-8"))
cand["passed"], cand["score"] = False, 0.10
(failed_primary_src / "eval-candidate.json").write_text(json.dumps(cand), encoding="utf-8")
failed_primary = build.compile_from_run(failed_primary_src)
check_that(
    failed_primary["decision"]["verified"] is False,
    "a ship whose primary gate failed is not verified",
)
check_that(
    any("missed its own target" in b for b in failed_primary["decision"]["verification_blockers"]),
    "the failed primary gate is named as a verification blocker",
)
check_that(
    any("missed its own target" in e for e in rc.validate(failed_primary)),
    "a ship whose primary gate failed cannot publish",
)

# (2) Gate -> slice mapping is explicit only. Name-token containment used to
# pick a coincidental short slice name over the correct specific one, turning a
# breadth regression into a reported pass.
mismap_src = ws.root / "src" / "mismap"
shutil.copytree(ws.source("routed-ship"), mismap_src, dirs_exist_ok=True)
cfg = json.loads((mismap_src / "config.json").read_text(encoding="utf-8"))
cfg["eval"]["regression"] = "fixture-breadth-suite"
del cfg["eval"]["regression_slice"]
(mismap_src / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
mismapped = build.compile_from_run(mismap_src)
reg = [g for g in mismapped["gates"] if g["role"] == "regression"][0]
check_that(
    reg["baseline"]["state"] == "missing" and reg["candidate"]["state"] == "missing",
    "without an explicit regression_slice a gate borrows no before/after pair",
)
check_that(
    reg["passed"]["state"] == "missing",
    "an unmapped regression gate reports no pass/fail rather than a pass",
)
# ...and a wrong pointer is a loud error, not a silent downgrade.
cfg["eval"]["regression_slice"] = "no_such_slice"
(mismap_src / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
try:
    build.compile_from_run(mismap_src)
    check_that(False, "a regression_slice naming a missing slice must raise")
except rc.ReportCardError as exc:
    check_that("not present in slice-metrics.json" in str(exc), "the bad pointer is named")

# (3) `validate` recomputes verified/blockers instead of trusting the payload.
forged = ws.card("historical")
check_that(forged["decision"]["verified"] is False, "the forgery fixture starts unverified")
forged["decision"]["verified"] = True
forged["decision"]["verification_blockers"] = []
check_that(
    any("does not match the evidence" in e for e in rc.validate(forged, allow_report_only=True)),
    "a forged verified=true is rejected by recomputation",
)
tampered_blockers = ws.card("historical")
tampered_blockers["decision"]["verification_blockers"] = ["a made-up blocker"]
check_that(
    any("does not match the evidence" in e for e in rc.validate(tampered_blockers, allow_report_only=True)),
    "a tampered blocker list is rejected by recomputation",
)

# (4) A gate's sample size comes only from the slice config names.
no_pointer_src = ws.root / "src" / "no-pointer"
shutil.copytree(ws.source("ship-verified"), no_pointer_src, dirs_exist_ok=True)
cfg = json.loads((no_pointer_src / "config.json").read_text(encoding="utf-8"))
del cfg["eval"]["primary_slice"]
(no_pointer_src / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
no_pointer = build.compile_from_run(no_pointer_src)
check_that(
    rc.primary_gate(no_pointer)["sample_size"]["state"] == "missing",
    "without primary_slice the gate reports no sample size",
)

# (5) Slice deltas are cross-checked like gate deltas.
bad_slice = ws.card("ship-verified")
target = next(s for s in bad_slice["slices"] if rc.has_value(s["delta"]))
target["delta"]["value"] = 99.0
check_that(
    any("does not equal candidate" in e for e in rc.validate(bad_slice)),
    "a fabricated slice delta is rejected",
)

# (6) A frontier ceiling is per-suite; one global score is not spread across gates.
global_frontier_src = ws.root / "src" / "global-frontier"
shutil.copytree(ws.source("ship-verified"), global_frontier_src, dirs_exist_ok=True)
(global_frontier_src / "eval-validity.json").write_text(
    json.dumps({"frontier": {"model": "fixture-frontier", "score": 1.0}}), encoding="utf-8"
)
global_frontier = build.compile_from_run(global_frontier_src)
check_that(
    all(g["frontier_ceiling"]["state"] == "missing" for g in global_frontier["gates"]),
    "a frontier score with no by_suite entry is not attributed to any gate",
)
check_that(
    global_frontier["decision"]["verified"] is False,
    "an unattributed frontier score cannot verify a ship",
)

# (7) The payload can never carry a value shape the Swift mirror cannot decode.
bad_rows = ws.card("ship-verified")
if bad_rows["compiled_from"]["dataset_hashes"]:
    bad_rows["compiled_from"]["dataset_hashes"][0]["rows"] = "40"
    check_that(
        any("must be an integer" in e for e in rc.validate(bad_rows)),
        "a string row count is rejected (Swift types it as Int?)",
    )
bad_value = ws.card("ship-verified")
bad_value["subject"]["target"] = rc.measured(["a", "list"], ["config.json#target"])
check_that(
    any("must be a number, string, or boolean" in e for e in rc.validate(bad_value)),
    "a list-valued field is rejected (Swift types it as number|string|bool)",
)

# (8) Baseline/candidate score keys match on whole tokens, so a candidate whose
# name merely contains "base" cannot be read as the baseline and invert a delta.
check_that(
    build._score_keys({"suite": "x", "stock_4b": 0.58, "distilled_4b": 1.0}, "x")
    == ("stock_4b", "distilled_4b"),
    "a conventional stock/candidate pair is classified correctly",
)
try:
    build._score_keys({"suite": "x", "model_v1": 0.30, "database_expert": 0.90}, "x")
    check_that(False, "`database_expert` must not be read as a baseline")
except rc.ReportCardError:
    check_that(True, "an unidentifiable score pair fails closed instead of inverting")

# The `/artifacts` inventory must link real published cards. This guard runs
# without node, so a renamed slug is caught even where the site is not built.
ARTIFACTS_TS = ROOT / "browser/src/artifacts.ts"
if ARTIFACTS_TS.is_file():
    import re

    source = ARTIFACTS_TS.read_text(encoding="utf-8")
    linked = set(re.findall(r'reportCard\(\s*"([^"]+)"', source))
    check_that(bool(linked), "the artifact inventory links at least one report card")
    for slug in sorted(linked):
        check_that(
            (PUBLISHED / f"{slug}.html").is_file() and (PUBLISHED / f"{slug}.json").is_file(),
            f"/artifacts links report card `{slug}` but it is not published",
        )
    if PUBLISHED.is_dir():
        for path in sorted(PUBLISHED.glob("*.json")):
            check_that(
                path.stem in linked,
                f"published report card `{path.stem}` is not linked from /artifacts",
            )
        for slug in sorted(linked):
            path = PUBLISHED / f"{slug}.json"
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry = re.search(
                rf'reportCard\(\s*"{re.escape(slug)}",\s*"([^"]+)",\s*(true|false)',
                source,
            )
            check_that(entry is not None, f"`{slug}` report-card link is well formed")
            if entry:
                check_that(
                    entry.group(1) == payload["decision"]["outcome_label"],
                    f"`{slug}` outcome label on /artifacts matches the payload",
                )
                check_that(
                    (entry.group(2) == "true") == payload["decision"]["verified"],
                    f"`{slug}` verified flag on /artifacts matches the payload",
                )

for case in fixtures.ALL_CASES:
    check_that(
        case in fixtures.GOOD_CASES + fixtures.SPECIALIST_CASES + fixtures.BAD_CASES,
        f"fixture `{case}` is classified",
    )
check_that(
    len(fixtures.ALL_CASES) >= 8,
    "every supported outcome class has a fixture",
)

ws.cleanup()

# ---------------------------------------------------------------------------

print()
if FAILURES:
    print(f"FAILED — {len(FAILURES)} problem(s), {PASSED} passed")
    for failure in FAILURES:
        print(f"  - {failure}")
    raise SystemExit(1)
print(f"ok — {PASSED} checks passed")
