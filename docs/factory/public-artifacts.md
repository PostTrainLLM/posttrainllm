# Public Artifacts

Public artifacts are first-class factory outputs. They are different from local
run files: a public artifact should be understandable outside this repo, have a
small committed metadata surface, and list its blockers as clearly as its wins.

Website surface: `/artifacts`. The website should behave like a built-in blog
for artifacts: one index page for scanning, one detail page per artifact, and
numbers/blockers/evidence on every page.

## Release Rule

Every public artifact entry must include:

- artifact id and type
- current status
- what can be published now
- measured evidence
- competitive context
- blockers
- next release action

Weights, adapters, and large run outputs do not need to live in git, but the
public artifact must explain where they came from, how they were evaluated, and
why it is or is not ready to package.

Competition rows must be labeled as:

| Label | Meaning |
|---|---|
| `Direct` | Same fixture, prompt/eval setup, metric, and scorer. |
| `Directional` | Useful market or method context, but not the same eval. |
| `Not comparable` | Public high bar or adjacent system that explains the target lane but cannot be claimed as a win/loss. |

Public copy should prefer "we beat X on this exact local gate" only for
`Direct` rows. Everything else is context until the same benchmark is run.

## Artifact States

| State | Meaning |
|---|---|
| `release-ready-metadata` | Small committed metadata exists; large weights may still be external. |
| `candidate-current-best` | Best measured candidate, but not yet a shipped specialist package. |
| `report-only` | Good public write-up/repro artifact, but no model should be used directly. |
| `blocked` | Needs a named unblocker before public release work continues. |
| `parked` | Real artifact, but not active in the factory sequence. |

## Current Public Artifact List

| Artifact | Type | State | Public value | Next release action |
|---|---|---|---|---|
| `qwen3-4b-file-ops-distilled` | Specialist package metadata | `release-ready-metadata` | Shows a real TinyGPT-built routed specialist: 58% -> 100% on file-ops hard gate, with breadth regression disclosed. | Decide whether to release metadata-only first or publish/host the multi-GB fused weights. |
| `qwen06-sql-routed-v1` | Routed SQL specialist POC | `candidate-current-best` | Shows the factory/router pattern on SQL: public exact 0.531 and synthetic execution 0.860 using separate routed adapters. | Convert to a public report artifact; package only after a public execution benchmark gate exists. |
| `factory-run-schema-v1` | Process artifact | `report-only` | Explains the repeatable `target -> data -> post-training -> eval -> package -> report` contract. | Add one canonical rendered example run and link it from the README. |
| `browser-playground` | Demo artifact | `parked` | Public proof of the earlier browser/WASM/WebGPU learning track. | Keep parked unless it directly presents factory reports or artifacts. |

## Artifact Details

### `qwen3-4b-file-ops-distilled`

Status: `release-ready-metadata`

Committed surface:

- `specialists/qwen3-4b-file-ops-distilled/model_card.md`
- `specialists/qwen3-4b-file-ops-distilled/eval_report.json`
- `specialists/qwen3-4b-file-ops-distilled/tinygpt.lock.json`
- `specialists/qwen3-4b-file-ops-distilled/prompt.md`
- `specialists/registry.json`

Measured evidence:

| Gate | Stock | Specialist |
|---|---:|---:|
| File-ops hard gate | 0.58 | 1.00 |
| File-ops hardgen heldout | - | 0.95 |
| Out-of-domain breadth | 0.596 | 0.423 |

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Weight distribution undecided | The lock points to `~/.cache/tinygpt/models/mt4b_fused`, not a public download. | Choose metadata-only release or publish the artifact to a durable host. |
| Breadth regression is real | The model is unsafe as a general planner. | Keep routed-only positioning in all public copy. |
| Frontier/breadth caveat remains | The breadth suite is directly comparable but not fully frontier-validated. | Keep caveat in model card; do not oversell as general capability. |

### `qwen06-sql-routed-v1`

Status: `candidate-current-best`

Current artifact shape:

- Public adapter:
  `runs/2026-07-02-sql-public-bmc2/qwen06-public-bmc2-v4-joinweighted.lora`
- Synthetic adapter:
  `runs/2026-07-02-sql-expanded-qwen06/qwen06-sql-expanded.lora`
- Router:
  `scripts/run_sql_routed_generate.py`
- Router smoke:
  `evals/sql-routed-router-smoke.sh`
- Eval fixture:
  `evals/sql-routed-mixed-v1/`
- Report:
  `docs/specialists/b1-sql-poc.md`

Measured evidence:

| Gate | Result |
|---|---:|
| Public b-mc2 exact, 64 rows | 0.531 |
| T5-small public baseline, same 64 rows | 0.484 |
| Synthetic SQLite execution, 50 rows | 0.860 |
| Synthetic SQLite exact, 50 rows | 0.840 |
| Label-free router smoke | 64 public / 50 synthetic, all high-confidence |

Competitive context:

| System | Metric | Score | Comparable? | Readout |
|---|---|---:|---|---|
| TinyGPT routed SQL v1 | b-mc2 exact / synthetic exec | 0.531 / 0.860 | Direct | Current local candidate. |
| T5-small local baseline | b-mc2 exact | 0.484 | Direct | Same 64-row public slice; TinyGPT is +4.7 points. |
| Defog SQLCoder-7B-2 | Defog SQL-Eval category scores | 77.1-96% | Directional | Strong public SQL specialist, but different benchmark and 7B size class. |
| Arctic-Text2SQL-R1-7B | BIRD execution accuracy | 68.47% | Not comparable | Public execution target class; TinyGPT needs BIRD/Spider execution before competing here. |
| Arctic-Text2SQL-R1-14B / 32B | BIRD execution accuracy | 70.04% / 71.83% | Not comparable | Current public high bar is execution accuracy, not exact string match. |

External source notes:

- `cssupport/t5-small-awesome-text-to-sql` is the direct local baseline model;
  the 0.484 score is our local rerun on the same 64-row b-mc2 slice.
- Defog SQLCoder-7B-2 reports category-level Defog SQL-Eval scores, not one
  aggregate score.
- Arctic-Text2SQL-R1 reports BIRD execution accuracy; use it as the public
  execution target lane, not as a direct comparison.
- BFCL-V4 market rows on the website use the LLM Stats July 2026 snapshot only
  as directional context because that page marks the rows as self-reported and
  unverified. The official BFCL page remains the methodology/source-of-truth
  benchmark reference.

Rejected alternatives:

| Attempt | Public exact | Synthetic execution | Decision |
|---|---:|---:|---|
| Single public v4 adapter | 0.531 | 0.240 | route required |
| Blended SFT v1 | 0.297 | 0.560 | reject |
| Best static LoRA composition tested | 0.516 | 0.460 | reject |
| BIRD+b-mc2 v5 | 0.438 | 0.280 | reject |

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Public execution benchmark missing | b-mc2 exact match is useful but not enough for a serious SQL model claim. | Add BIRD Mini-Dev SQLite or Spider SQLite execution gate once DBs are local. |
| Not packaged under `specialists/` | Current adapter paths are local `runs/` outputs, not package metadata. | Create a package only after `decision.json` is `ship`; until then publish as report-only/candidate. |
| Output hygiene is weak | Scorers extract the first `SELECT`; many completions still include prose after the query. | Add clean-SQL metric and stopping/format preference data before shipping. |
| Performance numbers missing | Public artifact should report latency, RAM, tok/s, and eval time. | Add one measured inference/eval run on the routed setup. |
| Data provenance needs public copy | b-mc2 and BIRD-derived rows have different licenses/provenance surfaces. | Add dataset license/provenance notes to the public report. |

Next release action:

Publish `qwen06-sql-routed-v1` as a **public report artifact**, not a shipped
specialist package. The report should say: targeted 0.6B SQL adapter beats a
small T5 baseline on the frozen public exact slice, but the robust artifact is a
router over two specialists, and public execution benchmarking is the next gate.

Website page: `/artifacts/qwen06-sql-routed-v1`

## Release Priority

1. `qwen06-sql-routed-v1` report artifact: best current story for the factory
   thesis because it includes failed attempts, routing, blockers, and measured
   improvement.
2. `qwen3-4b-file-ops-distilled` metadata artifact: strongest model win, but
   weight distribution and routed-only caveats must be handled carefully.
3. `factory-run-schema-v1`: publish as process proof once one rendered run
   folder is canonical.
4. `browser-playground`: leave parked unless it becomes a report browser.
