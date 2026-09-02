# Verified-win experiment manifests

These manifests preregister the four bounded experiments in Issue #138. They
separate a reviewed design from an executable run freeze:

```bash
python3 scripts/experiments/validate_verified_win_manifest.py \
  evals/verified-wins/*.json --stage design

python3 scripts/experiments/validate_verified_win_manifest.py \
  evals/verified-wins/*.json --stage run
```

`design` requires a paired comparison, an independent replicate unit,
randomization/blocking, explicit win/safety/resource gates, and a stop rule.
`run` additionally requires immutable arm revisions, fixture paths and SHA-256
digests, executable commands, and no open freeze requirements. A design-stage
pass is not permission or evidence that a run happened.

Raw outputs belong under each manifest's `raw_receipt_dir`. A result can use
only one of the manifest's four decisions: `promote`, `reject`,
`retry-protocol`, or `advance-model-class`.

## Current execution state

| Lane | State | Decision | Tracked result |
|---|---|---|---|
| WebGPU training | completed | `promote` | `webgpu-paired-result-v1.json` |
| Browser Parakeet vs native WhisperKit | completed | `reject` — quality/native-latency win, 50x short-clip gate miss | `parakeet-asr-result-v1.json` |
| ReST requalification | design-frozen | pending | — |
| Needle successor | design-frozen | pending | — |
