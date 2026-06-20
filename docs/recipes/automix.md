# Recipe — micro-AutoMixer for data-mix ratios (B21)

Stop hand-waving "50/30/20 code/web/math". `tinygpt automix` searches the
ratio: sample candidate mixes, score each with a short proxy train run, fit a
quadratic surrogate, and propose the next mix by predicted improvement until
gains fall below a threshold. Scaled down from Poolside's Laguna recipe;
[DoReMi](https://arxiv.org/abs/2305.10429) is the rigor target for V2.

## Run

```bash
tinygpt automix \
  --corpus code=stack.txt --corpus web=fineweb.txt --corpus math=meta.txt \
  --proxy-runs 6 --proxy-steps 2000 --max-iters 4 \
  --out automix-report.jsonl
```

Outputs:
- `automix-report.jsonl` — one row per proxy run: `{iter, source, score, ratio, predicted?}`
  (`source` is `sample` for the initial Dirichlet draws, `propose` for surrogate picks).
- `automix-recommendation.json` — `{ratio, best_score, runs, proxy_steps}`.

V1 scores by **negated final proxy-train loss**. Task-eval scoring (BFCL/GSM8K
via `run-lm-eval`) is the V2 extension; `--task` is reserved for it.

## Interpreting the report

- `score` rising across `propose` rows → the surrogate is finding better mixes.
- The run stops when the best predicted improvement drops below `--ei-threshold`
  (default 0) — i.e. the surrogate no longer expects a better mix than the best seen.
- Trust the *direction* more than the absolute ratio: small proxies retain rank-
  correlation with full runs (Poolside's claim), but proxy→full transfer is the
  documented V1 caveat — re-confirm the winning mix at the real scale.

## How it works (and how it's tested)

- `MixSampler` (TinyGPTModel) — symmetric-Dirichlet draws over corpora, seeded.
- `SurrogateFit` (TinyGPTModel) — ridge quadratic fit + predicted-improvement proposer.
- `AutoMix` (TinyGPT) — the loop; `--dry-run` swaps train+eval for a synthetic
  scorer with a known optimum so the whole search is CI-checkable without a GPU:

```bash
bash evals/automix-smoke.sh    # asserts the loop converges to the synthetic optimum
```

Unit tests: `Tests/TinyGPTModelTests/AutoMixTests.swift` (sampler validity,
surrogate optimum recovery, solver).
