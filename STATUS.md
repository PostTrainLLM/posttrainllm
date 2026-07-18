# Status

Last updated: 2026-07-18

> Short current view. For the deep project state and active gaps, see
> [`PROJECT_STATUS.md`](./PROJECT_STATUS.md). For the current queue and
> sequencing, see [`docs/NEXT.md`](./docs/NEXT.md). For how the docs are
> labelled (active / evidence / reference / learning), see
> [`docs/doc-status.md`](./docs/doc-status.md).

## Current objective

Run the Mac-local specialist factory loop end-to-end and keep it honest:
`target → data → post-training → eval → package → report`. Priority is
correctness, measured evidence, and learning over output quality or shipping.
posttrainllm is a development-time factory and eval lab for Pace — Pace
production must never depend on `posttrainllm serve`, localhost, or this
repo's dev runtime.

## Active work

- **Factory loop hardening** — two specialist packages are registered:
  `qwen3-4b-file-ops-distilled` (file-ops gate 58% → 100%, but out-of-domain
  breadth regressed 59.6% → 42.3%, so routed-only) and `qwen3-4b-rest-fused`
  (retains 100% file-ops gate, raises breadth to ~65%; ships as a research
  specialist, not a Pace default).
- **Documentation consolidation** — this knowledge system, with a
  `doc-status.md` registry separating active factory docs from historical
  roadmap material (in progress; see the docs branch).

## Blockers

- **Missing historical evidence for `qwen3-4b-rest-fused`** — historical
  latency/RAM/tok-s and raw trace logs were not preserved; the ship decision
  promotes existing measured evidence and explicitly discloses the gap rather
  than recreating it.

## Unresolved questions

- Which specialist (if any) becomes a Pace default vs. staying routed/research-only?
- How is the single-machine ↔ distributed boundary best captured as a durable
  learning artifact (a stated north-star, not yet a doc)?
- Blume docs-site publication target: `docs.posttrainllm.com` is recommended in
  `docs-site/blume.config.ts` but not yet published.

## Next steps

See [`docs/NEXT.md`](./docs/NEXT.md) for the authoritative queue and sequencing.
