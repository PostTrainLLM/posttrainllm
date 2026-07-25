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

## Next authorized step

Task 5.4: one bounded ordinary-loss pilot on the 16-row pilot manifest, capped
at 300 steps and 120 minutes. It needs its own owner approval and the GPU lock.
Task 5.5 then decides — from measured copy-bias and missed-edit slices — whether
an edit-aware objective is justified at all.

Two things the 5.3 probe suggests for 5.4 planning, neither yet tested:

- The pilot fixture has 8 distinct source documents against the tiny gate's one,
  so memorization pressure drops sharply. Whether 16 rows is enough signal to
  overcome the copy prior is the open question.
- Instruction echo on out-of-distribution input suggests the prompt template may
  need to appear in training with more source variety, or that decoding needs a
  guard. Recording it now so it is not rediscovered as a surprise.
