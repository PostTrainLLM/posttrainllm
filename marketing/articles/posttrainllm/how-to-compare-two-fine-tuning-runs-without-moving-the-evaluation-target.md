---
title: "How to compare two fine-tuning runs without moving the evaluation target"
slug: "how-to-compare-two-fine-tuning-runs-without-moving-the-evaluation-target"
target_query: "compare fine tuning runs"
search_intent: "Informational"
meta_title: "How to Compare Two Fine-Tuning Runs Without Moving the Evaluation Target"
meta_description: "Learn how to compare LLM fine-tuning runs effectively by freezing baselines, using frontier-calibrated gates, and measuring both primary and regression scores."
---

## Outline

1.  **Introduction**: The complexity of evaluating language models and the danger of optimizing against noise.
2.  **Rule 1: The Frozen Baseline**: Why the evaluation target must be absolute and established before any training.
3.  **Rule 2: The Frontier-Ceiling Gate**: Ensuring benchmarks are solvable by calibrating them against a frontier model.
4.  **Rule 3: Measuring the Breadth Tax**: Why measuring primary capabilities is not enough, and how specialization causes negative transfer.
5.  **Rule 4: Trusting the Parser**: The brittleness of exact-match scoring and the necessity of robust AST-based evaluation.
6.  **Rule 5: Enforcing Decisions**: Turning evaluation data into actionable ship, retry, or reject decisions.
7.  **Next Action**: Practical steps to implement this protocol locally.
8.  **Source Notes (Internal)**: Documentation of claims and limitations based on PostTrainLLM evidence.

## Introduction

Evaluating a fine-tuned language model is deceptively difficult. When you change hyperparameters, swap a dataset, or move from a 1.7B parameter base model to a 4B parameter model, you expect a clear signal of improvement or degradation. However, how do you know if the new model is genuinely better? If the evaluation metric changes alongside the model, or if the test itself is structurally flawed, you might be measuring noise instead of a genuine capability improvement.

In the PostTrainLLM research factory—a project dedicated to building and evaluating Mac-local models on Apple Silicon—we discovered early on that improving a model's score often means fixing the evaluation first. The goal is not merely to build models but to understand the space rigorously, establishing a repeatable factory loop of `target -> data -> post-training -> eval -> package -> report`.

This article outlines an evidence-backed protocol for comparing two fine-tuning runs without moving the evaluation target, ensuring that every point of improvement is real. Whether you are running parameter-efficient fine-tuning (PEFT) on a local machine or managing larger clusters, these principles will help you separate actual progress from evaluation artifacts. To see how these principles apply in practice across our guided learning paths, refer to our [learning labs](/learn).

## Rule 1: The Frozen Baseline

The first and most critical rule of comparing fine-tuning runs is to freeze the evaluation *before* training begins. A frozen baseline consists of a fixed set of prompts, a fixed scoring script, and a fixed reference performance from the base model. If you adjust the evaluation dataset or modify the scoring script after training a candidate model, you invalidate the comparison. Every fine-tuning run must be evaluated against the exact same frozen baseline to produce a meaningful delta.

When you run a baseline evaluation first, you establish the objective starting point. For instance, if your stock Qwen3-4B model scores 87.3% on a single-turn tool-calling benchmark, that is your frozen baseline. Any subsequent experiment—whether applying ToolRL-GRPO, function-masking SFT, or a new distillation recipe—must be judged against that 87.3%. If the new score drops to 80.0%, the run regressed. That is a measurable, honest result that prevents self-deception.

This rule is load-bearing. In the PostTrainLLM factory loop, the baseline comes strictly before training. This ensures that any reported improvement is entirely attributable to the post-training process, not to a coincidentally easier evaluation slice or a more lenient scoring script introduced after the fact. Review our past results in our [experiment archive](/experiments) to see how frozen baselines anchor our evaluations.

## Rule 2: The Frontier-Ceiling Gate

A common pitfall in evaluating small models is using a benchmark that is fundamentally broken. If an evaluation task asks for information that cannot be logically derived from the prompt, no model—regardless of size or training budget—will score well.

This leads to the **frontier-ceiling gate**: before any benchmark is used to grade a small, locally trained model, a frontier model must score approximately 100% on it. If a frontier model cannot ace the benchmark, the benchmark is broken. You must fix it or drop it entirely; you should never report a small model's accuracy on a benchmark that fails this calibration.

A clear example of this occurred when evaluating tool-calling capabilities. Initially, the `hermes-fc` dataset was used to grade local models. The local 1.7B model scored around 55% using exact-string matching. However, a deeper analysis revealed that approximately 29% of the held-out examples required "ungroundable" arguments—values such as specific device IDs, transaction codes, or literal placeholder strings like `unique_nft_identifier` that appeared nowhere in the prompt. When a frontier model was tested on these hard cases, it scored only around 12%, and notably, its answers were often more logically correct than the established gold standard.

Because the frontier model failed the ceiling gate, the `hermes-fc` dataset was strictly relegated to training data and disqualified as a reporting metric. The evaluation target shifted to the Berkeley Function Calling Leaderboard (BFCL) suite, where golds are verified as groundable. When tested against a controlled single-turn harness derived from BFCL, a frontier model scored 99.2%, proving it was a valid, reliable ruler for comparing smaller models.

By using a frontier-calibrated benchmark, you ensure that the gap you measure between two fine-tuning runs reflects a real capability difference. The frontier model serves as the calibration anchor, ensuring you are measuring against a reachable capability ceiling.

## Rule 3: Measuring the Breadth Tax (Catastrophic Forgetting)

Fine-tuning is rarely a free lunch. Specializing a model for a specific task often causes it to forget general capabilities—a phenomenon known as catastrophic forgetting, negative transfer, or the "breadth tax." To accurately compare two runs, you must separate the primary task score (depth) from the regression score (breadth).

Consider a multi-turn agentic task focused specifically on file-system operations. A stock 4B parameter model might score 58% on this difficult gate. After applying rejection-sampling distillation using 99 high-quality frontier trajectories, a specialized 4B model achieved 100% on the exact same gate. Viewed in isolation, this looks like an unmitigated success for the primary task.

However, the evaluation must not stop there. When the same models were tested on 52 held-out, out-of-domain tasks (spanning trading bots, vehicle control APIs, and travel bookings), the stock model scored 59.6%. The narrowly distilled model, which aced the file-ops tasks, saw its out-of-domain score drop significantly to 42.3%.

The fine-tuning run bought depth in file operations at the cost of a 17-point regression in breadth. The model became a file-ops specialist, not a generally better agent.

When comparing runs, you must report both numbers. A report card that only shows the 100% depth win is incomplete and misleading. By rigorously tracking both primary and regression scores, you can make an informed decision on how to deploy the artifact: you might choose to route the model specifically for its narrow domain (as a routed specialist), or you might iterate on the training data to recover breadth through techniques like interleaved multi-backend distillation. For more on creating and utilizing these models, refer to our [recipe registry](/recipes).

## Rule 4: Trusting the Parser, Not the String

The mechanism used to score the model is just as important as the dataset itself. Exact-string matching is notoriously brittle and punitive for evaluating language models, especially for structured outputs like tool calls, JSON payloads, or code snippets.

To compare fine-tuning runs fairly and accurately, prefer benchmarks that utilize verified golds combined with Abstract Syntax Tree (AST) matching, semantic matching, and per-call partial credit. A lenient, well-tested parser is an absolute prerequisite for a fair evaluation.

During the development of our tool-calling benchmarks, two subtle parser bugs initially masked the true capabilities of the local models. One bug inadvertently discarded multi-call outputs that used a single closing tag, while another failed to properly parse bare-JSON calls containing nested arguments.

Fixing these parser bugs had a dramatic impact on the measured results. For example, a distilled 1.7B model's score on parallel multiple calls moved from a false 8% to a real 60% simply by correcting the parsing logic.

When comparing two runs, ensure your parser evaluates the semantic correctness and functional validity of the output, not just its exact formatting or character sequence. If Run A appears worse than Run B, verify that the parser isn't unfairly penalizing Run A for a functionally valid, but slightly structurally different, output. A rigorous evaluation requires measuring intent and execution, not just syntax.

## Rule 5: Enforcing Ship, Retry, and Reject Decisions

The ultimate goal of comparing fine-tuning runs is not just to generate metrics, but to make decisions. An effective evaluation protocol must enforce explicit outcomes: Ship, Retry, or Reject. Optimistic prose about a model's potential cannot replace a hard decision based on the numbers.

*   **Ship:** You ship a candidate only when the primary score clearly beats the frozen baseline, the regression is within acceptable limits, the failure classes are well-understood, and the entire artifact can be reproduced.
*   **Retry:** You decide to retry (e.g., retry-data or retry-training) when the model shows promise but fails a critical constraint. For instance, a DPO run that improves execution scores but fails to fix output-format hygiene requires a data retry, not a ship.
*   **Reject:** You reject a candidate when the primary score does not beat the baseline, when breadth damage erases the gain, or when the evaluation itself is deemed too unstable to trust. Rejecting a model is a successful application of the evaluation protocol.

By strictly enforcing these decisions, you ensure that every fine-tuning run either improves the system or provides a documented learning outcome, avoiding the accumulation of untrusted or marginally useful models.

## Summary of the Protocol

To effectively compare two fine-tuning runs without moving the evaluation target, adhere to these core principles:

1.  **Freeze the Eval**: Define your dataset, your parser, and your baseline score *before* any training code is executed.
2.  **Calibrate with Frontier**: Ensure a frontier model can achieve near 100% on your benchmark. If it cannot, you are optimizing against noise.
3.  **Measure the Trade-off**: Always report both the primary task score (depth) and a regression/breadth score to accurately capture catastrophic forgetting.
4.  **Use Semantic Matching**: Avoid brittle exact-string match; employ AST parsing or semantic evaluation to measure true capability.
5.  **Force a Decision**: Use the evaluation data to make a clear Ship, Retry, or Reject decision, recording all metrics in a durable report.

By adopting this evidence-backed protocol, you can trust your evaluation metrics and make confident decisions about the value of your fine-tuning experiments.

## Next Action

To apply these principles today, start by defining a completely frozen baseline for your current project. Select a small, groundable dataset tailored to your primary task. Run a frontier model against this dataset to confirm a >95% ceiling. Then, evaluate your stock base model to establish your starting score. Only after these numbers are recorded should you begin your next fine-tuning experiment.

---

### Source Notes (Internal / Non-Publishable)

*   **Evidence Sources:**
    *   `AGENTS.md` ("Eval philosophy"): Establishes the core philosophy of reaching frontier capability at a lower cost, the necessity of the "frontier-ceiling gate" (~100% requirement before a benchmark is valid), the rejection of the `hermes-fc` dataset due to ungroundable golds (frontier scored ~12%), and the strong preference for AST/semantic matching over exact-string match.
    *   `docs/factory/eval-protocol.md`: Outlines the strict rules for the factory evaluation protocol, explicitly stating "Freeze the eval before training," running the baseline first, keeping primary and regression scores separate, and enforcing the Ship/Reject discipline.
    *   `docs/learn/tool-calling-frontier-parity.md`: Provides the concrete, measured data for all claims. This includes the 1.7B parser bug fix (jumping from 8% to 60%), the stock Qwen3-4B baseline of 87.3, the multi-turn file-ops distillation jumping from 58% to 100%, and the critical catastrophic forgetting measurement where breadth dropped from 59.6% to 42.3%, leading to negative transfer.
    *   `PRODUCT.md`: Reinforces the product principles that "A frozen baseline comes before training," "Task outcomes and regressions outrank training loss," and "Ship, block, and park are explicit decisions—not optimistic prose."
*   **Limitations:**
    *   The "frontier-parity" claims cited are specific to a bounded, single-domain (file operations) multi-turn gate and do not represent generalized 4B > 12B superiority across all tasks.
    *   The project explicitly measures and notes that narrow distillation causes negative transfer; the "breadth" score regression is a known trade-off, leading to the model being retained as a "routed specialist" rather than a general-purpose successor.
    *   All measured numbers and performance claims are based on single-Mac (Apple Silicon) evaluations.
