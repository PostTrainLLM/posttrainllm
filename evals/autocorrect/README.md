# Autocorrect foundation v1

This directory is the committed, no-model foundation for
`build-mac-local-autocorrect-specialist`.

## Frozen artifacts

- `protocol-v1.json` — text-to-text contract, protected spans, language,
  maximum input size, and non-goals.
- `taxonomy-v1.json` — supported keyboard errors and qualitative failures.
- `thresholds-v1.json` — quality, regression, resource, energy, and stop gates.
- `sources-v1.json` + `source-documents-v1.jsonl` — consented original,
  MIT-licensed tiny source with a content-hash revision. It is a smoke corpus,
  not representative natural-error evidence.
- `eval-v1.jsonl` — 12 manually reviewed original error rows and 6 clean
  controls covering rare words, names, numbers, URLs, Unicode, whitespace,
  casing, punctuation, and code-like spans.
- `keyboard-mac-us-ansi-v1.json` + `corruption-config-v1.json` — versioned
  physical layout and training-only corruption prior.
- `simulator-cases-v1.json` — deterministic expected edit traces for every
  error family and a clean control.
- `tiny-overfit-manifest-v1.json` and `pilot-manifest-v1.json` — bounded,
  source-first manifests. They materialize to 3,321 and 6,981 UTF-8 bytes,
  respectively; neither contains a test source.
- `distribution-report-v1.json` — comparison of the reviewed error fixture
  with 256 deterministic weighted simulator rows.
- `apple-autocorrect-assessment-v1.json` — local SDK evidence that Apple
  autocorrect is an observational, non-equivalent comparator for v1.
- `frontier-predictions-codex-v1.jsonl` +
  `frontier-calibration-v1.json` — the approved-text-scope Codex calibration,
  including immutable fixture/prediction hashes, invocation provenance, and
  measured perfect preservation on this smoke ruler.
- `base-bakeoff-v1.json` — complete offline predictions, tokenizer and timing
  rows, strict slice metrics, runtime pins, and the measured FLAN-T5-small
  base-selection decision.

## No-model checks

```bash
python3 scripts/autocorrect_foundation.py validate
python3 tests/test_autocorrect_foundation.py
bash evals/autocorrect-foundation-smoke.sh
```

Score a strict prediction file containing exactly one
`{"id": "...", "prediction": "..."}` object per row:

```bash
python3 scripts/autocorrect_foundation.py evaluate \
  --predictions evals/autocorrect/oracle-predictions-v1.jsonl
```

The validator fails on incomplete source provenance, source-derived split
leakage, exact or NFKC/case/whitespace-normalized cross-split overlap, lexical
holdout leakage, hash drift, non-reproducible manifests, trace drift, or a
changed distribution report.
