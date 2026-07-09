# Factory Enforcement

World-class docs are not enough by themselves. posttrainllm needs validators that
refuse weak artifacts.

## Enforcement Layers

| Layer | Tool | What It Checks |
|---|---|---|
| Run bundle schema | `posttrainllm factory-run validate runs/<id>` | Core typed JSON bundle: config, dataset, baseline, candidate, decision, optional artifact |
| Publish evidence | `posttrainllm factory-run publish-check runs/<id>` | Required evidence files, report sections, slice metrics, trace review, decision, ship/package constraints |
| Portable publish smoke | `python3 scripts/check_factory_run_publish.py runs/<id>` | Same policy in a no-build Python checker for CI/smokes |
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

## Current Gap

The native strict check exists, and the Python checker remains as a portable
smoke. A later cleanup can remove duplication by making the Python checker call
the native binary in CI once the build is cheap enough everywhere.
