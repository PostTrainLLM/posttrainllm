## Why

posttrainllm already has a flat specialist registry, a fast intent router,
task/tool routing infrastructure, a two-tier cloud-escalation path, and measured
evidence that input-aware routing can preserve conflicting capabilities. It
does not yet have one validated directory that expresses capability boundaries,
verification, resource policy, and multi-tier fallback as an executable system.

Without that contract, a “forest” of tiny specialists remains a collection of
model cards: routing mistakes, false accepts, cold loads, and fallback behavior
cannot be evaluated or trusted end to end.

## What Changes

- Add an additive, versioned capability graph referencing existing specialist
  package ids without replacing `specialists/registry.json` authority.
- Model routers, specialists, generalists, verifiers, optional external
  fallbacks, and typed route/fallback/verification/composition edges.
- Validate graph integrity, operating-envelope evidence, compatible schemas,
  safe terminal behavior, privacy boundaries, and acyclic executable paths.
- Add deterministic dry-run routing plus a bounded V1 cascade: smallest eligible
  specialist, external verification, broader local fallback, and explicit
  opt-in external tier.
- Emit privacy-safe per-hop traces and distinguish active parameters, resident
  bytes, installed bytes, shared-base/adapters, and cold/warm latency.
- Evaluate the whole graph through the Everyday Specialist Benchmark `system`
  track, including false accepts, escalation behavior, route regret, and
  end-to-end cost.

## Capabilities

### New Capabilities

- `specialist-capability-graph`: Versioned specialist directory, verified
  routing, bounded multi-tier escalation, and resource-aware execution.

### Modified Capabilities

None. B2/B7 remains the task-specific router bake-off/training plan, B5 remains
the learned escalation-data plan, the flat specialist registry remains artifact
authority, and production Pace routing remains out of scope.

## Impact

The change adds a graph schema/config, validator, graph inspection/dry-run
surface, mockable cascade executor, verifier adapters, privacy-safe trace
contract, resource accounting, benchmark adapter, and focused no-model tests.
It does not train routers or specialists, automatically download or delete
models, call cloud providers without explicit operator opt-in, touch secrets,
change Pace production, deploy, or claim a system win before benchmark evidence.

Planning detail: `docs/prds/specialist-capability-graph.md`.
GitHub issue: [#78](https://github.com/PostTrainLLM/posttrainllm/issues/78).
