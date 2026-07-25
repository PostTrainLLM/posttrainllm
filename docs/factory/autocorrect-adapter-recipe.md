# Autocorrect adapter recipe and training path

Frozen 2026-07-25. This is the canonical home for tasks 5.1 and 5.2 of
`build-mac-local-autocorrect-specialist`: the ordinary supervised adapter recipe
and the encoder-decoder training path it needs.

Prior stages: [foundation](autocorrect-foundation.md) (contract, evaluator,
simulator, manifests) and [base gate](autocorrect-model-shortlist.md) (the
measured three-candidate bake-off that selected FLAN-T5-small).

**Nothing here has been trained.** Tasks 5.3 (tiny-overfit gate) and 5.4 (pilot)
still require explicit owner approval and the GPU lock.

## The frozen recipe

Machine-readable and authoritative:
[`evals/autocorrect/adapter-recipe-v1.json`](../../evals/autocorrect/adapter-recipe-v1.json).
The prose below explains the choices; the JSON wins on any disagreement.

| Dimension | Frozen value | Why |
|---|---|---|
| Base | `google/flan-t5-small` @ `0fc9ddf` | Only candidate that survived the bake-off resource and copy-fidelity gates |
| Method | LoRA, rank 8, alpha 16 (scaling 2.0), dropout 0 | Original LoRA ablation geometry; zero dropout keeps parity tests exact |
| Targets | `q` and `v` in encoder self-attn, decoder self-attn, decoder cross-attn | Query/value only, per the LoRA paper; cross-attention is included because this task rewrites the source rather than continuing it |
| Trainable | 344,064 params across 48 modules (0.447%) | Derived from the base config, not asserted |
| Optimizer | AdamW, lr 1e-3, betas (0.9, 0.999), wd 0, clip 1.0 | LoRA-on-small-T5 convention; the tiny-overfit gate is the empirical check |
| Schedule | Linear warmup 10%, then constant | Small step budgets do not benefit from decay |
| Precision | float32 | T5 overflows in float16; the bake-off measured this base in float32 |
| Seed | 20260725 | Same seed as the data manifests |
| Batch / steps | 4; 200 tiny-overfit, 300 pilot | Inside the frozen 1000-step pilot cap |
| Checkpoints | Every 50 steps, keep last + best | Cheap at 344 K trainable params |

### Two non-obvious choices

**`lora_b` initializes to exact zeros.** This makes `delta_W` identically zero
before the first optimizer step, so an adapted model must be *bit-identical* to
the base. That converts "did I wire the adapter in correctly?" from a judgement
call into an equality assertion. It is measured below.

**`truncation_policy` is `error`, not `longest_first`.** The correction
contract is byte-preserving: silently truncating an over-length row would
fabricate a deletion and teach the model to drop text. An over-length row is a
recorded drop instead. Measured headroom is wide — the longest source in any
frozen dataset is 38 tokens against a 256-token cap.

## The training path

[`scripts/autocorrect_adapter.py`](../../scripts/autocorrect_adapter.py) is
split so that the dependency-free half is always testable:

- **Stdlib layer** — recipe validation, target-module resolution, example
  building on top of `autocorrect_foundation.materialize_manifest`, the
  LR/checkpoint schedule, and the stop-rule state machine. No third-party
  import.
- **Torch layer** — LoRA injection, adapter save/load, batch encoding, one
  training step. Imported lazily.

LoRA is hand-rolled rather than taken from `peft`. Torch, transformers, and
peft are **not** dependencies of this repository, and the bake-off already
established the pattern of a caller-supplied disposable runtime. The
implementation is about forty lines; a dependency would have cost more.

`train` is present but refuses:

```console
$ python3 scripts/autocorrect_adapter.py train --stage tiny_overfit
REFUSED: training the autocorrect adapter needs explicit owner approval and
the GPU lock (~/.cache/posttrainllm/gpu.lock).
```

## Measured evidence

### Load parity against the real base

Forward-only, CPU, zero optimizer steps, `HF_HUB_OFFLINE=1`:

```bash
python3 scripts/autocorrect_adapter.py verify-base
```

| Check | Result |
|---|---|
| Base parameters | 76,961,152 |
| Adapted modules | 48 (matches the frozen expectation) |
| Trainable parameters | 344,064 = 0.4471% (matches the frozen expectation) |
| Logits bit-identical after injection | **true**, max absolute delta `0.0` |
| Base tensors modified | none |
| All trainable tensors are LoRA | true |

### Offline test suite

```bash
bash evals/autocorrect-adapter-smoke.sh
```

19 tests, all passing (2026-07-25, torch 2.7.1 / transformers 5.10.2). The ten
torch-backed tests build a **tiny randomly-initialized T5** — no checkpoint is
downloaded or loaded — and skip with a visible marker when torch is absent, so
CI runs the nine stdlib tests and reports `9/19 passed (10 skipped)` rather than
a false green.

What the suite actually proves:

- **Load parity** — zero-init injection leaves logits bit-identical.
- **Frozen base** — every trainable tensor is LoRA; the count equals the value
  derived from the config; a training step moves no base tensor.
- **Gradient wiring** — at step 0 `dL/dA` is *exactly* zero (because `B = 0`)
  while `dL/dB` is non-zero; after one step `dL/dA` becomes non-zero. This is
  the property that distinguishes a correctly wired LoRA from one whose
  branch is silently detached from the graph.
- **Save/load** — round-trips exactly, restores identical logits, carries no
  base weights, and fails closed on recipe-id or rank drift.
- **Determinism** — two injections produce identical A matrices, and distinct
  modules do not share one.
- **Data safety** — padding is masked to `-100`; an over-length batch raises
  instead of truncating; a drifted dataset hash refuses to build examples.
- **Recipe drift** — twelve mutations (prompt, revision, model, precision,
  dataset hash, row count, truncation policy, unfrozen base, non-zero `B`
  init, trainable count, step cap, gate bar) are each detected.

### What is not proven

- No adapter has been trained. There is no quality, latency, RAM, or throughput
  claim for any adapted model.
- The one-step loss-decrease test runs on an 11 K-parameter random T5. It shows
  the optimizer path functions; it says nothing about whether FLAN-T5-small can
  learn this task.
- The tiny-overfit gate (5.3) is the first real evidence, and it is unrun.
- Loading the real base emits a transformers warning that `shared.weight` and
  `lm_head.weight` are present with different values and will not be tied. This
  is a property of the checkpoint, not of the adapter, and neither tensor is a
  LoRA target — but a future full-model or embedding-touching recipe must
  revisit it.

## Task 5.3 — the tiny-overfit gate (run 2026-07-25, passed)

Owner-approved; GPU lock acquired and released. Evidence:
[`evals/autocorrect/tiny-overfit-result-v1.json`](../../evals/autocorrect/tiny-overfit-result-v1.json).
Adapters stay in gitignored `runs/autocorrect-tiny-overfit-v1/`.

```bash
python3 scripts/autocorrect_adapter.py train --stage tiny_overfit --i-have-operator-approval
```

| Measure | Value |
|---|---|
| Exact match | **1.0** at step 50 (budget 200) |
| Loss | 1.585 → 0.030, no non-finite step |
| Wall time | 0.28 min |
| Peak RSS | 1,135 MiB, device `mps` |
| Stop rule fired | none |

### Read this before quoting "8/8"

**The fixture has exactly one unique target.** All 8 rows derive from a single
source document, so every target is the identical string `Please review the
draft before lunch.` Exact match 1.0 is therefore reachable by memorizing one
sentence. The gate proves the training path runs end to end and that 344 K
trainable parameters suffice to fit the fixture. It is **not** evidence of
correction ability, and it must never be quoted as a quality result.

A forward-only diagnostic probe on three unseen inputs (not a scored eval)
tested whether the adapter had degenerated into a constant emitter. It had not —
outputs vary with input — but all three predicted failure modes are visible:

| Input | Output | Failure |
|---|---|---|
| `The meetign is at nine tomorrow.` | identical | copy bias — the typo survived |
| `Send the invoice to https://…` | `Please send the invoice to https://…` | memorization leakage — spurious `Please` |
| `quokka sightings rose by 12 percent.` | `Correct only the typing errors in the following text.` | instruction echo |

This is useful, not disappointing: §3 of
[`../learn/encoder-decoder-adapters.md`](../learn/encoder-decoder-adapters.md)
predicted copy bias as the dominant risk, and the pilot's job is to move it.

## Tasks 5.4–5.5 — the pilot (run 2026-07-25, regressed)

Owner-approved; GPU lock acquired and released; no lingering process. Trained on
the manifest's 12 train-split rows only — the 4 development rows were monitored,
never trained on. Scored on the unchanged frozen `eval-v1.jsonl` through the
same foundation evaluator the bake-off used. Evidence:
[`evals/autocorrect/pilot-result-v1.json`](../../evals/autocorrect/pilot-result-v1.json).

| Metric | Zero-shot base | Pilot | Delta |
|---|---:|---:|---:|
| Error reduction | +0.0625 | **−0.8125** | **−0.875** |
| Exact match | 0.389 | 0.444 | +0.056 |
| Clean preservation | 0.667 | 0.667 | 0.000 |
| Protected spans | 0.867 | 0.800 | −0.067 |
| Unnecessary edit rate | — | 0.839 | bar is ≤ 0.005 |

Negative error reduction means the output is *further* from the clean reference
than the noisy input was. The pilot made text worse.

### The failure is overcorrection, not copy bias

The model became a paraphraser:

| Noisy | Clean | Prediction |
|---|---|---|
| `I will remeber to bring the charger.` | `…remember…` | `I will **remind you** to bring the charger.` |
| `Meet teh team beside the station.` | `…the team…` | `Meet **your** team beside the station.` |
| `The café opens tomorroww.` | `…tomorrow.` | `The café opens tomorrow **morning**.` |
| `The repourt is ready.` | `…report…` | `The repourt is ready.` *(unfixed)* |

Structural slices are genuinely clean — casing, name, number, and url all score
1.0 error reduction with zero unnecessary edits. The damage is concentrated in
lexical repair, which turned into semantic rewriting: exactly the behaviour the
design's non-goals forbid.

This *inverts* the prediction from the tiny gate, where the untrained-ish
adapter copied typos through. Fifty steps on twelve rows took the model straight
past "repair" into "rewrite" without stopping at the target.

### Recipe defect: the stop rule was unsatisfiable

The run stopped at step 50 of 300 on `clean-preservation-collapse`. But
`thresholds-v1.stop_on_clean_preservation_below` is **0.995** while the base
model's own zero-shot clean preservation is **0.667** — so the rule fires at the
first scheduled evaluation no matter what training does. A ship-grade regression
bar is being used as a training stop rule.

The regression above is real and measured, but it is **truncated evidence**:
50 of 300 steps, forced by construction rather than by the model. A fair test of
this recipe needs a new thresholds version that separates training stop rules
from ship bars.

### 5.5 answer: an edit-aware objective is not justified

An edit-aware loss up-weights the positions that need correcting. The measured
failure is that this model edits far too *much*, not too little — unnecessary
edit rate 0.839 against a 0.005 bar. Weighting edit positions harder would very
likely push overcorrection higher, which is task 5.7's explicit reject
condition. Tasks 5.6–5.7 are therefore **not** proceeding.

The real blockers, none of which an edit-aware loss addresses:

1. Twelve training rows is too little signal for lexical repair.
2. The unsatisfiable stop rule truncates every pilot at its first evaluation.
3. Nothing in the objective or the decoding path guards against meaning change.

## Next step — needs a new recipe version, not another run

The frozen recipe has reached its stop rule, and its `movement_policy` forbids
moving bars inside a live run. A `v2` should address, in this order:

1. **Separate training stop rules from ship bars** so a pilot can run its budget.
2. **More data** — the 26 source documents already exist; the pilot uses 8.
3. **A meaning-change guard**, since overcorrection is now the measured enemy.

No further training should run under `adapter-recipe-v1`.
