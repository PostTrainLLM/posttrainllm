---
description: Compare logits distillation with response imitation, inspect local CLI prerequisites, and measure student quality, regressions, and costs fairly.
---

# LLM distillation: methods, commands, and fair comparisons

LLM distillation trains a student model using a teacher's predictions or
generated answers. It can help a smaller model learn a narrow task, but the
gain depends on the teacher, data, student capacity, and evaluation. A lower
training loss does not establish better task accuracy or cheaper inference.

This guide separates two methods, explains the local `posttrainllm distill`
command, and gives a comparison checklist. For a recorded outcome, inspect
the [file-ops specialist report card](https://posttrainllm.com/report-cards/qwen3-4b-file-ops-distilled).
That is a response-imitation example with a breadth regression, not a measured
comparison of the logits loss below.

## Choose the method from the teacher access you have

| Method | What you need | What the student learns from |
|---|---|---|
| Soft or logits distillation | Teacher logits on the same token positions and vocabulary | A probability distribution over next tokens |
| Response imitation | Teacher-generated answers or checked tool trajectories | The tokens in accepted responses, usually through supervised fine-tuning (SFT) |
| Gold-label SFT | Verified target answers or executable reference trajectories | Correct examples without needing a teacher model |

Use logits distillation when a compatible teacher can run locally and its
distribution is useful for the task. A text-only teacher API does not provide
the full vocabulary distribution this implementation needs. Response imitation
fits that access pattern: collect outputs, check them, then train in the
student's own tokenizer and chat format. It does not require a shared teacher
tokenizer because teacher token probabilities are not being compared.

If you already have reliable gold answers, compare against gold-label SFT
before paying to generate teacher responses. In every case, first check
whether the unchanged student with a suitable prompt already meets the task.

### Reasoning distillation is not automatically a logits loss

The [DeepSeek-R1 paper, section 2.4](https://arxiv.org/html/2501.12948v1#S2.SS4),
describes fine-tuning smaller models on curated responses using SFT. That is
response imitation. Adding step-by-step text to a corpus does not by itself
turn training into soft distillation, or demonstrate that a tiny student has
acquired general reasoning ability. Test the required behavior on held-out
tasks, including cases where an imitated answer would be wrong.

## What the local logits command computes

For each next-token position, let `p_t = softmax(teacher_logits / T)` and
`p_s = softmax(student_logits / T)`. The executable loss in
[`Distill.swift`](https://github.com/PostTrainLLM/posttrainllm/blob/main/native-mac/Sources/TinyGPT/Distill.swift)
is:

```text
L = alpha * T^2 * KL(p_t || p_s)
  + (1 - alpha) * NLL(student_logits, next_token)

KL(p_t || p_s) = sum_vocab p_t * (log(p_t) - log(p_s))
```

The direction is **teacher to student**. The teacher's probabilities weight
the discrepancy; the student is the trainable model. The hard-target NLL is
ordinary next-token cross-entropy on the corpus. If the corpus is generated
text, those targets are generated tokens, not independently verified truth.

[Hinton, Vinyals, and Dean (2015), section 2](https://arxiv.org/html/1503.02531v1#S2),
explains softened targets: increasing temperature spreads probability across
alternatives, and the `T^2` factor compensates for temperature's gradient
scaling. This motivates the loss; it does not predict a universal perplexity
gain for an LLM or validate this repository's implementation.

The current command defaults are `--mode soft`, `--temperature 4`,
`--alpha 0.7`, `--lr 3e-4`, and `--steps 1000`. They are implementation
defaults, not proven best settings. Alpha may range from 0 to 1; both terms
are not mandatory. Temperature must be positive. Changing either is a recipe
change whose task and regression effects need measurement.

## Local command and prerequisites

The trainable student must be a from-scratch `TinyGPTModel` checkpoint loaded
from `.tinygpt`; an HF-architecture student is rejected by this command. The
teacher loader accepts a supported `.tinygpt` checkpoint or HF model
directory. This is separate from the MLX LoRA response-imitation pipeline
used by the file-ops specialist.

Before running soft distillation:

1. Use an existing valid student checkpoint and compatible local teacher.
   Record their identities and the student's prior training; do not hide an
   initialization run outside the student budget.
2. Confirm the **same tokenizer vocabulary and token IDs** for both models.
   Equal vocabulary size is insufficient: token ID 42 must mean the same
   thing for each. Preserve tokenizer files and hashes. The runner checks
   vocabulary size only; it does not verify tokenizer identity or remap IDs.
3. Supply a UTF-8 text corpus. `--corpus` is not a JSONL chat-data importer:
   JSONL passed here is tokenized as literal text. Keep evaluation examples
   outside this corpus and any teacher-data generation.
4. Fit both models, logits, student gradients, and optimizer state within the
   memory budget. The teacher adds a forward pass per step. The overhead is
   model- and batch-dependent; there is no fixed 2× memory guarantee.

Illustrative command shape with placeholder paths, **not a completed run**:

```sh
posttrainllm distill ./student-init.tinygpt \
  --teacher ./teacher-model \
  --corpus ./train.txt \
  --tokenizer ./shared-tokenizer \
  --mode soft --temperature 4 --alpha 0.7 \
  --steps 1000 --batch 1 \
  --out ./student-distilled.tinygpt
```

For hard next-token training on already prepared teacher text, the command
also supports the following shape. `--mode hard` defaults alpha to zero and
does not load a teacher unless a positive alpha is explicitly supplied:

```sh
posttrainllm distill ./student-init.tinygpt \
  --corpus ./checked-teacher-text.txt \
  --tokenizer ./student-tokenizer \
  --mode hard --alpha 0 --steps 1000 --batch 1 \
  --out ./student-imitation.tinygpt
```

This hard mode uses NLL over the entire text. It does not add assistant-only
masking, generate responses, or verify their correctness. For chat/tool
trajectories, inspect the [specialist distillation recipe](https://posttrainllm.com/recipes/distillation)
and its retained data-format and evaluation evidence instead. Saving a
checkpoint is not a quality or runtime qualification.

## A comparison you can interpret

Start with the [factory evaluation protocol](../factory/eval-protocol.md).
Write the question before choosing the budget: are you testing whether
teacher information helps the **same student**, or whether a smaller student
can replace a larger teacher within a resource limit?

- **Freeze data and scoring.** Record train/validation/test identities,
  overlap checks, task scorer, prompts, decoding settings, and regression
  slices before tuning. Teacher generation must not see the sealed test set.
  Benchmark grades here require a qualified frontier ceiling; an unqualified
  set may still expose relative regressions but cannot establish parity.
- **Control initialization.** For a logits-versus-NLL ablation, branch both
  candidates from the exact same student checkpoint. Hold training corpus,
  tokenizer, batch, context, optimizer, and sampling policy fixed where
  possible; record seeds and differences. Keep the unchanged student and
  teacher as evaluation anchors.
- **Name the budget.** Equal student steps can control token exposure when
  batches and context match. They are not matched compute: soft distillation
  also runs a teacher forward pass. For a fixed-time or fixed-compute
  comparison, measure that budget and record the different steps/tokens
  completed. Do not describe one protocol as the other.
- **Separate costs.** Record teacher pretraining or acquisition separately
  from teacher response/logit generation, student adaptation, and evaluation.
  State which costs are shared, sunk, unavailable, or included. Measure
  student serving on the same hardware, runtime, precision, prompt lengths,
  and output limits; parameter count alone does not establish latency or RAM.
- **Decide from behavior.** Inspect target scores, error cases, safety and
  breadth. Lower perplexity on the same held-out corpus/tokenizer may support
  a language-modeling result; it does not substitute for tool-use or reasoning
  accuracy. Route a narrow winner only when the router and regression policy
  support that decision; otherwise retry or reject.

Keep this small result worksheet with the artifact. Use **not measured** for
missing evidence rather than an expected number:

| Record | Required comparison |
|---|---|
| Model and recipe identity | Baseline/student/teacher revisions; tokenizer; seed; changed variables |
| Quality and regressions | Same frozen task and slices; denominators; scores; failures; decision |
| Training cost | Student steps/tokens/time/peak RAM; teacher work and data cost separately |
| Serving cost | Paired latency, peak RAM, tok/s, hardware/runtime/precision; or not measured |
| Scope | What the evidence supports, missing checks, and stop/routing conditions |

## Retained example: a file-ops gain with a breadth cost

The [file-ops report card](https://posttrainllm.com/report-cards/qwen3-4b-file-ops-distilled) and
[retained evaluation report](https://github.com/PostTrainLLM/posttrainllm/blob/main/specialists/qwen3-4b-file-ops-distilled/eval_report.json)
preserve historical results from June 2026, not a fresh evaluation. They
record a Qwen3-4B specialist adapted from the same 4B base using accepted
trajectories. The 12-task hard gate is recorded as **58% to 100%**. The
52-task out-of-domain breadth comparison falls from **59.6% to 42.3%**;
its frontier ceiling was not validated, so this is a relative regression
signal, not a frontier-capability grade. The retained verdict is routed
file-ops use only, not general planning.

Read the [dated method and failure analysis](../learn/tool-calling-frontier-parity.md)
for trajectory filtering, chat-template formatting, and stop-signal handling.
This response-imitation result does **not** measure soft KL against NLL,
student-versus-scratch perplexity, smaller-student compression, or matched
compute. Paired serving RAM, latency, and tok/s are **not recorded in that
evaluation report**. No numerical gain for this guide's logits command is
established by that artifact.

Next: [inspect the specialist recipe](https://posttrainllm.com/recipes/distillation), then
[read the report card and its caveats](https://posttrainllm.com/report-cards/qwen3-4b-file-ops-distilled).
Use the checklist above to identify what an existing result does and does
not demonstrate before starting a new experiment.
