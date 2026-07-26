# History Coverage Audit

This audit tracks how much of posttrainllm's historical work is normalized into the
structured attempt ledger, classified as technique inventory, or intentionally
left as narrative/reference material.

The goal is precision, not completeness theater. If an old note has numbers but
not enough context to recover a real attempt, it stays listed here until it can
be normalized without inventing history.

## Current Structured Coverage

Source of truth: [`attempts.json`](attempts.json).

| Dimension | Count |
|---|---:|
| Total structured attempts | 57 |
| Autocorrect | 2 |
| SQL | 17 |
| Pace planner | 6 |
| Browser product | 6 |
| Runtime/perf | 14 |
| File-ops | 3 |
| Factory/docs | 5 |
| Apple FM | 1 |
| Architecture | 1 |
| Archive model | 1 |
| Tool-calling harness | 1 |

## Confidence Coverage

| Confidence | Count | Meaning |
|---|---:|---|
| `exact` | 43 | Direct run report, decision file, artifact metadata, or current source doc supports the reason. |
| `inferred` | 5 | Reason is reconstructed from docs/artifact notes, not a canonical run folder. |
| `not-applicable` | 9 | No failure reason is expected for worked/not-tried status. |
| `missing-evidence` | 0 | No structured entry currently uses this label. |

## Normalized Families

| Family | Status | Primary evidence |
|---|---|---|
| SQL factory POC and retries | normalized | `runs/2026-07-02-*`, `runs/2026-07-03-*`, `docs/specialists/b1-sql-poc.md` |
| Pace planner unhappy-path drill | normalized | `docs/DRILLDOWN.md`, `docs/RETROSPECTIVE.md`, `docs/pace-handoff-2026-06-10.md` |
| Browser product/demo failures | partially normalized | `docs/qa_log.md`, `docs/archive/lessons.md` |
| File-ops specialist artifacts | normalized | `docs/factory/public-artifacts.md`, `specialists/qwen3-4b-file-ops-distilled/` |
| Apple Foundation Models probe | normalized | `docs/learn/apple-on-device-foundation-models.md`, `AGENTS.md` |
| Browser/runtime performance attempts | partially normalized | `docs/performance.md`, `docs/speculative_heads.md`, `docs/cpu_speedup_results.md`, `docs/cold_start_results.md`, `docs/gradient_checkpointing_results.md`, `docs/kv_cache_optimization.md`, `docs/yoco_results.md`, `docs/streaming_llm_kivi.md`, `docs/data_perf.md`, `docs/perf_audit_mlxfast_tied.md` |
| MoE architecture smoke | normalized | `docs/moe.md` |
| Audit 2026 technique rows | classified | `docs/audit_2026.md`, `docs/techniques/audit-inventory.md` |
| Factory/docs enforcement work | normalized | `docs/factory/`, `docs/techniques/`, smoke scripts |

## Classified Non-Ledger / Partial Surfaces

These docs contain useful evidence or lessons, but not every row is a run
attempt. The table records their exact treatment so we do not inflate the
attempt ledger with implementation facts or learning notes.

| Surface | Current treatment | Next action |
|---|---|---|
| `docs/audit_2026.md` | Large shipped/skipped technique inventory; now classified in `docs/techniques/audit-inventory.md` rather than forced into attempts. | Promote only rows that later gain target/eval/decision evidence into the attempt ledger. |
| `docs/performance.md` and `docs/perf_*` | Core WASM/WebGPU/matmul, CPU, cold-start, checkpointing, KV, YOCO, KIVI/StreamingLLM, data regularizer, and audit attempts are normalized; smaller perf notes may still be implementation facts rather than attempts. | Add only additional entries with baseline/candidate/gate/lesson. |
| `docs/speculative_heads.md` | The Medusa/EAGLE smoke is normalized; deeper paper-recipe ideas remain future techniques. | Keep future logit-KL/tree-attention work in the technique backlog until run. |
| `docs/qa_log.md` and browser docs | Core demo failures are normalized; remaining entries are mostly chronology, product copy, or implementation handoff. | Add only entries with evidence, shipped outcome, and a reusable lesson. |
| `docs/archive/lessons.md` | Major concrete lessons are normalized; the rest is explanatory context for the browser/demo arc. | Keep as supporting narrative unless a new concrete run/eval source appears. |
| `docs/learn/journal.md` | Broad learning journal with many technique notes. | Use as supporting evidence, not structured attempts, unless a section points to a run. |

## Classified Historical Sources

| Source | Classification | Ledger treatment |
|---|---|---|
| `docs/audit_2026.md` | Technique inventory | Row-level treatment lives in `docs/techniques/audit-inventory.md`. Rows graduate only when a source doc preserves target, measurement, verdict, lesson, and next action. |
| `docs/qa_log.md` | Chronological browser/product narrative | Six concrete browser-product attempts are normalized; the remaining entries stay as timeline context. |
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

The structured history is strong for the factory-relevant lanes: SQL,
Pace-planner, browser-product failures, file-ops, Apple FM, runtime/perf
attempts with numbers, MoE, and factory enforcement. Broad technique rows are
classified in `docs/techniques/audit-inventory.md`. Learning-journal and
archive narrative entries are intentionally not attempts unless they point to a
real run, eval, artifact, or PRD decision.
