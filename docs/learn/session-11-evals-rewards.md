# Session 11 — Evals, rewards, and self-improvement: making progress real

> Fills **Module 10** of [`curriculum.md`](curriculum.md), the capstone. Modules
> 1–9 built a model and taught it behavior. This session is the part that
> decides whether any of it *worked* — frozen evals, verifiable rewards, failure
> analysis, and the loop that turns a failed run into the next better recipe.

## Where we are

You can now train and post-train a model (Module 9). The dangerous moment is
right after: a number went up and it *feels* like progress. Most of the skill in
this factory is refusing to believe that feeling until the eval earns it. This
session is how you tell a real improvement from a measurement artifact — and how
you turn "it failed" into the next thing to build.

This is where the ground-up curriculum meets the factory loop:

```text
target -> data -> post-training -> eval -> package -> report
```

Modules 1–9 were mostly the middle. This module is `eval -> report`, plus the
feedback arrow back to `data`.

---

## Why a frozen eval comes first

If the eval moves while you train, every comparison is meaningless — you cannot
tell whether the model improved or the test got easier. So the eval is **frozen
before training starts**: the dev set, the scoring command, and the pass
threshold are all written down and never touched during the run.

This repo enforces it. [`docs/factory/eval-protocol.md`](../factory/eval-protocol.md)
is the contract: a candidate is compared against a **frozen baseline** whose
scores were stamped ahead of time. The frozen SQL target
`qwen06-sql-hygiene-dpo-v1` recorded its baseline (synthetic execution 0.860,
clean-SQL raw rate 0.000) and its ship bar *before* the candidate existed. That
ordering is not bureaucracy; it is the only way the after-number means anything.

**Mastery reflex:** if someone reports an improvement without naming the frozen
baseline it beat, you do not yet know if it is real.

---

## Two numbers that disagree: exact match vs execution accuracy

The single most important eval lesson in this project. Consider SQL:

```sql
-- gold:      SELECT name FROM users WHERE age > 30
-- candidate: SELECT name FROM users WHERE age > 30.0
```

- **Exact match** (string equality): **fail** — the strings differ.
- **Execution accuracy** (run both, compare result rows): **pass** — same rows.

Exact match under-counts correct answers (many SQL strings return identical
results) and occasionally over-counts (a string can match yet error at runtime).
**Execution accuracy is the trusted metric; exact match is only directional.**
This is why `docs/NEXT.md` keeps public b-mc2 *exact* (0.531) as a gate but flags
that the real bar is a public Spider/BIRD *execution* gate. The general lesson:
**score the thing you actually care about, not a proxy that's easy to compute.**

---

## Verifiable rewards — evals you can trust enough to train on

An eval you trust can become a **reward**: a signal a training loop optimizes
against. But only *verifiable* rewards are safe to optimize, because a training
loop will exploit any gap between the reward and what you meant.

| Reward type | Verifiable? | Example in repo |
|---|---|---|
| Executable check | **Yes** — run it, get ground truth | SQL execution accuracy; unit-test pass |
| Structural match | **Yes** — parse and compare | BFCL tool-call AST matching |
| Format rule | **Yes** — deterministic scorer | clean-SQL raw-output metric (`scripts/score_sql_clean_output.py`) |
| Model-judged | **Partly** — a judge can be gamed | LLM-as-judge (use with care) |
| Vibes | **No** | "it looks better" |

The rule: **the more verifiable the reward, the more aggressively you can train
against it.** SQL execution and BFCL AST matching are the clean reward surfaces
in this repo precisely because they cannot be faked — the query runs or it
doesn't. [`../techniques/sql-technique-backlog.md`](../techniques/sql-technique-backlog.md)
is the ledger of which reward each SQL recipe targets.

---

## Leakage and contamination — the silent score inflator

If a test example (or its answer) appeared in training, the eval measures
memorization, not skill, and the score is a lie. Two guards:

- **Held-out split locked before training** — the dev set is quarantined.
- **Overlap checks** — the hygiene DPO run explicitly verified *zero
  prompt/gold overlap* between its 108 preference pairs and the 50-row dev set.

Contamination is the most common way a great-looking number is worthless. When a
small model suddenly aces a public benchmark, suspect leakage first.

---

## Slices and traces — one number is not enough

**Aggregate accuracy hides where the model actually fails.** "0.74 overall" can
be 0.95 on easy single-table queries and 0.20 on multi-table JOINs. **Slice
metrics** break the score down by category so you can see the real weakness.
This repo requires it: `scripts/score_sql_slices.py` emits `slice-metrics.json`,
and `docs/NEXT.md` states *no SQL candidate is reported without
`slice-metrics.json` and `trace_review.md`.*

**Trace review** goes one level deeper — read the actual failing generations,
not just the count. `scripts/review_sql_trace.py` surfaces them, and a
**failure taxonomy** groups them ("wrong JOIN key," "hallucinated column,"
"fenced output") so the failures become a *shape*, not noise. That shape is what
you turn into the next dataset.

---

## The decision — ship, reject, or retry

An eval is not done until it produces a decision with evidence. The required
report fields (from [`../factory/reports.md`](../factory/reports.md) and
`docs/NEXT.md`):

```text
score delta · pass/fail · regressions · breadth retention
latency · RAM/peak RSS · token throughput · cost/time
artifact path · ship / reject / retry decision
```

**Breadth retention** deserves its own callout: a specialist that wins its niche
but wrecks general ability is a routed specialist at best, not a planner. The
file-ops distill took the file-ops hard gate 58% → 100% but dropped
out-of-domain breadth 59.6% → 42.3% — a real result, and exactly why it ships as
a *routed* specialist and not a general model. The decision is only `ship` when
the win is real *and* the regressions are acceptable.

---

## Self-improvement: a failed run is the next learning prompt

This is the arrow that makes the factory a *loop* instead of a pipeline. The
canonical worked example in this repo:

1. **Ran** the hygiene SimPO candidate against the frozen baseline.
2. **It collapsed** — composed execution 0.860 → 0.080; the adapter alone
   generated fence spam. Decision: **retry-training**.
3. **The failure became the diagnosis** — ref-free SimPO with too high a
   learning rate wrecked the policy.
4. **The diagnosis became the next recipe** — reference-anchored DPO (or SimPO
   at ~10× lower LR, ≤50 steps) on the *same frozen pairs*, evaluated composed.
5. **It all got recorded** in [`../attempt-ledger.md`](../attempt-ledger.md) so
   the next person (or the next you) does not repeat it.

That is self-improvement without any RL: the eval exposed a specific failure, the
failure named a specific fix, and the ledger kept the lesson. **RLVR/ReST** loops
(covered in [`advanced-llm-training.md`](advanced-llm-training.md)) automate this
same shape — generate, score with a verifiable reward, keep the winners, retrain
— but the manual loop above is the concept; the RL version is the throughput
upgrade. Note the discipline: the retry reuses the *frozen* pairs and eval, so
the only thing that changed is the recipe. That is how you learn from a failure
instead of just churning.

---

## A subtle one: selection is easier than generation

The current lab focus. Judging which of several candidate SQL queries is correct
(**selection**) is an easier task than writing the correct one from scratch
(**generation**) — and it has a cleaner reward (execution/gold equivalence).
`scripts/build_sql_candidate_choice.py` and `score_sql_candidate_choice.py` build
and score selection rows. The open question — the thing the eval is being
designed to answer — is *whether selection skill transfers back to generation.*
That is a real research question posed as an eval, which is exactly the altitude
this module is training you to operate at.

---

## Self-check

Don't peek:

1. **Why must the eval be frozen before training, not after?**
2. **Give a SQL pair where exact match and execution accuracy disagree — and say
   which metric you trust.**
3. **What makes a reward "verifiable," and why does that determine how hard you
   can train against it?**
4. **A specialist takes its target gate 58% → 100% but drops general breadth
   60% → 42%. Ship, reject, or route — and why?**
5. **The hygiene SimPO run collapsed 0.860 → 0.080.** Walk the loop: what did the
   eval expose, what recipe change does it imply, and where is the lesson
   recorded?

---

## Where this connects

- **Back to Module 9:** post-training produced the candidate; this module decides
  whether it earned a place. Back to Module 8: a collapsed policy shows up first
  as a broken eval, not a broken loss curve.
- **This is the end of the ground-up arc** — from `y = mx + b` (Session 2) to a
  documented ship/reject decision on a real specialist. The rest of the project
  is applying this loop to new targets.
- **Repo anchors:** posttrainllm's factory contracts —
  [`../factory/eval-protocol.md`](../factory/eval-protocol.md),
  [`../factory/reports.md`](../factory/reports.md),
  [`../techniques/sql-technique-backlog.md`](../techniques/sql-technique-backlog.md),
  [`../techniques/method-vs-recipe.md`](../techniques/method-vs-recipe.md),
  [`../attempt-ledger.md`](../attempt-ledger.md),
  [`advanced-ml-systems-eval.md`](advanced-ml-systems-eval.md) (LLM-as-judge,
  perplexity, contamination), and [`coverage-map.md`](coverage-map.md) for how
  every eval surface in the repo maps back to this module.
- **Factory consequence:** this *is* the factory consequence. Everything upstream
  exists to feed a decision that is honest about deltas, regressions, and cost.
  Design the next SQL recipe with target, data, verifiable reward/eval, stop
  rule, and report fields, and you have passed this module's mastery gate.
