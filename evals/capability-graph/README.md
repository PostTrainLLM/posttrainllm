# Capability graph V1

This is dependency-free, no-model infrastructure for issue #78. It validates a
development-only specialist graph, filters candidates under an explicit policy,
simulates a bounded verified fallback chain, and adapts its trace to the
Everyday Specialist Benchmark system contract.

It does not load weights, call a provider, train, install artifacts, or change
the flat specialist registry. The checked-in graph references the registry and
makes no new model-quality claim.

## Surfaces

- `specialists/capability-graph.json`: additive development graph.
- `configs/specialist-capability-graph.schema.json`: allowed node, edge,
  verifier, measurement, and failure vocabularies.
- `configs/capability-graph/policies/local-only-v1.json`: local-only eligibility,
  resource, hop, latency, and external-use policy.
- `configs/capability-graph/system-gates-v1.json`: fail-closed end-to-end
  qualification gates; strong leaf scores cannot qualify a weak routed system.
- `scripts/capability_graph.py`: validate, inspect, dry-run, fixture cascade,
  and benchmark-adapter CLI.
- `evals/capability-graph/fixtures/`: metadata-only request, install, router,
  and verifier outcome fixtures.

## Commands

```bash
python3 scripts/capability_graph.py validate
python3 scripts/capability_graph.py inspect --capability file-ops
python3 scripts/capability_graph.py dry-run \
  --request evals/capability-graph/fixtures/request-file-ops-v1.json \
  --installed evals/capability-graph/fixtures/installed-v1.json \
  --router-output evals/capability-graph/fixtures/router-file-ops-v1.json
bash evals/capability-graph-smoke.sh
```

External fallback is disabled in both the graph and the default policy. A test
can enable it only when the node, network policy, external policy, request
authorization, call budget, and cost budget are all explicit; the test still
uses a deterministic fixture and performs no network call.

The first separately approved measured system run is committed as
`pace-intent-apple-calibration-v1.json`. It correctly rejects qualification:
zero of 1,560 frozen threshold candidates passed, and even a perfect router over
the measured 60.7% specialist and 85.7% fallback would reach only 96.4% against
the 99% final-accuracy gate. The graph infrastructure ships; the rejected
development system is not promoted into a production or benchmark headline.
