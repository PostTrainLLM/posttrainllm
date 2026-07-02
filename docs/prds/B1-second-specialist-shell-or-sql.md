---
name: B1 second specialist (SQL POC)
status: expanded-qwen06-poc-complete; retry-data
owner: unassigned
created: 2026-06-13
parent_plan: docs/PLAN.md §3 Tier B (B1)
related_prds: A1-first-specialist-tool-caller.md (the template; B1 cookie-cuts off it)
---

# PRD — Second specialist after A1 ships

## Goal

Run the factory recipe shape against SQL to validate that the platform is not
accidentally tied to a tool-calling target. Same factory loop, different data
and eval.

Two specialists ship the platform thesis: "you can do this for *any*
task" is much stronger than "we did this for one task."

## Why now

- The active factory cleanup selected SQL as the first low-compute POC because
  `tinygpt eval-sql` is already self-contained and smoke-tested.
- The initial fixture is deliberately tiny and deterministic. The first live
  Qwen3-0.6B runs proved the loop but were marked `retry-data`; Spider remains
  the later public benchmark once preference tuning is tested.

## Scope — in

- Freeze the POC fixture in `evals/sql-poc/`.
- Use `scripts/recipes/b1-sql.sh` for the live SFT/generate/eval path.
- Score with `tinygpt eval-sql`.
- Write row-level failure traces from `eval-sql --out`.
- Ship/retry gate: candidate execution accuracy ≥ baseline + 3pp.
- Artifact: `adapters/b1-sql.lora` or `specialists/b1-sql/`.

## Scope — out

- **Combining A1 + B1 into a single multi-task adapter.** Distinct
  adapters keep the experiment clean; merging is its own arc.
- **Cross-domain transfer ablation.** Useful research; defer.

## Files to touch

| File | Change |
|---|---|
| `scripts/recipes/b1-sql.sh` | recipe path for SFT → generate → eval |
| `Sources/TinyGPT/EvalSql.swift` | SQL execution-accuracy harness |
| `docs/specialists/b1-sql-poc.md` | POC brief |
| `docs/research/mac_slm_leaderboard_v0.md` | regenerate with the new row |
| `docs/PLAN.md` | B1 ⬜ → ✅ on ship |

## Acceptance criteria

- [x] Low-compute SQL fixture exists and is smoke-tested.
- [x] Row-level eval traces capture SQL failures.
- [x] Live baseline score recorded from Qwen3-0.6B on the toy SQL eval.
- [x] First SQL adapter beats base by ≥ 3pp on the toy SQL eval.
- [x] Expanded non-overlapping synthetic SQL set generated and evaluated.
- [x] Failure labels and DPO-style preference rows emitted from the expanded
  candidate failures.
- [x] Factory run folder contains config, dataset, train log,
  baseline/candidate evals, row traces, report, artifact metadata, and
  decision.
- [ ] Run preference tuning or move to a public benchmark slice before any ship
  claim.

## Reference patterns

- `docs/prds/A1-first-specialist-tool-caller.md` — the template.
  This PRD is the second instance; if the recipe doesn't generalize
  easily, that's the finding.
- [InterCode-Bash](https://intercode-benchmark.github.io/) — the
  shell-side eval scaffolding.
- [Spider](https://yale-lily.github.io/spider) — the SQL-side eval
  scaffolding.

## Open questions

- Which public benchmark replaces the toy fixture after the POC: Spider is the
  default unless another SQLite-backed text-to-SQL set is lower friction.
