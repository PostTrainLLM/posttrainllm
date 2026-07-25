## Context

posttrainllm already defines a factory-run folder, Swift IO types, publish checks, Markdown reports, and an `/artifacts` surface. The gap is not another evaluator; it is a stable, portable proof contract that joins those records and makes missing or historical evidence as legible as measured wins. The work must stay metadata-only and respect the project's ban on unapproved long GPU loops.

## Goals / Non-Goals

**Goals:**

- Compile existing canonical run evidence into one versioned report-card payload.
- Preserve before/after, regression, performance, leakage, provenance, and decision semantics.
- Render honest public examples across successful and failed outcomes.
- Keep the format usable by third parties without training hardware.

**Non-Goals:**

- Running training, model generation, evaluation, or performance benchmarks.
- Uploading weights or changing Hugging Face release policy.
- A hosted GPU evaluation service.
- Replacing canonical factory-run source artifacts with a second source of truth.

## Decisions

### Make the report card a derived artifact

The compiler reads the existing factory-run folder and emits a versioned report-card JSON payload plus static rendering. Source fragments remain canonical; the report card records per-field provenance and compiler version.

Alternative considered: extend `report.md` until it serves every use case. Rejected because prose is difficult to validate, consume programmatically, or compare across runs.

### Add explicit measurement-state wrappers

Every numeric or categorical observation carries a state: measured, derived, historical, skipped, missing, or not-applicable. Values with weaker provenance cannot accidentally render like current measurements.

Alternative considered: use nullable fields plus footnotes. Rejected because `null` cannot distinguish skipped work, historical imports, unavailable hardware metrics, and inapplicable checks.

### Align with existing factory contracts

The report-card schema maps from `FactoryRunFolder`, current decision vocabulary, `slice-metrics.json`, `trace_review.md`, and publish-check rules. Shared concepts are extended in the pure IO target so CLI and website code do not load MLX or checkpoints.

Alternative considered: implement a standalone Python-only schema. Rejected because it would drift from the Swift CLI's canonical validation boundary.

### Keep compilation deterministic and offline

No report-card step calls an LLM, model server, registry, or benchmark. Static HTML and JSON are rendered from validated local inputs; external evidence is represented by recorded links and hashes.

Alternative considered: use an LLM to summarize lessons. Rejected because public proof must be reproducible and source-bounded.

### Layer report-card checks onto publish-check

The existing factory publish check remains authoritative for run completeness. A report-card validator adds schema version, measurement states, source mappings, leakage/frontier disclosure, decision consistency, and safe static rendering. Report-only artifacts are allowed when evidence is complete and the non-ship label is explicit.

Alternative considered: replace existing publish-check with a new command. Rejected because it would duplicate mature enforcement and disrupt current artifact flows.

### Dogfood across outcome classes

Initial fixtures and public examples cover the file-ops routed specialist, ReST release, SQL report-only/retry results, at least one rejected candidate, and a historical-evidence artifact. The schema is not declared canonical until those cases render without hiding caveats.

Alternative considered: design around the cleanest successful run only. Rejected because the project's marketing advantage is honest decision quality, including failures.

## Risks / Trade-offs

- [Schema duplicates factory concepts] → Generate/map through the existing pure IO types and add cross-contract fixtures.
- [Legacy runs lack mandatory evidence] → Preserve historical/missing states and prohibit verified-ship language where provenance is incomplete.
- [A polished report hides regressions] → Keep target and regression gates adjacent and make the canonical decision prominent.
- [Static pages drift from JSON] → Render both from one payload and snapshot-test representative outcome classes.
- [Scope triggers expensive reruns] → Implementation tasks explicitly prohibit training/eval execution; new measurements remain operator-owned follow-up.

## Migration Plan

1. Define the report-card schema and measurement-state types alongside current factory IO contracts.
2. Implement fixture-backed mapping and validation over existing run folders.
3. Add deterministic JSON and static report renderers plus a CLI build command.
4. Compile and review the initial outcome-diverse dogfood cohort without rerunning models.
5. Link validated report cards from `/artifacts` and make the format canonical only after review.

Rollback removes the derived artifacts and links; canonical factory-run folders and existing reports remain unchanged.

## Open Questions

- Should the static renderer remain in the current web stack or be emitted entirely by the CLI?
- Which historical runs have enough hashes and command provenance to be more than illustrative examples?
- Should cost use only observed dollar cost, or also expose compute-time and energy proxies as separate measured fields?
