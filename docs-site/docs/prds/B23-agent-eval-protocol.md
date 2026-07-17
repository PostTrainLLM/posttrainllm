---
title: "PRD — Repeated-pass@1 + fixed resource budgets for agent evals"
---

# PRD — Repeated-pass@1 + fixed resource budgets for agent evals

> **Status (2026-06-18): partial shipped.** `posttrainllm eval-gate --passes K`
> now preserves repeated-run uncertainty in `gate-result.json`: per-suite
> trial scores, n, stdev, stderr, and 95% CI are attached to the candidate
> result, and the console table renders `mean±ci95_half_width`. `--budget
> evals/sample-budget.json` now attaches the fixed eval budget under the
> report's `"protocol"` block and exposes its path to suite commands as
> `TINYGPT_EVAL_BUDGET`. BFCL / tau / common Swift harness output rows now
> attach the same protocol block when `--budget` or `TINYGPT_EVAL_BUDGET` is
> present. `posttrainllm eval-compare` now renders repeated-run uncertainty as
> `mean±ci95_half_width` either from row-level `pass_stats` or from repeated
> rows with the same task/model/metric. `scripts/eval_pace_unhappy.py` now
> supports `--passes K` plus budget/protocol metadata in its JSON output.
> Remaining B23 work: future SWE-mini / Terminal-mini rows and actual
> sandbox/resource enforcement.

## Goal

Replace single-shot agent eval runs with the Poolside-class protocol:
each task is run K times under fixed budget constraints, results are
averaged with confidence intervals, and the exact resource envelope
(max steps, sandbox CPU/RAM, sampling params, model temperature) is
logged with every score. Applies to BFCL, τ-bench, the Pace unhappy-
paths suite, and any future SWE-mini / Terminal-mini benchmarks.

The result the leaderboard reports stops being "the model got 47/60
on OOS this run" and becomes "the model gets 47.3 ± 2.1/60 on OOS
under (max_steps=8, T=0, sandbox=1cpu+512mb)".

## Why now

- E9 just showed how noisy n=130 evals are — dims at n=40 carry ~±15pp
  CI. Single-run numbers in the SLM leaderboard are misleading, and
  cross-model comparisons amplify the noise.
- The leaderboard v0 just shipped (B27 in PLAN.md); rigor on the
  protocol is the difference between "internally interesting" and
  "publishable / linkable" outputs.
- Cheap to add — each harness already has a per-sample loop; the
  change is wrapping it in a per-task repeat loop with seed control
  and a budget config.

## Scope — in

- `Sources/TinyGPTModel/AgentEvalProtocol.swift` — shared types:
  ```swift
  struct AgentEvalBudget {
      let max_steps: Int
      let sandbox_cpus: Double
      let sandbox_ram_mb: Int
      let temperature: Float
      let top_p: Float
      let sampling_seed: Int  // base seed; pass+i is the per-pass seed
      let infra_patches: [String]  // e.g. "fix for bfcl#127 applied"
  }
  struct AgentEvalRunSummary {
      let task: String
      let model_fingerprint: String
      let budget: AgentEvalBudget
      let k: Int                         // number of pass@1 trials
      let per_trial_scores: [Double]
      let mean: Double
      let stdev: Double
      let ci95: (low: Double, high: Double)
  }
  ```
- Add `--passes K --budget budget.json` to `posttrainllm eval-bfcl`,
  `posttrainllm eval-tau-bench`, `scripts/eval_pace_unhappy.py`.
- Output JSON gains the `protocol` block carrying the budget + the
  per-trial scores. Existing `passed`/`total` stays for back-compat.
- `eval-compare` learns to render error bars (use ±1.96σ if `ci95`
  present).
- Default K=1 with budget loaded from a sensible per-task default
  (so the old `posttrainllm eval-bfcl` invocation works the same; opt
  into repeats via `--passes 3`).

## Scope — out

- **Sandbox enforcement** (actually capping CPU/RAM in the rust
  sandbox). The budget recorded here is *declarative* — the eval
  scripts pass the right flags into the existing sandbox-runner (see
  E5 HumanEval sandbox PRD). Hard enforcement is its own infra PRD.
- **Per-task default budgets baked into a config file**. Defer; this
  PRD ships a CLI flag, callers can build their own config.
- **Automatic flake detection** (find tasks where K=10 trials swing
  >20%). Useful follow-up; defer.

## Files to touch

| File | Change |
|---|---|
| `Sources/TinyGPTModel/EvalGate.swift` | shipped partial — `PassStats`, `AgentEvalBudget`, `AgentEvalProtocol` for gate results |
| `evals/sample-budget.json` | shipped partial — example fixed budget config |
| `Sources/TinyGPT/EvalBFCL.swift` | shipped partial — `--budget` row metadata wiring; K-pass repetition stays at `eval-gate` |
| `Sources/TinyGPT/EvalTauBench.swift` | shipped partial — same |
| `scripts/eval_pace_unhappy.py` | shipped partial — `--passes K`; aggregate per-trial via mean/stdev/ci95 and protocol budget |
| `Sources/TinyGPT/EvalCompare.swift` | shipped partial — renders `mean±ci95` for repeated rows / row-level `pass_stats` |
| `evals/sample-budget.json` | new — fixture budget config |
| `docs/research/mac_slm_leaderboard_v0.md` | "Protocol" subsection citing the budget format |

## Don't touch

- The harness scoring logic itself — we wrap, not rewrite.

## Acceptance criteria

- [x] `posttrainllm eval-bfcl <model> --budget evals/sample-budget.json`
  emits row-level protocol metadata.
- [ ] Per-harness `--passes 3` loops emit the `AgentEvalRunSummary`
  shape. Current K-pass repetition is centralized in `eval-gate`.
- [x] `posttrainllm eval-gate --passes K` gates on K-pass means and writes per-trial scores + 95% CI to `gate-result.json`.
- [x] `posttrainllm eval-gate --budget evals/sample-budget.json` writes budget metadata to `gate-result.json`.
- [ ] Default K=1 with default budget reproduces today's exact output
  format (back-compat).
- [x] `posttrainllm eval-compare` renders error bars when `ci95` is present.
- [ ] The SLM leaderboard page updates its column headers to reflect
  the per-task pass count.
- [x] Pace unhappy-paths gains `--passes` and the runbook in
  `docs/recipes/eval_planner.md` (if it exists; create if not) walks
  through the K=3 protocol.

## Reference patterns

- `Sources/TinyGPT/RunLmEval.swift` — already loops over tasks; the
  outer per-pass loop sits one level above that.
- [Poolside Laguna deep dive](https://poolside.ai/blog/laguna-a-deeper-dive)
  — the protocol-hardening rationale (their pass@1-with-fixed-budget
  is the discipline this PRD copies).
- Pace planner-champion JSON already records `date` per result —
  add the budget block alongside.

## Open questions

- Default K. **Recommendation:** K=1 for back-compat; the user-facing
  recipe in `docs/recipes/` advocates K=3. CI runs at K=1 to keep CI
  fast; manual publication runs at K=3+.
- Whether to fold the existing planner-champion JSON into the new
  schema or keep a separate "leaderboard champion" format.
  **Recommendation:** evolve in place — add the budget block, keep
  the existing fields. Migration is a one-time tool.
