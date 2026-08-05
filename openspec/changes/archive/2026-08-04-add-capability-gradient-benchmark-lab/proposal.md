## Why

posttrainllm targets a 30-50M Mac-local specialist. Before any specialist
training is allowed, the chosen benchmark must prove a **capability gradient**:
a pinned frontier LLM materially beats a valid random/legal executor on the
same task. If the ruler cannot separate reasoning from chance, any specialist
score on it is noise — exactly the failure mode AGENTS.md warns about for
hermes-fc (frontier ~12%, ungroundable golds).

Character-only 2048 has now failed its separate development gradient screen:
pinned Sonnet matched random legal play and partial pinned Opus evidence stayed
below the admission margin. It is rejected before specialist training. This
change searches for a better ruler without pretending an alternative is
already admitted.

This change builds that alternative bench: a candidate lab that ranks six-plus
deterministic text-only tasks, each with a full state/action protocol, legal
random executor, intelligence-sensitive metric, deterministic verifier,
leakage plan, 30-50M fit estimate, frontier eval cost, and explicit reject
condition. It then implements dependency-free Python reference environments
for two non-overlapping candidates so their baseline claims can be measured
before any frontier call. Reference implementation is not benchmark admission.

## What Changes

- Define a machine-readable candidate scorecard that ranks eight deterministic
  text-only tasks (five game-like, three everyday-action), distinguishes
  measured baselines from projections, and separately records the hypothesis
  that a 30-50M specialist could beat a larger LLM.
- Implement dependency-free Python reference environments and harnesses for
  the two selected candidates (Connect-4 and calendar scheduling): seeded
  reset/step, legal action enumeration, canonical traces, random-legal
  baseline, compact fixtures, and a deterministic verifier for each.
- Add a small Devin-authored, GLM-assisted development probe set for each selected candidate.
  Every probe is mechanically verifiable by the environment's own verifier,
  marked development-only, carries provenance, and creates no specialist
  training labels or frozen evaluation material.
- Add focused offline tests and a no-model smoke script that exercise reset
  determinism, legal-action correctness, random-legal baseline behavior,
  canonical-trace replay, verifier accept/reject, probe validation, scorecard
  consistency, and exact 2,000-seed baseline-claim replay.
- Record the remaining blockers before any cloud model run, training run, or
  public benchmark claim.

## Capabilities

### New Capabilities

- `capability-gradient-benchmark-lab`: A no-model lab that ranks deterministic
  text-only benchmark candidates for a 30-50M specialist, implements reference
  environments for two non-overlapping candidates, and provides the local
  boundary required before a frontier-vs-random gradient screen.

### Modified Capabilities

None. The existing `everyday-specialist-benchmark` cohort comparison, factory
evals, report cards, and `decision.json` authority are unchanged. Qualified
candidates from this lab may later feed into the everyday benchmark as
additional task families, but that promotion is a separate change.

## Impact

The change adds benchmark candidate configs, reference environment code, dev
probes, tests, and a smoke script. It does not train a model, call a cloud
API, load a checkpoint, run a long benchmark, install a dependency, commit,
push, deploy, or touch frozen evaluation material. All code is stdlib-only
Python. The scorecard and environments are additive; rollback removes them
without affecting any existing surface.
