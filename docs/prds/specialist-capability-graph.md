---
title: "Specialist capability graph and verified cascade"
---

<!-- PRD metadata (kept outside frontmatter for Blume compatibility) -->
**status:** proposed
**owner:** unassigned
**created:** 2026-08-03
**openspec:** `openspec/changes/add-specialist-capability-graph/`
**github_issue:** [#78](https://github.com/PostTrainLLM/posttrainllm/issues/78)
**related_prds:** B2-B7-router-family.md, B5-cloud-escalate-training.md,
B31-gallery-and-project-pins.md, everyday-specialist-benchmark.md

# PRD — Specialist Capability Graph and Verified Cascade

## Goal

Turn the flat specialist package registry into a validated capability graph
that can route a request to the smallest eligible specialist, verify the
result, and escalate through broader local models to an optional frontier tier
when the result is invalid, out of distribution, or insufficiently trusted.

The product claim is a system claim, not merely a directory claim:

> Many independently measurable specialists can behave like one dependable
> local intelligence surface because routing, verification, and fallback are
> explicit and benchmarked.

## Why a graph, not a strict tree

A tree is useful for visualizing broad-to-narrow capability, but everyday tasks
overlap. “Read this message and schedule the proposed meeting” touches message
understanding, calendar normalization, policy, and action execution. A directed
capability graph permits shared parents and future composition without
duplicating models.

V1 execution remains intentionally simpler: select one leaf and follow one
bounded fallback chain. Multi-specialist decomposition is represented in the
schema but stays disabled until single-route cascades are correct and measured.

## Existing foundation

- `specialists/registry.json` already registers model artifacts and records
  intended and prohibited use.
- `pace-intent-router-v8` demonstrates a small from-scratch routing specialist.
- B2/B7 specifies tool and specialist routing, but explicitly leaves production
  multi-specialist serving downstream.
- B5 specifies a learned two-tier local-to-cloud signal, but explicitly excludes
  multi-tier escalation.
- `posttrainllm agent --cloud-escalate` and `eval-escalate` provide runtime and
  evaluation primitives.
- The SQL attempt ledger records that input-aware routing preserved two
  conflicting capabilities where naive data mixing and static LoRA composition
  failed.

This PRD composes those pieces. It does not replace their task-specific
training or bake-off work.

## Users and decisions

1. **Operator:** Which models are installed, trusted, and eligible for this
   request under a latency/RAM/privacy policy?
2. **Factory:** Where does a newly shipped specialist attach, and what evidence
   is required before the graph can route to it?
3. **Runtime:** When should a small specialist be skipped, accepted, retried,
   or escalated?
4. **Evaluator:** Does the whole graph outperform the best single model after
   router errors and system overhead are counted?

## Graph contract

Keep `specialists/registry.json` as package identity and artifact authority.
Add a separate versioned capability graph that references registered package
ids instead of copying their model cards or lock data.

Each node declares:

- stable node id and kind: `router`, `specialist`, `generalist`, `verifier`, or
  `external-fallback`;
- package id or explicit runtime id;
- capability ids and accepted input/output schemas;
- task and eval versions that establish its operating envelope;
- minimum route confidence and out-of-distribution behavior;
- verifier ids and acceptance policy;
- fallback targets and terminal behavior;
- privacy class and network eligibility;
- known failure classes and prohibited use;
- measured warm/cold latency, peak RSS, active parameters, and artifact bytes;
- evidence state for every measurement and source artifact hashes.

Edges declare one relationship:

- `routes-to`: router eligibility;
- `fallback-to`: ordered escalation;
- `verified-by`: acceptance dependency;
- `composes-with`: declared future composition, ignored by the V1 executor.

## Graph validation

The validator fails closed on:

- duplicate or dangling node/package ids;
- cycles in `fallback-to` edges;
- a non-terminal node with no valid fallback or safe failure response;
- specialist nodes without an operating-envelope eval and prohibited-use list;
- acceptance policies with no verifier or explicit deterministic success rule;
- external fallbacks lacking an operator opt-in boundary;
- incompatible request/response schemas along an edge;
- resource claims without measurement state and provenance;
- graph fixtures that embed credentials, private prompts, or request payloads.

The graph may contain cycles in future composition metadata only after a
separate execution contract exists; V1 rejects all executable cycles.

## Routing and cascade policy

1. A router produces ranked eligible nodes, route confidence, and an explicit
   out-of-distribution score or class.
2. Policy filters candidates by installed state, privacy/network permission,
   resource budget, and capability/schema compatibility.
3. The smallest eligible node that satisfies the configured quality floor is
   attempted; ties prefer measured lower end-to-end cost.
4. A declared verifier evaluates the output or resulting environment state.
5. The result is returned only if its acceptance policy passes.
6. Route uncertainty, verifier rejection, load failure, timeout, or policy
   refusal advances to the ordered fallback.
7. Execution stops at the first accepted result or a configured maximum hop,
   latency, energy, or external-cost budget.
8. Exhaustion returns a typed safe failure; it never silently returns the last
   rejected answer.

Model self-confidence may contribute to routing but cannot be the sole
acceptance signal for a generative result. Prefer schema validation, execution,
final-state comparison, or a separately calibrated verifier.

## Runtime surface

V1 adds a no-surprises CLI/runtime surface equivalent to:

```bash
posttrainllm graph validate specialists/capability-graph.json
posttrainllm graph inspect --capability file-ops
posttrainllm cascade \
  --graph specialists/capability-graph.json \
  --request request.json \
  --policy local-only \
  --trace-out cascade-trace.json
```

The exact command grouping may follow existing CLI conventions during
implementation. A dry-run returns the eligible path and estimated resource
envelope without loading a model.

## Verification classes

V1 supports three explicit verifier classes:

1. **Structural:** schema, grammar, type, or policy validation.
2. **Executable:** code/test, filesystem state, database state, or deterministic
   domain checker.
3. **Calibrated learned verifier:** separately versioned model with held-out
   selective-risk evidence.

An LLM-as-judge result may be recorded as advisory evidence but cannot by
itself upgrade a result to deterministic verification.

## Trace and observability

Every request emits a bounded machine-readable trace containing:

- graph and policy revision;
- request schema/capability metadata, with content redacted by default;
- candidates considered and policy-filter reasons;
- selected node, route confidence, and cold/warm load state;
- verifier result and failure class;
- escalation reason and next node;
- per-hop and total latency/resource/cost evidence;
- final accepted node or typed exhaustion.

Private request text, tool results, and model outputs stay local unless an
explicit publication policy permits them. Public receipts contain hashes and
aggregates only.

## Model residency and storage

The directory must distinguish:

- active parameters for the current request;
- resident bytes in the process;
- total installed artifact bytes;
- shared-base bytes versus task-specific adapter bytes;
- cold-load and adapter-swap cost.

V1 uses a bounded LRU residency policy and does not assume every specialist is
simultaneously resident. The policy may prefer a resident node only inside a
declared quality tolerance; residency must never silently override the quality
floor.

Independent small checkpoints and shared-base adapters are both valid nodes.
The benchmark, not architectural preference, decides which produces the better
quality/resource frontier.

## Benchmark integration

The capability graph competes in the `system` track of the Everyday Specialist
Benchmark. A system result is invalid unless it includes:

- the graph and policy hash;
- all invoked node/package revisions;
- route accuracy/regret;
- false accepts and escalation precision/recall;
- hop and tier distribution;
- cold and warm end-to-end latency;
- peak resident memory, active parameters, and installed bytes;
- external calls and cost.

Per-leaf accuracy is useful diagnostic evidence but cannot substitute for the
end-to-end system result.

## Migration and compatibility

1. Introduce the graph as a separate additive file referencing the current
   registry.
2. Generate a development graph containing the Pace intent router, registered
   file-ops specialist, a local generalist placeholder, deterministic fixture
   verifiers, and an explicitly disabled external fallback.
3. Keep all current package consumers working without graph awareness.
4. Enable runtime execution only after schema and mock-cascade smokes pass.
5. Do not enable production Pace routing or network fallback through this
   repository change.

## Acceptance criteria

- [ ] A versioned capability-graph schema and validator reject cycles,
  dangling nodes, incompatible schemas, unverified acceptance, missing terminal
  behavior, and credential/private-payload leakage.
- [ ] Existing `specialists/registry.json` packages remain valid and unchanged
  for graph-unaware consumers.
- [ ] A checked-in development graph references at least two registered
  specialists, one broader local fallback, fixture verifiers, and a disabled
  external tier without making new quality claims.
- [ ] Dry-run deterministically reports the eligible route, exclusions, budget,
  and estimated residency without loading a model.
- [ ] A no-model cascade smoke proves leaf acceptance, router bypass on low
  confidence, verifier-driven fallback, timeout/load failure fallback, budget
  exhaustion, and safe terminal failure.
- [ ] Rejected outputs are never returned merely because the chain exhausted.
- [ ] Cascade traces are privacy-safe by default and include all fields required
  by the Everyday Specialist Benchmark system track.
- [ ] Cold/warm latency, active parameters, resident bytes, installed bytes,
  hop count, false accepts, and escalation metrics are reported distinctly.
- [ ] External/cloud execution requires explicit operator opt-in and reuses
  existing credential boundaries without storing secrets in graph files.
- [ ] Focused schema/CLI/smoke checks pass without model loading, training,
  sustained benchmarks, network calls, or deployment.

## Delivery sequence

1. Freeze graph schema, validator, and additive registry references.
2. Build deterministic dry-run route selection and policy filtering.
3. Add mock execution, verifier acceptance, and bounded fallback.
4. Add privacy-safe cascade traces and residency accounting.
5. Connect the graph to the benchmark system-track adapter.
6. Only after a measured system win, consider live multi-model loading,
   adapter hot-swap optimization, or production-app integration.

## Out of scope

- Training the B2/B7 router or B5 escalation signal in this infrastructure
  change.
- Token-level MoE, weight merging, or per-layer adapter composition.
- Multi-specialist task decomposition or parallel debate in V1.
- Automatic downloading, deleting, or updating model artifacts.
- Automatic cloud calls, credential management, paid evaluation, or deploy.
- Pace production integration.
- Claiming the graph is better than a single model before the benchmark passes.

## Dependencies and coordination

- B2/B7 remains the task-specific router bake-off and training plan.
- B5 remains the learned local-to-cloud supervision plan.
- The flat registry and package locks remain artifact authority.
- The Everyday Specialist Benchmark owns cross-system scoring and cannot be
  weakened to make the graph pass.
- Do not modify the active autocorrect OpenSpec or its frozen eval.

## References

- [RouteLLM](https://arxiv.org/abs/2406.18665)
- [FrugalGPT](https://arxiv.org/abs/2305.05176)
- [RouterBench](https://openreview.net/forum?id=IVXmV8Uxwh)
- [Model MoErging survey](https://openreview.net/forum?id=u0azVc9Y0y)
- [Compress then Serve](https://openreview.net/forum?id=3XMA8RDJu2)
