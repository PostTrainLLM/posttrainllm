# TinyGPT learning curriculum — ground up

This is the owner learning roadmap from first principles to a self-improving
factory for Mac-local specialist models: a self-improving factory in practice,
not a pile of disconnected courses.

The goal is not to "finish a course." The goal is to build durable taste:

- know what a model is actually doing,
- know what changes when data, loss, optimizer, architecture, or eval changes,
- know when a post-training result is real,
- and know how to turn a failure into the next better recipe.

## 10/10 Bar

The roadmap is good enough only if it satisfies all of these:

1. **Ground-up order** — no DPO, LoRA, RLVR, or eval jargon before the
   underlying model/training concepts are in place.
2. **One spine** — every module fits the same arc:
   `concept -> toy implementation -> TinyGPT anchor -> factory consequence`.
3. **Exercises, not passive reading** — each module has something to compute,
   inspect, run, or write.
4. **Mastery gates** — each module has a concrete "you understand it when"
   check.
5. **Project transfer** — every module says how it changes SQL/factory work.
6. **External anchors** — one or two canonical external resources per stage,
   used as support, not as the curriculum owner.
7. **Progress tracking** — learning state lives in
   [`../learning-progress.md`](../learning-progress.md), with evidence.
8. **Cadence** — each week ends in a note, a repo artifact, or a recipe change.
9. **Failure feedback** — failed TinyGPT runs create the next learning prompt.
10. **No random walk** — interesting topics are parked unless they improve
    target selection, data, post-training, eval, packaging, or reporting.

## Operating Loop

For each module:

```text
read -> explain -> implement/inspect -> connect to TinyGPT -> change a recipe/report
```

Suggested weekly cadence:

| Block | Time | Output |
|---|---:|---|
| Read/watch | 30-60 min | notes on the concept |
| Rebuild toy version | 60-120 min | tiny script, notebook, or code inspection |
| TinyGPT bridge | 30-60 min | point to the repo file/run where it matters |
| Written checkpoint | 15 min | one paragraph in the next report or learning note |

Do not advance because a file was read. Advance when the mastery gate is met.

## Canonical External Anchors

Use these as supporting material:

- Karpathy, **Neural Networks: Zero to Hero**:
  <https://github.com/karpathy/nn-zero-to-hero>
- 3Blue1Brown, **Neural Networks** visual series:
  <https://www.3blue1brown.com/topics/neural-networks>
- Stanford CS224N, **NLP with Deep Learning**:
  <https://web.stanford.edu/class/cs224n/>
- The Annotated Transformer:
  <https://nlp.seas.harvard.edu/annotated-transformer/>

The project still owns the path. External material fills intuition gaps; it
does not decide what to build next.

## Master Roadmap

| # | Module | Learn | Exercise | Repo Anchor | Mastery Gate |
|---:|---|---|---|---|---|
| 1 | Functions, data, parameters | A model is a parameterized function; learning means choosing parameters from data | Fit `y = mx + b` by hand on 5 points; explain fixed data vs moving parameters | [`session-01-neural-net-basics.md`](session-01-neural-net-basics.md) | You can explain what a "parameter" is without using LLM examples |
| 2 | Loss and gradient descent | Loss turns wrongness into one number; gradients say how to change parameters | Compute MSE for two `(m,b)` guesses; take one gradient-descent step | [`session-02-gradient-descent.md`](session-02-gradient-descent.md) | You can predict what too-high and too-low learning rate look like |
| 3 | Vectors, matrices, tensors | Neural nets are mostly structured multiply/add over arrays | Rewrite a one-input line as a dot product; trace tensor shapes through one layer | [`llm-mechanics-fundamentals.md`](llm-mechanics-fundamentals.md), [`essential-vs-optimization.md`](essential-vs-optimization.md) | You can read a shape error and identify which axis is wrong |
| 4 | Non-linear neural nets + backprop | Stacking linear layers only stays linear; activations and chain rule make depth useful | Train a tiny 2-layer MLP on a non-linear toy dataset; explain backprop as credit assignment | [`session-03-non-linearities.md`](session-03-non-linearities.md) | You can explain why a model can fit curves after adding activation functions |
| 5 | ML paradigms and scaling | Supervised learning, self-supervision, imitation, RL, and scale each solve different parts | Classify TinyGPT attempts as pretrain, SFT, preference tuning, eval, or routing | [`session-04-ml-paradigms.md`](session-04-ml-paradigms.md), [`session-05-scaling.md`](session-05-scaling.md) | You can say why scale helps knowledge but does not fix bad evals or bad data |
| 6 | Tokenization, embeddings, language modeling | Text becomes tokens; tokens become vectors; next-token prediction creates language skill | Tokenize three prompts; inspect how SQL punctuation and identifiers split | [`session-06-tokenization-embeddings.md`](session-06-tokenization-embeddings.md), [`../tool_call_extractor.md`](../tool_call_extractor.md) | You can explain why tokenization affects SQL/tool-call reliability |
| 7 | Attention and transformer blocks | Attention routes information across positions; transformer blocks repeat attention + MLP | Work one tiny attention example with query/key/value vectors and shapes | [`llm-mechanics-fundamentals.md`](llm-mechanics-fundamentals.md), [`advanced-llm-inference.md`](advanced-llm-inference.md) | You can describe what attention can copy/route that an MLP alone cannot |
| 8 | Training mechanics | Batches, epochs, optimizers, schedules, precision, overfit checks, and loss curves govern whether training worked | Overfit a tiny dataset or inspect an existing overfit gate; identify failure mode from a loss curve | [`session-08-training-mechanics.md`](session-08-training-mechanics.md), [`../training_guide.md`](../training_guide.md) | You can tell data bug vs LR bug vs capacity bug from symptoms |
| 9 | Post-training: SFT, LoRA, preference tuning | SFT teaches behavior; LoRA changes a low-rank slice; DPO/SimPO shape preferences and can collapse | Compare successful SQL SFT vs failed hygiene SimPO; run/inspect LoRA geometry | [`../training/sft.md`](../training/sft.md), [`../training/dpo.md`](../training/dpo.md), [`../factory/lora-geometry.md`](../factory/lora-geometry.md) | You can explain why the hygiene SimPO run collapsed without hand-waving |
| 10 | Evals, rewards, and self-improvement | Frozen evals, verifiable rewards, traces, failure taxonomy, and public reports make improvement measurable | Build/inspect SQL candidate-selection rows; attach slice metrics and trace review to a run | [`../factory/eval-protocol.md`](../factory/eval-protocol.md), [`../techniques/sql-technique-backlog.md`](../techniques/sql-technique-backlog.md), [`../attempt-ledger.md`](../attempt-ledger.md) | You can design the next SQL recipe with target, data, reward/eval, stop rule, and report fields |

## Where Existing Sessions Fit

The original eight sessions remain useful. They are now the foundation half of
the roadmap, not the whole roadmap.

| Existing Session | Roadmap Module |
|---|---|
| [`session-01-neural-net-basics.md`](session-01-neural-net-basics.md) | 1 |
| [`session-02-gradient-descent.md`](session-02-gradient-descent.md) | 2 |
| [`session-03-non-linearities.md`](session-03-non-linearities.md) | 4 |
| [`session-04-ml-paradigms.md`](session-04-ml-paradigms.md) | 5 |
| [`session-05-scaling.md`](session-05-scaling.md) | 5 |
| [`session-06-tokenization-embeddings.md`](session-06-tokenization-embeddings.md) | 6 |
| [`session-07-behavior-learning.md`](session-07-behavior-learning.md) | 9 |
| [`session-08-training-mechanics.md`](session-08-training-mechanics.md) | 8 |

Missing polished sessions are explicit:

- Module 3 needs a compact vectors/matrices/tensors session.
- Module 7 needs a tiny attention/transformer-block session.
- Module 10 needs a ground-up evals/rewards/self-improvement session.

Until those are written, the linked reference docs plus the exercises above are
the working path.

## Current Starting Point

Start at Module 1 unless the owner can pass the mastery gate out loud.

The current project work is SQL candidate selection, but the learning path does
not jump straight there. The correct bridge is:

```text
parameters -> loss -> gradients -> tensors -> neural nets
-> tokens -> transformers -> training loops
-> SFT/LoRA/DPO -> evals/rewards/self-improvement
```

The SQL factory is the lab. Ground-up understanding is the curriculum.

## Checkpoint Template

At the end of each module, write a short checkpoint:

```text
Module:
Concept in my words:
Toy exercise completed:
TinyGPT file/run inspected:
What this changes about the next SQL/factory recipe:
Open confusion:
```

Store durable checkpoints in [`../learning-progress.md`](../learning-progress.md)
or the next run report. Do not create loose notes unless they feed back into the
tracker.
