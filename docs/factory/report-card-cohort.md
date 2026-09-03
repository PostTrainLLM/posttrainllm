# Report Card Cohort and Review

The dogfood pass for the [Fine-Tune Report Card](report-card.md): what was
compiled from existing evidence, what could not be, and what the review changed.

No model was trained, loaded, or evaluated for any of this. Every card is
compiled from files already in the repository.

## Published cohort

| Slug | Source | Outcome | Verified | Headline |
|---|---|---|---|---|
| [`qwen3-4b-file-ops-distilled`](https://posttrainllm.com/report-cards/qwen3-4b-file-ops-distilled) | specialist package | `routed-ship` | no | depth 0.58 → 1.00, breadth 0.596 → 0.423 |
| [`qwen3-4b-rest-fused`](https://posttrainllm.com/report-cards/qwen3-4b-rest-fused) | specialist package | `routed-ship` | no | fresh depth 0.75 → 1.00, breadth 0.667 → 0.556 |
| [`qwen06-sql-routed-v1`](https://posttrainllm.com/report-cards/qwen06-sql-routed-v1) | canonical run folder | `report-only` | no | synthetic execution 0.16 → 0.86 |

**No published card claims a verified ship**, and that is the honest result: the
two shipped packages carry `historical` values with no eval command, frozen-eval
identity, or overlap check, and the SQL candidate is a `retry-eval` with three
open blockers. Each card lists its own blockers.

Regenerate the cohort with `python3 scripts/factory/publish_report_cards.py`; check for
drift with `--check` (also step 4 of `evals/fine-tune-report-card-smoke.sh`).

### What each card shows

`qwen3-4b-file-ops-distilled` is the useful case for the format. The depth gate
passes hard, the breadth gate is derived as **failing** (candidate below
baseline, no threshold recorded), and publication is only allowed because the
package states a routing constraint. Its depth benchmark does carry a recorded
frontier score of 1.0 — but as `historical`, so it still cannot certify a
verified ship.

`qwen3-4b-rest-fused` now imports the fresh paired scores and candidate resource
measurements, but remains a legacy specialist-package card: the compiler marks
them `historical` and cannot import the frozen-eval identity or overlap check
from the external run receipt. Depth passes, breadth is derived as regressing,
and publication remains valid only because the routing constraint is explicit.
Nothing is promoted to a fully verified general ship.

`qwen06-sql-routed-v1` is the strongest provenance in the cohort: `measured`
baseline and candidate, four slices including a candidate-only join slice whose
baseline and delta stay `missing`, seven dataset SHA-256 hashes, and a
`retry-eval` decision with one next action.

## Documented absences

The spec allows a documented absence where an outcome class has no compilable
evidence. Three classes have none in a clean checkout:

| Class | Why absent | Covered by |
|---|---|---|
| `retry-training` / `retry-data` | The three SQL hygiene runs (2026-07-03, 2026-07-11 ×2) exist only as folders under gitignored `runs/`. An operator can regenerate and compile them; a fresh clone cannot. | fixture `retry` |
| `reject` | `qwen3-4b-multibackend-distilled` (negative transfer: depth 100%, breadth 31%) is recorded only as a prose row in [`public-artifacts.md`](public-artifacts.md). No `eval_report.json` or run folder was committed. | fixture `reject` |
| fully verified ship | No real candidate has recorded frontier-ceiling **and** overlap-check evidence, because the run schema had nowhere to put them until this change. | fixture `ship-verified` |

Fixtures live in `tests/report_card_fixtures.py` and cover nine cases — the five
publishable classes, the historical specialist shape, and three that must fail
closed. They are synthetic by construction and are never published.

## Mapping gaps found in review

Reviewing each card against its sources surfaced gaps in the *source* formats,
not in the report card. They are recorded rather than papered over.

### Specialist package format

| Gap | Effect on the card |
|---|---|
| No owner goal | `subject.owner_goal` is `missing`. |
| No per-gate eval command | The gate cannot be replayed from the card alone. |
| No ship threshold | The primary gate's `passed` is `missing` — a pass/fail cannot be derived without a bar. |
| No frozen-eval identity | Blocks a verified ship. |
| No train/eval overlap check | Blocks a verified ship. |
| No machine-readable next action | The release action lives as prose in `public-artifacts.md`. |
| No dataset hashes | `compiled_from.dataset_hashes` is empty. |
| Ad-hoc score keys (`stock_4b`, `distilled_4b`, `rest_4b`) | The compiler identifies the baseline/candidate pair and **fails closed** on ambiguity rather than guessing. |

### Canonical run schema

| Gap | How the compiler handles it |
|---|---|
| No per-gate sample size (only per-slice) | Read from the slice `config.eval.primary_slice` names; `missing` without that pointer. |
| Regression gate has no before/after pair | Read from the slice `config.eval.regression_slice` names; `missing` without that pointer. |
| No frontier-ceiling, overlap, or frozen-eval identity fields | Added as the optional `eval-validity.json` fragment. |
| No training time / cost / eval time | Added as the optional `cost.json` fragment. |
| No artifact routing constraint | Added as optional `artifact.routing_constraint`. |
| `runs/` is gitignored | Run-sourced cards must be regenerated by the operator. The SQL card works in a clean checkout only because `render_sql_factory_run.py` rebuilds its folder from committed fixtures. |

Both new fragments are absent-tolerant: without them the matching fields stay
`missing`, so every pre-existing run folder compiles unchanged.

## What the review changed

Refinements made *because* the cohort exposed them:

- Added `eval-validity.json` and `cost.json` so frontier-ceiling, leakage,
  frozen-eval identity, and cost/time have a canonical home. Before this, a
  fully verified ship was unreachable by construction.
- Added optional `artifact.routing_constraint`, so a run-sourced routed ship can
  disclose its envelope the way a specialist package already can.
- Renamed the `missing` display label from "not measured" to **"not recorded"**:
  the same label has to read correctly for an absent number *and* an absent text
  field.
- A `park` decision from an unregistered package now **derives** its next action
  from the registry check that produced the decision, instead of leaving it
  `missing` and failing the "non-ship needs one next action" rule.

An adversarial review pass then found eight ways a card could still be
confidently mislabeled. All are fixed, and each has a regression test in
`tests/test_fine_tune_report_card.py` under "review regressions":

| Was | Now |
|---|---|
| A ship whose **primary** gate was recorded as failing published as `shipped-specialist` and rendered "Fully verified" — the chain checked that pass/fail was *measured*, not that it *passed*. | A failed primary gate is a verification blocker and a hard publication failure. |
| Gate→slice mapping was inferred. Score-equality matching could attach an unrelated 3-row slice's `n` to a 400-row gate; name-token containment could pick a coincidental short slice name over the correct specific one, turning a 19-point breadth regression into a reported +50-point pass. | Both heuristics deleted. Mapping is explicit via `config.eval.primary_slice` / `regression_slice`, else `missing`. |
| `validate` only cross-checked `verified` against `verification_blockers`, so a payload could assert both. | Both validators recompute the chain from the evidence and reject any disagreement. |
| Slice deltas were never checked against their own baseline/candidate. | Slices get the same consistency check as gates, in Python and Swift. |
| A single global `frontier.score` was attributed to every suite, citing a `by_suite` path absent from the source. | Frontier ceilings are per-suite only; an unattributed score verifies nothing. |
| The denylist scan was Python-only; Swift's typed decoder silently dropped a smuggled `eval_prompt`. | `FineTuneReportCard.checkPublicSafety` walks the raw JSON before decoding. |
| `dataset_hashes[].rows` was untyped in Python but `Int?` in Swift, so the compiler could emit a card its own mirror could not decode. | Row counts and field value shapes are type-checked to match the Swift contract. |
| `BASELINE_KEY_HINTS` matched substrings, so a candidate key containing `base` (e.g. `database_expert`) could be read as the baseline and invert a delta's sign. | Whole-token matching; an unidentifiable pair fails closed. |

## Next actions

These are operator-owned and need real measurement, not more tooling:

1. Emit `eval-validity.json` and `cost.json` from the live train/eval commands so
   the next run can reach a verified ship.
2. Record a frontier-ceiling score for the file-ops breadth suite and the SQL
   synthetic-execution suite — both are currently unvalidated rulers.
3. Run an overlap check on the SQL held-out split and commit the result; the
   zero-overlap claim for `preferences.jsonl` currently lives only in
   `docs/NEXT.md` prose.
4. Commit an `eval_report.json` for `qwen3-4b-multibackend-distilled` so the
   `reject` class has a real published card instead of a documented absence.
