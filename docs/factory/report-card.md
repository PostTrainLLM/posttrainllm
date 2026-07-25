# Fine-Tune Report Card

A **report card** is the portable proof that a fine-tune helped, hurt, or is
not yet decidable. It is a *derived* artifact: canonical
[run folders](run-schema.md) and [specialist packages](packaging.md) stay the
source of truth, and the compiler joins them into one versioned payload plus a
static public page.

The point is legibility for someone who has neither this repository nor a GPU.
The published cohort and what it revealed live in
[`report-card-cohort.md`](report-card-cohort.md).

## Why it exists

`report.md` is prose: hard to validate, hard to compare across runs, easy to
read as a win. A report card makes the uncomfortable parts structural —
regressions sit beside the target gate, and an absent measurement is a first
class state rather than a blank cell.

## Build and validate

```bash
# from a canonical run folder
python3 scripts/build_fine_tune_report_card.py --run runs/<id> --out <dir>

# from a committed specialist package (legacy evidence)
python3 scripts/build_fine_tune_report_card.py \
    --specialist specialists/qwen3-4b-rest-fused --out <dir>

# validate a card before it reaches the public registry
python3 scripts/check_fine_tune_report_card.py <dir>/report-card.json

# regenerate the published cohort / detect drift
python3 scripts/publish_report_cards.py
python3 scripts/publish_report_cards.py --check
```

Output is `report-card.json` (machine contract) plus `report-card.html`
(self-contained public page) rendered from the same validated payload.

Both entrypoints are **offline and deterministic**: no model load, training,
generation, eval, registry call, or network request; no wall-clock timestamp and
no live `git` call enters a payload, so recompiling the same sources reproduces
the same bytes. Provenance is recorded as content hashes instead.

No-GPU smoke: `bash evals/fine-tune-report-card-smoke.sh`.

The full operator chain works unchanged — emitted fragments →
`assemble_factory_run.py` → `check_factory_run_publish.py` →
`build_fine_tune_report_card.py` → `check_fine_tune_report_card.py` — so a card
can be compiled from any folder the generic assembler bridge produces.

## Measurement states

Every numeric or categorical observation carries a state. A bare `null` cannot
tell four different claims apart, so it is never used alone.

| State | Meaning | Rules |
|---|---|---|
| `measured` | Read directly from a source artifact for this candidate. | Needs a value and ≥1 source. |
| `derived` | Computed from other recorded values (a delta, a threshold comparison). | Needs `derived_from`. |
| `historical` | Imported from a legacy record without current run provenance. | Needs a caveat note. |
| `skipped` | Deliberately not run for this candidate. | Value must be null; note required. |
| `missing` | Evidence should exist but does not. | Value must be null; note required. |
| `not-applicable` | The check does not apply. | Value must be null; note required. |

`historical`, `skipped`, and `missing` are **weak**: a ship decision leaning on
one of them cannot be labeled fully verified.

Two consequences worth stating outright:

- Absent latency, RAM, throughput, cost, or timing renders as *not recorded*,
  never as `0`.
- A delta is only derived when both sides have values. "No change measured" and
  "change not measurable" are different claims, so a one-sided delta is
  `missing`.

## Payload shape

```text
schema_version, report_card_id, title
compiled_from   compiler, compiler_version, source_kind, source_id, dataset_hashes
subject         target, owner_goal, base_model, candidate_model, method, artifact
decision        decision, outcome_label, verified, verification_blockers,
                reason, failure_reason, failure_reason_confidence, lesson,
                next_action, blocked_by, evidence_sources
gates[]         role, name, metric, baseline, candidate, delta, threshold,
                passed, sample_size, frontier_ceiling, eval_identity
slices[]        name, metric, baseline, candidate, delta, passed, sample_size
performance     latency_ms, peak_rss_mb, tokens_per_second,
                training_time_seconds, training_cost_usd, eval_time_seconds
eval_validity   frontier_ceiling, frozen_eval, leakage, known_limitations
evidence[]      label, path, kind, sha256?, note?
caveats[]
```

Exactly one gate has `role: primary`; the rest are `regression` or `breadth`.

The typed mirror is
[`native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift`](../../native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift),
in the pure IO target so CLI, app, and report tooling can validate a card
without loading MLX. The smoke decodes real compiler output through it, so the
Python and Swift contracts cannot drift.

## Decisions and outcome labels

The canonical `ship`, `reject`, `retry-data`, `retry-training`, `retry-eval`,
and `park` vocabulary is unchanged (see [`eval-protocol.md`](eval-protocol.md)).
The report card adds a public label derived from it:

| Label | When |
|---|---|
| `shipped-specialist` | `ship` with no routing constraint. |
| `routed-ship` | `ship` that is safe only inside a named route or task envelope. |
| `report-only` | Any retry or park decision. No model to use. |
| `rejected` | `reject`. |

Only a `ship` decision can produce a ship-shaped label, so a report-only or
rejected candidate can never read as shipped.

## Verified vs. published

`decision.verified` is narrow and separate from "is this good". It is true only
when a ship traces end to end:

1. the decision is `ship`;
2. the primary gate's baseline, candidate, threshold, and result are all current
   measurements (not `historical`/`missing`);
3. the primary benchmark has frontier-ceiling evidence and frontier ~aces it
   (≥ 0.99 — an eval frontier cannot pass is a broken ruler, not a hard eval);
4. frozen-eval identity is recorded;
5. a train/eval overlap check ran and reports `no-overlap`;
6. no open blockers.

Anything else sets `verified: false` and lists every reason, on the page as well
as in the JSON. A verified ship can still have a failing breadth gate — verified
means *traceable*, not *unconditionally good*.

## Publication gate

`check_fine_tune_report_card.py` layers onto
[`check_factory_run_publish.py`](enforcement.md) rather than replacing it. It
fails closed, exits non-zero, prints every problem locally, and — when run via
the compiler — writes no artifact at all on failure.

Beyond schema and per-field state rules:

| Rule | Why |
|---|---|
| Detected train/eval overlap blocks publication outright | A contaminated score is not evidence. The candidate measurements stay in the payload rather than being hidden. |
| A `ship` needs `shipped=true`, a `package_dir`, no blockers, and a primary gate with values | An incomplete ship claim fails closed. |
| A `ship` whose **primary** gate is recorded as failing cannot publish | Recording a failure as *measured* is not the same as passing it: the candidate missed its own target. |
| `verified` and `verification_blockers` are recomputed from the evidence and must agree with the payload | The gate is where an untrusted or hand-edited card arrives; it must not take the payload's word for its own verification status. |
| A `ship` with a failing regression/breadth gate needs a `routing_constraint` | A regressing candidate may not be published as a general win. |
| A non-ship card must not be marked shipped and needs exactly one next action | Report-only artifacts stay honestly labeled. |
| A recorded delta must equal `candidate - baseline` | Blocks a hand-typed number that contradicts the measurements. |
| Denylisted field names (`prompt`, `completion`, `gold`, `prediction`, `weights`, credentials…) are rejected | A report card is a proof surface, not a data dump. |
| The rendered page must state the decision, its label, and every weak state it uses | The page can never read better than the payload. |

Non-ship cards with honest open blockers publish with `--allow-report-only`.
Ship claims stay strict in both modes.

The static page is also checked structurally: one `h1`, no skipped heading
levels, a caption and scoped headers on every table, resolvable
`aria-labelledby` targets, no empty link text, and no external asset or script.

## Public surface

Published cards are committed to `browser/public/report-cards/<slug>.{json,html}`
and served as `/report-cards/<slug>.html`. `/artifacts` links each one with its
outcome label and verification status; the card itself remains the source of
truth for its numbers, so the two surfaces cannot disagree.

Report cards do **not** change weight-release policy — the artifact `state` in
[`public-artifacts.md`](public-artifacts.md) still governs what may be released.

`publish_report_cards.py --check` recompiles into a temp directory and compares
against the committed files, so a stale card cannot ship silently.

A card records the SHA-256 of every committed file it cites, so **editing a cited
document changes the card**. That coupling is deliberate — the hash pins which
version of the evidence a claim rests on — but it means the drift check will fail
after an evidence-doc edit. Rerun `python3 scripts/publish_report_cards.py` and
commit the regenerated cards alongside the doc change. Ephemeral run-folder
fragments are deliberately *not* hashed; hashing them would make every re-render
drift.

## Optional run fragments

Two optional fragments let a run record evidence the base schema does not carry.
Both are absent-tolerant: without them the matching fields stay `missing`, so
existing run folders keep compiling unchanged. See
[`run-schema.md`](run-schema.md#optional-report-card-fragments).

- `eval-validity.json` — frontier ceiling, frozen-eval identity, overlap check,
  known limitations. Required for a fully verified ship.
- `cost.json` — training time, training cost, eval time.
