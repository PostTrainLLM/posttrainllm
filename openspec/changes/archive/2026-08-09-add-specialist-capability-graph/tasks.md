## 1. Graph contract and compatibility

- [x] 1.1 Define the versioned graph schema for node kinds, capability/schema
  envelopes, typed edges, verifier policies, resource evidence, privacy class,
  fallbacks, and future non-executable composition metadata
- [x] 1.2 Add valid and adversarial fixtures for dangling ids, duplicate ids,
  executable cycles, incompatible schemas, unverified acceptance, missing safe
  terminal behavior, unsupported claims, and credential/private-data leakage
- [x] 1.3 Implement a fail-closed validator that references the existing flat
  registry without changing graph-unaware package consumers

## 2. Development graph and dry-run routing

- [x] 2.1 Add an explicitly non-production development graph referencing the
  Pace router, registered file-ops specialists, a broader local placeholder,
  deterministic fixture verifiers, and a disabled external tier without making
  new quality claims
- [x] 2.2 Implement deterministic eligibility and policy filtering for
  capability, schema, operating envelope, OOD/route confidence, installed
  state, privacy/network authorization, quality floor, and resource budgets
- [x] 2.3 Add graph validate/inspect/dry-run CLI surfaces that report candidates,
  exclusions, ordered route, fallback path, and estimated residency without
  loading a model

## 3. Verified bounded cascade

- [x] 3.1 Implement structural, executable/final-state, and separately versioned
  learned-verifier interfaces with deterministic fixture adapters
- [x] 3.2 Implement one-leaf plus ordered-fallback execution with typed timeout,
  load, output, verifier, privacy, network, hop, latency, resource, and cost
  failures
- [x] 3.3 Enforce disjoint accepted-result and safe-failure terminal types so a
  rejected answer cannot leak through on exhaustion
- [x] 3.4 Require explicit operator policy and existing external authorization
  before an external node can execute; keep all credentials outside graph data

## 4. Tracing and residency

- [x] 4.1 Emit privacy-safe dry-run and execution traces with graph/policy hashes,
  candidates, filter reasons, route confidence, load state, verifier outcomes,
  escalation reasons, budgets, resource/cost evidence, and terminal outcome
- [x] 4.2 Implement bounded LRU residency metadata/policy and distinguish active
  parameters, loaded bytes, resident bytes, installed bytes, shared base,
  adapter bytes, and cold/warm latency
- [x] 4.3 Prove that residency preference cannot override capability, privacy,
  verification, or quality-floor constraints

## 5. Benchmark integration

- [x] 5.1 Add an Everyday Specialist Benchmark system adapter that binds graph,
  policy, node/package, verifier, and trace revisions to each task result
- [x] 5.2 Report route regret, false acceptance, escalation precision/recall,
  over-escalation, hop/tier distribution, complete end-to-end latency,
  residency, active parameters, installed bytes, and external calls/cost
- [x] 5.3 Reject system qualification when end-to-end gates fail even if one or
  more individual specialist nodes have strong standalone scores

## 6. Verification and handoff

- [x] 6.1 Add focused unit and no-model smoke coverage for graph validation,
  deterministic routing, low-confidence bypass, verifier fallback, timeout/load
  failure, policy blocking, exhaustion, privacy, and resource accounting
- [x] 6.2 Run the smallest relevant offline checks and strict OpenSpec
  validation; do not run live multi-model loading, training, sustained
  benchmarks, external calls, or deployment without separate operator approval
- [x] 6.3 Update active navigation/status only after a measured system result
  ships, archive this change, and close the linked GitHub issue through the
  normal PR lifecycle
