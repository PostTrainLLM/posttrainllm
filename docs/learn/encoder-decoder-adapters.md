# Encoder-decoder adapters: LoRA on a seq2seq model for text repair

**What:** why a text-repair specialist uses an encoder-decoder base instead of a
decoder-only one, and what changes about LoRA, tokenization, loss, and decoding
when you do.
**Why it matters here:** the autocorrect specialist is the first target in this
repo that is *not* decoder-only, so every habit built on Qwen — prompt-continues-
the-sequence, adapt `q`/`v` in self-attention, judge by execution — needs
re-derivation.

Recorded 2026-07-25 alongside tasks 5.1/5.2. Implementation and measured parity:
[`../factory/autocorrect-adapter-recipe.md`](../factory/autocorrect-adapter-recipe.md).
General LoRA mechanics stay in [`../lora_guide.md`](../techniques/lora_guide.md) — this page
only covers what is *different* for seq2seq.

## 1. Why encoder-decoder for this task

**What:** T5 frames every task as text-to-text, with a bidirectional encoder over
the full input and an autoregressive decoder that writes the output.
**Why it matters here:** autocorrect is "one complete span in, one corrected span
out" — the model may look at the end of the sentence to fix its beginning, which
a causal decoder-only model structurally cannot do on the input side.
[T5 (Raffel et al., 2020)](https://arxiv.org/abs/1910.10683)

**What:** FLAN-T5 is T5 further trained on a large instruction mixture.
**Why it matters here:** it is the only bake-off candidate that mostly *copied*
its input instead of rewriting or translating it — the behavioral prior that
matters most for a minimum-edit contract.
[FLAN (Chung et al., 2022)](https://arxiv.org/abs/2210.11416) ·
measured: [`../factory/autocorrect-model-shortlist.md`](../factory/autocorrect-model-shortlist.md)

**What:** ByT5 drops the tokenizer and operates on raw UTF-8 bytes.
**Why it matters here:** it is the theoretically *right* architecture for typos —
misspellings fragment badly under SentencePiece — but it lost the bake-off on
measured cost, not on theory: 899 ms median end-to-end against a 250 ms gate.
[ByT5 (Xue et al., 2021)](https://arxiv.org/abs/2105.13626)

> The general lesson, which is not specific to this project: the architecture
> best matched to the task's *unit of error* can still lose to a worse-matched
> one that fits the latency envelope. Record it as a resource loss, not as
> evidence that byte-level modeling was the wrong idea.

## 2. What LoRA does differently on seq2seq

**What:** LoRA freezes the base and learns a low-rank update `ΔW = BA`, with `B`
initialized to zero so the adapted model starts exactly at the base.
**Why it matters here:** the zero-init property turns adapter wiring into an
*equality assertion* — inject, run a forward pass, and the logits must be
bit-identical. Our check reports max absolute delta `0.0` on the real 77 M base.
[LoRA (Hu et al., 2021)](https://arxiv.org/abs/2106.09685) ·
where: `scripts/research/autocorrect_adapter.py::inject_lora`

Three seq2seq-specific consequences:

**Three attention sites, not one.** A decoder-only model has one attention type
to adapt. An encoder-decoder has encoder self-attention (reading the noisy span),
decoder self-attention (tracking what has been emitted), and **decoder
cross-attention** (deciding which source position to copy or repair next). For a
rewriting task, cross-attention is arguably the most important of the three — it
is where "copy this character through" lives. All three are adapted here; 48
modules, 344,064 parameters, 0.447% of the base.

**The gradient signature is diagnostic.** Because `B = 0` at step 0,
`dL/dA` is *exactly* zero while `dL/dB` is not — a mathematical consequence of
the chain rule, not an approximation. After one optimizer step `B` is non-zero
and `A` starts learning. A LoRA branch that has been silently detached from the
graph produces zero gradients on *both*, so asserting this asymmetry catches a
failure mode that a "loss went down" smoke test would miss. This is the single
most useful test in the suite.

**Labels need an ignore index.** Decoder-only SFT masks the prompt out of the
loss. Seq2seq instead has a separate label tensor, and its *padding* must be set
to `-100` or the model is trained to emit pad tokens. Cheap to get wrong, silent
when wrong.

## 3. Copy bias — the failure mode to expect

**What:** seq2seq models trained on near-identity input/output pairs learn to
copy the input verbatim, because copying is an excellent loss-minimizing policy
when ~97% of characters are unchanged.
**Why it matters here:** a model that copies perfectly scores 0% error reduction
but ~100% clean preservation, which looks *partially* good on a naive average.
This is exactly why the frozen thresholds score error reduction and clean
preservation as separate gates that must both pass.
Background: [Pointer-Generator (See et al., 2017)](https://arxiv.org/abs/1704.04368),
[CopyNet (Gu et al., 2016)](https://arxiv.org/abs/1603.06393)

The staged plan (task 5.5) is to *measure* copy bias on the ordinary-loss pilot
before deciding whether an edit-aware objective is justified. If ordinary
sequence loss already fixes the target slices, the edit-aware stage never runs —
that is a success, not a skipped feature.

**Observed, 2026-07-25 — and then inverted.** The tiny-overfit adapter, probed
on unseen input, copied `The meetign is at nine tomorrow.` through *unchanged*:
copy bias, exactly as predicted.

Then the pilot trained for 50 steps on 12 rows and blew straight past the
target in the opposite direction. It became a **paraphraser** — `remeber` →
`remind you`, `teh team` → `your team`, `tomorroww` → `tomorrow morning` — with
an unnecessary-edit rate of 0.839 against a 0.005 bar, and an error reduction of
**−0.8125**, meaning the output is further from the clean text than the typo'd
input was.

So the real dynamic is not "copy bias, which training must overcome." It is a
**narrow band between two failure modes**: copy everything (zero repair) and
rewrite everything (negative repair). Ordinary sequence loss on a tiny dataset
does not find that band — it slid from one wall to the other in fifty steps.
Full evidence:
[`../factory/autocorrect-adapter-recipe.md`](../factory/autocorrect-adapter-recipe.md#tasks-5455--the-pilot-run-2026-07-25-regressed).

That is also why the edit-aware objective was *rejected* rather than tried: it
up-weights edit positions, which pushes toward the wall the model had already
hit.

### Designing a stop rule that can actually be satisfied

A related trap, found the same day. The pilot's stop rule was
`clean_preservation < 0.995 → stop`. Sensible as a *ship* bar. But the base
model's own zero-shot clean preservation is 0.667, so the rule fired at the
first evaluation regardless of what training did — the pilot could never run
past step 50 by construction.

**The general rule: a training stop rule must be satisfiable by the model you
are starting from.** Reusing a ship-grade bar as a training guard silently
converts "stop if we regress" into "stop always." Check every stop rule against
the *baseline's* measured value, not against the target.

## 4. Edit-aware loss, and why it is gated behind an ablation

**What:** an edit-aware objective up-weights the decoder positions that
correspond to actual corrections, using an alignment between the noisy source
and the clean target.
**Why it matters here:** it is the motivating account's headline claim, and it is
the easiest place in this whole project to fool ourselves — the weighting is a
free parameter that can be tuned until the target metric moves.

The hard part is not the loss, it is the **offset mapping**: edits are computed
over characters or bytes, but the loss lives on *tokens*. Insertions have no
source position, deletions have no target position, and a multi-byte grapheme
can straddle a token boundary. The spec requires this mapping be unit-tested on
toy Unicode cases *before* any training, with ordinary sequence loss retained as
the oracle ablation.
Background: [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance) ·
where: `scripts/research/autocorrect_foundation.py::edit_operations`

## 5. Overfit a tiny batch first

**What:** before training on real data, verify the model can drive loss to ~zero
on a handful of examples; if it cannot memorize 8 rows, the bug is in the code,
not the data.
**Why it matters here:** this repo has already paid for skipping it — the SimPO
SQL collapse and the "eval was measuring framework, not model" episode were both
found late. The autocorrect lane makes it a *gate*: 3,321 bytes, exact match
1.0 required, and a hard `retry-training` stop rule if it fails.
[Karpathy, *A Recipe for Training Neural Networks*](http://karpathy.github.io/2019/04/25/recipe/) ·
where: `evals/autocorrect/tiny-overfit-manifest-v1.json`

**The trap this fixture walked into.** Our tiny-overfit set derives all 8 rows
from *one* source sentence, so all 8 targets are identical — and the gate passed
at exact match 1.0 in 50 steps. That number is nearly free: a model that learns
to emit one memorized sentence scores 1.0 without correcting anything.

The gate is still worth having; it caught nothing only because nothing was
broken, and it would have caught a detached optimizer, a NaN, or a
capacity shortfall. But it teaches a sharper lesson than intended:
**a memorization gate should have more than one unique target**, or its pass
condition is satisfiable by a degenerate policy. Ours needed a separate
diagnostic probe on unseen input to find out which had happened. A stronger v2
fixture would draw from several source documents so that "memorize the data" and
"emit one constant" stop being the same behavior.

## 6. Decoding: greedy first, beam only if traces justify it

**What:** beam search keeps `k` hypotheses and can recover from a locally-bad
token that greedy commits to; stable-prefix streaming emits only the longest
common prefix of surviving beams, so displayed text is never retracted.
**Why it matters here:** beam search multiplies latency by roughly the beam
width, against a 250 ms end-to-end gate that FLAN-T5-small already sits at
124 ms for. It is gated behind evidence of *recoverable* search errors in trace
review, not adopted by default.
Background: [The Curious Case of Neural Text Degeneration (Holtzman et al., 2019)](https://arxiv.org/abs/1904.09751)
for why beam is not a free win on open-ended generation — though repair is far
more constrained than generation, which is the argument *for* trying it here.

The streaming correctness property is worth stating precisely because it is
testable: every emitted prefix must equal a prefix of the final output, and
emission may only happen at valid UTF-8 grapheme boundaries. That makes "never
retract" a unit test rather than a UX aspiration.

## 7. Where this connects

| Concept | This project |
|---|---|
| Encoder-decoder text-to-text | `evals/autocorrect/protocol-v1.json` — the frozen span-in/span-out contract |
| LoRA on three attention sites | `scripts/research/autocorrect_adapter.py`, [recipe](../factory/autocorrect-adapter-recipe.md) |
| Copy bias vs error reduction | `evals/autocorrect/thresholds-v1.json` — separate quality and regression gates |
| Edit alignment | `scripts/research/autocorrect_foundation.py::edit_operations` |
| Tiny-overfit discipline | `evals/autocorrect/tiny-overfit-manifest-v1.json`, task 5.3 |
| Decoding/latency trade | `evals/autocorrect/base-bakeoff-v1.json` measured TTFT and end-to-end |

Sibling pages: [`../lora_guide.md`](../techniques/lora_guide.md) (general LoRA),
[`session-07-behavior-learning.md`](session-07-behavior-learning.md) (Module 9,
post-training concepts), [`session-11-evals-rewards.md`](session-11-evals-rewards.md)
(Module 10, why the gates are shaped this way).

## Self-check

1. Why can a decoder-only model not do what the encoder does here?
2. At step 0, which LoRA matrix has zero gradient, and why is that a *useful*
   property rather than a problem?
3. A candidate scores 0% error reduction and 100% clean preservation. What
   happened, and which gate catches it?
4. A candidate scores **−0.81** error reduction. What does a *negative* error
   reduction mean, and which failure mode produces it?
5. Why is the byte-to-token offset mapping the risky part of edit-aware loss?
6. Our pilot overcorrected. Explain why an edit-aware objective was rejected
   rather than tried as the fix.
7. A stop rule reads `clean_preservation < 0.995 → stop`. What must you check
   before accepting it as a *training* guard?
8. ByT5 is better matched to typo repair than FLAN-T5. Why did it lose?
