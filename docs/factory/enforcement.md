# Factory Enforcement

World-class docs are not enough by themselves. posttrainllm needs validators that
refuse weak artifacts.

## Enforcement Layers

| Layer | Tool | What It Checks |
|---|---|---|
| Run bundle schema | `posttrainllm factory-run validate runs/<id>` | Core typed JSON bundle: config, dataset, baseline, candidate, decision, optional artifact |
| Publish evidence | `posttrainllm factory-run publish-check runs/<id>` | Required evidence files, report sections, slice metrics, trace review, decision, ship/package constraints |
| Portable publish smoke | `python3 scripts/check_factory_run_publish.py runs/<id>` | Same policy in a no-build Python checker for CI/smokes |
| Report-card publication | `python3 scripts/check_fine_tune_report_card.py <card>.json` | Derived-artifact layer: schema version, measurement states and provenance, decision/label consistency, frontier-ceiling and frozen-eval disclosure, leakage policy, routed-use disclosure, public safety, static-page accessibility |
| Report-card drift | `python3 scripts/publish_report_cards.py --check` | Committed public cards still match a fresh offline compile |
| Target-specific smokes | `evals/*-smoke.sh` | No-GPU fixture checks for scripts and report helpers |
| Public artifact review | `docs/factory/public-artifacts.md` | Human-readable release state, blockers, competition context |

## Publish Check

Report-only artifacts may have blockers, but they still need evidence:

```bash
posttrainllm factory-run publish-check --allow-report-only runs/<id>
```

Shipped artifacts are stricter:

```bash
posttrainllm factory-run publish-check runs/<id>
```

For `decision=ship`, the check requires:

- `artifact.json`
- `artifact.shipped=true`
- `artifact.package_dir`
- no blockers in `decision.blocked_by`

For every run, the check requires:

- baseline and candidate JSON
- dataset manifest
- train log
- report
- `slice-metrics.json`
- `trace_review.md`
- `provenance.json`
- report sections for decision, target, data, eval, performance, failures, and
  next action

## Report Card Layer

The report-card checker layers on top of publish-check rather than replacing it:
publish-check stays authoritative for run completeness, and the report-card gate
adds the derived-artifact rules (states, provenance, decision consistency,
leakage, safe rendering). See [`report-card.md`](report-card.md#publication-gate)
for the exact rules and [`report-card-cohort.md`](report-card-cohort.md) for what
they rejected in practice.

Both layers fail closed. On failure the compiler writes no artifact at all, so a
weak card cannot reach `/artifacts` by accident.

## Current Gap

The native strict check exists, and the Python checker remains as a portable
smoke. A later cleanup can remove duplication by making the Python checker call
the native binary in CI once the build is cheap enough everywhere.

The report-card layer has the mirror shape: Python is the runnable CLI and
`native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift` is the typed schema
boundary, decoded against real compiler output by
`evals/fine-tune-report-card-smoke.sh`. Wiring it into a `posttrainllm
factory-run report-card` subcommand is deferred — that target pulls MLX, so it
is only verifiable behind a full package build.
