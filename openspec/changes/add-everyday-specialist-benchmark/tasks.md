## 1. Contract and fixtures

- [ ] 1.1 Define versioned suite, task, entry, run, result, resource, routing,
  and receipt schemas under the repo's config-as-source-of-truth convention
- [ ] 1.2 Add valid and adversarial synthetic fixtures for all three tracks,
  incompatible instance sets, missing disclosure, leakage, and inconsistent
  derived metrics
- [ ] 1.3 Implement a dependency-light validator that fails before writing a
  public receipt or report

## 2. Common runner and scoring

- [ ] 2.1 Implement a no-model runner interface for local packages,
  OpenAI-compatible endpoints, imported external predictions, and
  capability-graph system adapters without embedding provider credentials
- [ ] 2.2 Implement the first deterministic intent-routing task adapter with
  exact class, unknown/OOD, route-confusion, protected-slice, and repeated-pass
  scoring
- [ ] 2.3 Record same-instance identity, prompt/tool/environment budgets,
  per-instance timing, errors, and scorer outputs for every entry
- [ ] 2.4 Add system-trace aggregation for false accepts, escalation
  precision/recall, over-escalation, route regret, hops, and final tier

## 3. Resources and receipts

- [ ] 3.1 Add explicit measurement-state fields for cold/warm end-to-end
  latency, active parameters, resident bytes, installed bytes, energy,
  training/eval time, and local/external cost
- [ ] 3.2 Emit privacy-safe official receipts with instance-set hashes,
  frontier qualification, leakage checks, custody, provenance, and bounded
  aggregate evidence
- [ ] 3.3 Reject receipts containing credentials, private prompts, prohibited raw
  outputs, or unsupported claims

## 4. Qualification and cohort report

- [ ] 4.1 Freeze and frontier-qualify a shared Pace intent task using identical
  sealed instances for every headline model before publishing a win/loss claim
- [ ] 4.2 Qualify two additional V1 everyday families using existing
  deterministic scorers where possible; keep any frontier-failing ruler
  development/training-only
- [ ] 4.3 Compile validated results into deterministic JSON and a static report
  with task/track filters, slices, reliability, selective risk, and
  quality/resource Pareto views
- [ ] 4.4 Link benchmark entries to package model cards, report cards, and
  privacy-safe evidence without changing `decision.json` authority

## 5. Verification and handoff

- [ ] 5.1 Add focused unit and no-model smoke coverage for good runs, track
  disclosure, same-instance comparison, scorer failures, resource math,
  privacy, and deterministic rendering
- [ ] 5.2 Run the smallest relevant offline checks and strict OpenSpec
  validation; do not run training, heavy model evals, network providers, or
  deployment without separate operator approval
- [ ] 5.3 Update active navigation/status only after a qualified cohort ships,
  archive this change, and close the linked GitHub issue through the normal PR
  lifecycle
