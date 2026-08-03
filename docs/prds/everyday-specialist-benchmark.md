---
title: "Everyday specialist benchmark"
---

<!-- PRD metadata (kept outside frontmatter for Blume compatibility) -->
**status:** proposed
**owner:** unassigned
**created:** 2026-08-03
**openspec:** `openspec/changes/add-everyday-specialist-benchmark/`
**github_issue:** [#77](https://github.com/PostTrainLLM/posttrainllm/issues/77)
**related_prds:** B23-agent-eval-protocol.md, B32-eval-ci-gate.md,
B9-energy-per-token.md, B2-B7-router-family.md,
specialist-capability-graph.md

# PRD — Everyday Specialist Benchmark

## Goal

Create a public, reproducible benchmark of narrow everyday digital tasks where
Mac-local task specialists, general-purpose frontier models, adapted open
models, and routed systems compete on the same verifiable outcomes.

The benchmark should make the project's north-star legible in one line:

> Retain frontier-level capability on a bounded task while using a fraction of
> the active parameters, latency, RAM, energy, and cost.

The benchmark is not a claim that a small specialist is generally more capable
than a frontier model. Every result must disclose its task boundary, training
access, regression behavior, and escalation policy.

## Why now

- The existing browser leaderboard proves deterministic evaluation for
  100K–100M-parameter models, but its launch tasks are toy algorithmic or
  perplexity tasks rather than everyday user outcomes.
- `pace-intent-router-v8` is already a strong proof-shaped artifact: a 49.5M
  specialist with a recorded narrow-task win over larger generalists. Its
  current comparisons use synthetic data and different sample counts, so they
  are not yet the shared sealed head-to-head this benchmark requires.
- Fine-tune report cards compare one candidate with its baseline, but there is
  no cohort contract for comparing generalists, adapted specialists, and full
  routed systems on identical task instances.
- The proposed specialist capability graph needs an independent system-level
  ruler. Otherwise routing can improve a curated slice while hiding false
  accepts, cold-start cost, or excessive escalation.

## Users and decisions

The benchmark serves three decisions:

1. **Operator:** Is this specialist worth installing and routing to on a Mac?
2. **Model builder:** Which base, data, or post-training recipe produces the
   best capability-retention/resource trade-off for this task?
3. **System builder:** Does a specialist cascade beat the best single model
   after router mistakes, verification, loading, and fallback are included?

## Benchmark principles

1. **Outcome over prose.** Prefer exact schemas, executable checks, or final
   environment state over LLM-as-judge scoring.
2. **Same ruler.** All entries in a comparison use the same task instances,
   tool surface, budgets, and scorer version.
3. **Frontier-calibrated.** A task is reportable only after the declared
   frontier ceiling clears its near-perfect qualification threshold.
4. **Specialization is disclosed.** Training access and task-specific data are
   first-class track metadata, not footnotes.
5. **Reliability matters.** Repeated-run success and false acceptance are
   reported beside average accuracy.
6. **System costs count.** Routing, model loading, verification, retry, and
   escalation are included in end-to-end latency and resource measurements.
7. **No single magic score.** Publish quality/resource Pareto views and the
   underlying measurements; any summary index remains secondary.

## V1 task families

V1 defines the common contract for six families and publishes at least three
fully qualified families before calling the benchmark launched:

| Family | Example outcome | Preferred verifier |
|---|---|---|
| Intent and safe unknown routing | Choose the correct local, research, action, or unknown route | Exact class plus cost-weighted route-confusion matrix |
| Text correction with preservation | Correct typos without changing meaning, names, numbers, URLs, or casing constraints | Reference edits plus protected-span and unnecessary-edit checks |
| Calendar understanding | Create normalized event fields and identify explicit conflicts | Schema check plus deterministic calendar-state comparison |
| Local file operations | Produce or execute a bounded file plan in a sandbox | Final filesystem-state comparison |
| Table cleanup | Transform CSV rows, types, or formulas without losing records | Deterministic table diff and invariant checks |
| Distractor-heavy tool selection | Select and call the grounded tool or refuse when none applies | BFCL-style AST/semantic call matching |

A task family may remain `development` until its frontier gate, leakage check,
and deterministic scorer all pass. A family with an ambiguous or
frontier-failing ruler may be used for training but not for public ranking.

## Competition tracks

Every entry declares exactly one track:

| Track | Training/data access |
|---|---|
| `generalist` | No benchmark-specific training; public task instructions and permitted examples only |
| `adapted` | Benchmark training split allowed; training method, rows, compute, and base disclosed |
| `system` | Routers, specialists, verifiers, and fallbacks allowed; every invoked model and hop disclosed |

Leaderboards may filter by track. A task-adapted specialist must never be
presented as a zero-shot generalist win.

## Data and leakage contract

Each task has a versioned manifest containing:

- task id, version, lifecycle state, and capability boundary;
- public development fixtures and generator/scorer revisions;
- hidden-test custodian and evaluation protocol without storing secrets in the
  repository;
- permitted training sources and cutoff;
- prompt/tool/environment budget;
- primary, regression, and frontier qualification thresholds;
- overlap checks for prompts, normalized targets, and generator templates;
- distribution-shift mutations and protected slices.

Public development fixtures support local iteration. Official ranking uses a
sealed set or maintainer-held seeds and emits a signed, privacy-safe receipt.
After an evaluation window closes, a non-sensitive frozen slice may be
published for audit and replaced by a new sealed version.

## Runner and submission contract

The runner accepts a versioned entry manifest and one of:

- a local posttrainllm specialist package;
- a local OpenAI-compatible endpoint;
- an external-provider prediction JSONL produced outside the repository;
- a capability-graph system entry.

The repository must not store API keys or provider credentials. External calls
are operator-run and imported as evidence. A no-model fixture path proves the
runner and scorer without network access, model loading, or sustained compute.

Each run emits:

```text
benchmark-runs/<run-id>/
  run.json
  entry.json
  task-results.json
  resource-results.json
  routing-results.json       # system track only
  predictions.jsonl          # private by default; publish only when safe
  receipt.json
  report.md
```

Large or private outputs remain ignored/local. Public result receipts contain
only bounded evidence, hashes, aggregate slices, and replay instructions.

## Metrics

### Quality

- task success rate and per-slice success;
- repeated-run `pass^k` or equivalent reliability;
- frontier capability retained;
- parse, tool, execution, and policy error rates;
- primary-task and out-of-domain/regression results.

### Routing and verification

- false-accept rate: wrong specialist result returned without escalation;
- false-escalation and over-escalation rate;
- escalation recall on locally incorrect cases;
- route accuracy and route regret against the per-instance oracle;
- hop count and final tier distribution.

### Resources

- p50/p95 end-to-end latency, including cold load and retries;
- warm latency separately from cold latency;
- peak RSS and model/cache residency;
- active parameters and total installed artifact bytes;
- energy when measured by the existing Mac harness;
- local and external cost, training time, and eval time.

Missing measurements remain explicitly `missing`; they are never represented
as zero. The public view shows Pareto frontiers rather than hiding trade-offs in
one composite rank.

## Public surface

V1 produces deterministic JSON and a static benchmark report suitable for the
existing browser publication pipeline. The report includes:

- task and track filters;
- quality versus active parameters, latency, RAM, energy, and installed bytes;
- one comparison table where all headline entries share the same test set;
- failure and escalation slices;
- links to specialist model cards, report cards, and privacy-safe receipts.

Public deployment is a separate manual action. This PRD does not authorize a
site deploy.

## Acceptance criteria

- [ ] A versioned suite/task/entry/result schema validates good fixtures and
  rejects unknown versions, mismatched sample sets, missing track disclosure,
  and inconsistent metrics.
- [ ] At least three V1 task families have deterministic scorers, public dev
  fixtures, leakage checks, and a passing frontier-ceiling qualification.
- [ ] The same-instance comparison path runs a generalist, adapted, and system
  fixture through one scorer without silently changing prompts or budgets.
- [ ] System results report false accepts, escalation behavior, route regret,
  hop distribution, and complete end-to-end latency.
- [ ] Resource evidence distinguishes active parameters, resident memory, and
  installed artifact bytes, and distinguishes warm from cold latency.
- [ ] Repeated-run reliability and primary/regression slices appear in both
  machine-readable and rendered reports.
- [ ] The Pace intent benchmark is rerun on one shared, sealed, real-user-like
  set before its current cross-model numbers become a benchmark headline.
- [ ] No-model smokes cover runner, schema, scorer, receipt, and deterministic
  report generation without training, model loading, network calls, or deploy.

## Delivery sequence

1. Freeze schemas and one no-model intent-routing fixture.
2. Qualify the first real task and same-instance cross-model comparison.
3. Add two more deterministic everyday task families.
4. Integrate system/cascade traces and selective-risk metrics.
5. Publish the first static cohort after manual evidence review.

## Out of scope

- A universal intelligence or open-ended writing benchmark.
- GUI pixel-control, live websites, or long-running OSWorld-style environments
  in V1.
- Automated paid frontier calls, credential storage, or background evals.
- Training a new specialist as part of benchmark infrastructure work.
- Replacing BFCL, existing factory evals, fine-tune report cards, or
  `decision.json` authority.
- Production Pace routing or public deployment.

## Dependencies and coordination

- Reuse B23 repeated-pass/budget semantics and B32 gate behavior.
- Reuse the factory measurement-state and report-card conventions rather than
  inventing zero-filled resource fields.
- Reuse BFCL scorers where applicable.
- The capability graph consumes this benchmark contract; it must not weaken or
  special-case the scorer.
- Do not modify the active autocorrect OpenSpec or its frozen eval while
  implementing benchmark infrastructure.

## References

- [BFCL V4](https://gorilla.cs.berkeley.edu/leaderboard.html)
- [tau-bench](https://arxiv.org/abs/2406.12045)
- [WorkArena++](https://openreview.net/forum?id=PCjK8dqrWW)
- [AssistantBench](https://arxiv.org/abs/2407.15711)
