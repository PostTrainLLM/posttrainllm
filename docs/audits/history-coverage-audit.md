# History Coverage Audit

This audit tracks how much of posttrainllm's historical work is normalized into the
structured attempt ledger, classified as technique inventory, or intentionally
left as narrative/reference material.

The goal is precision, not completeness theater. If an old note lacks enough
context to recover a real attempt, it receives a final narrative/reference
classification rather than becoming fabricated evidence or unfinished work.

## Current Structured Coverage

Source of truth: [`attempts.json`](../attempts.json).

| Dimension | Count |
|---|---:|
| Total structured attempts | 75 |
| Autocorrect | 2 |
| Chess | 1 |
| SQL | 17 |
| Pace planner | 14 |
| Browser product | 7 |
| Runtime/perf | 14 |
| File-ops | 3 |
| Factory/docs | 5 |
| Apple FM | 1 |
| Architecture | 1 |
| Archive model | 1 |
| Tool-calling harness | 3 |
| Game benchmarks | 3 |
| OffHours | 3 |

## Confidence Coverage

| Confidence | Count | Meaning |
|---|---:|---|
| `exact` | 64 | Direct run report, decision file, artifact metadata, or current source doc supports the reason. |
| `inferred` | 5 | Reason is reconstructed from docs/artifact notes, not a canonical run folder. |
| `not-applicable` | 4 | No failure reason is expected for a clean worked status. |
| `missing-evidence` | 2 | Attempt is known, but available docs do not preserve enough evidence to state a real reason. Used by Pace planner v1-v4 and v10. |

## Normalized Families

| Family | Status | Primary evidence |
|---|---|---|
| Character Chess specialist | normalized | `evals/chess/character-chess-44m-pilot-10k-v1.json`, `docs/learn/reproducing-qwen-chess-under-50m.md` |
| SQL factory POC and retries | normalized | `runs/2026-07-02-*`, `runs/2026-07-03-*`, `docs/specialists/b1-sql-poc.md` |
| Pace planner unhappy-path drill | normalized | `docs/sessions/DRILLDOWN.md`, `docs/sessions/RETROSPECTIVE.md`, `docs/sessions/pace-handoff-2026-06-10.md` |
| Browser product/demo failures | evidence normalized; narrative remainder classified | `docs/sessions/qa_log.md`, `docs/archive/lessons.md` |
| File-ops specialist artifacts | normalized | `docs/factory/public-artifacts.md`, `specialists/qwen3-4b-file-ops-distilled/` |
| Apple Foundation Models probe | normalized | `docs/learn/apple-on-device-foundation-models.md`, `AGENTS.md` |
| Browser/runtime performance attempts | evidence normalized; implementation notes classified | `docs/performance/performance.md`, `docs/techniques/speculative_heads.md`, `docs/performance/cpu_speedup_results.md`, `docs/performance/cold_start_results.md`, `docs/performance/gradient_checkpointing_results.md`, `docs/performance/kv_cache_optimization.md`, `docs/performance/yoco_results.md`, `docs/techniques/streaming_llm_kivi.md`, `docs/performance/data_perf.md`, `docs/performance/perf_audit_mlxfast_tied.md` |
| MoE architecture smoke | normalized | `docs/techniques/moe.md` |
| Audit 2026 technique rows | classified | `docs/audits/audit_2026.md`, `docs/techniques/audit-inventory.md` |
| Factory/docs enforcement work | normalized | `docs/factory/`, `docs/techniques/`, smoke scripts |
| Needle 2 base and catalog ablation | normalized | `docs/techniques/needle2-baseline-review.md`, `evals/needle2/` |
| Parakeet WebGPU browser ASR | normalized | `docs/techniques/parakeet-wgsl-browser-smoke.md`, `evals/parakeet-wgsl/` |
| OffHours validation and boundary runs | normalized | `evals/offhours/results/`, `/artifacts/offhours-context-interference` |
| Character Chess, 2048, and arena rulers | normalized | `evals/chess/`, `evals/game-2048/`, `browser/src/data/benchmarks/` |

## Classified Non-Ledger / Partial Surfaces

These docs contain useful evidence or lessons, but not every row is a run
attempt. The table records their exact treatment so we do not inflate the
attempt ledger with implementation facts or learning notes.

| Surface | Current treatment | Final treatment |
|---|---|---|
| `docs/audits/audit_2026.md` | Large shipped/skipped technique inventory; classified in `docs/techniques/audit-inventory.md` rather than forced into attempts. | Closed classification; fresh runs create new entries. |
| `docs/performance/performance.md` and `docs/perf_*` | Core WASM/WebGPU/matmul, CPU, cold-start, checkpointing, KV, YOCO, KIVI/StreamingLLM, data regularizer, and audit attempts are normalized; smaller notes are implementation facts. | Closed classification; do not inflate implementation notes into experiments. |
| `docs/techniques/speculative_heads.md` | The Medusa/EAGLE smoke is normalized; deeper paper ideas are recipe/reference material. | Closed as a learning recipe until a fresh target is opened. |
| `docs/sessions/qa_log.md` and browser docs | Core demo failures are normalized; other entries are chronology, product copy, or implementation handoff. | Closed narrative classification. |
| `docs/archive/lessons.md` | Major concrete lessons are normalized; the rest is explanatory context for the browser/demo arc. | Closed supporting narrative. |
| `docs/learn/journal.md` | Broad learning journal with technique notes. | Closed as learning context, not experiment evidence. |

## Classified Historical Sources

| Source | Classification | Ledger treatment |
|---|---|---|
| `docs/audits/audit_2026.md` | Technique inventory | Row-level treatment lives in `docs/techniques/audit-inventory.md`. Rows graduate only when a source doc preserves target, measurement, verdict, lesson, and next action. |
| `docs/sessions/qa_log.md` | Chronological browser/product narrative | Six concrete browser-product attempts are normalized; the remaining entries stay as timeline context. |
| `docs/archive/lessons.md` | Lessons narrative with concrete failure examples | Concrete failures are normalized when they include evidence and an outcome; explanatory teaching text stays narrative. |
| `docs/learn/journal.md` | Learning thought process | Not an attempt source by default. Promote only when an entry points to a real run, eval, artifact, or PRD decision. |
| `docs/perf_*`, `docs/*_results.md` | Runtime result notes | Normalize measured before/after attempts; leave pure design notes as references. |

## Backfill Rule

Add an old attempt to `docs/attempts.json` only when all fields can be filled:

- `id`
- `name`
- `family`
- `status`
- `evidence`
- `failure_reason_confidence`
- `lesson`
- `next_action`
- `evidence_sources`

For `failed`, `regressed`, `worked-with-caveat`, and `inconclusive`, also
require `failure_reason`.

If the source docs conflict on a number, do not hide the conflict. Either quote
both values in `evidence` and use `inferred`, or leave the attempt out until the
original run artifact resolves it.

## Current Honest Readout

The structured history now covers every known evidence-backed experiment in the
factory, browser, Mac-runtime, model, external-runtime, and benchmark lanes.
Broad technique rows remain classified in `docs/techniques/audit-inventory.md`.
Learning-journal and archive narrative entries are intentionally not attempts
unless they point to a real run, eval, artifact, or PRD decision; that is a
final classification, not an implied experiment backlog.
