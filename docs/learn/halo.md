# Halo: source review and Mac-local disposition

Reviewed **2026-10-02** against White Circle's
[Halo source at `50dab99`](https://github.com/whitecircle/halo/tree/50dab99eafa89bd215b8f342bf7a0259d4ee26b1).
This is a source/documentation review, not a local Halo execution or benchmark.

**Decision: retain as a distributed-training reference and credit the three
completed local contract improvements it informed. Do not install or replace
the Mac runtime.** The public [inspiration article](https://posttrainllm.com/inspiration/halo)
previously retained only a short architecture summary; the issue history shows
that the research also led to concrete work in September.

## What Halo does

Halo adds training and distributed behavior to existing Hugging Face models.
Its trainers extend Transformers/TRL; wrappers and PyTorch sharding add scale
without maintaining a second model architecture. Gathered full-model exports
remain Hugging Face checkpoints, while adapters and optional expert shards
need their own loading or merging path.
[Architecture](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/README.md).

| Capability                                             | What to retain for this lab                                                                                                                                       |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pre-training and SFT; LoRA and QLoRA                   | Shared training infrastructure and small-to-large configuration paths; no evidence of a runnable Mac backend                                                      |
| DPO, KTO, SMPO and reward modeling                     | Separate preference objectives and reward learning from inference-time presentation                                                                               |
| Offline and online GRPO; asynchronous environment GRPO | Distinguish recorded rewards, single-turn verifiers, and multi-turn tool/environment trajectories                                                                 |
| Teacher and self-distillation; online SDPG             | Distinguish a frozen external teacher, a hint-conditioned self-teacher, and on-policy rollouts; do not equate them with our existing response-distillation recipe |
| Classification, embeddings and multimodal training     | Broader framework coverage, not authorization to reopen our parked VLM lane                                                                                       |
| Data preparation and export utilities                  | Offline tokenization/packing/sharding, adapter merging, expert-shard merging, and serving-layout conversion                                                       |

The [distillation contract](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/agent-docs/training-methods/distillation/README.md)
also states that those methods do not support context or pipeline parallelism.
The [model matrix](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/agent-docs/models/README.md)
is family- and mode-specific. A general framework capability does not establish
every combination of model, method, parallelism, precision, and serving engine.

## The single-Mac-to-cluster boundary

| Mode                            | Bottleneck addressed                                        | Cost or boundary                                                                        |
| ------------------------------- | ----------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| FSDP2 / data parallelism        | Replicas and sharded parameters, gradients, optimizer state | Synchronization and parameter gathers; requires multiple devices for this scale benefit |
| Expert parallelism (EP)         | MoE experts exceed one device's capacity                    | Token dispatch/combine traffic across devices through DeepEP                            |
| Context parallelism (CP)        | Long-sequence activations and attention                     | Sequence partitioning and communication; capacity need not improve speed                |
| Tensor parallelism (TP)         | Dense weights and matrix operations                         | Sharded tensors with inter-device communication; family/layout restrictions apply       |
| Expert-tensor parallelism (ETP) | An individual expert is too large                           | Shards expert FFNs; experimental and combination-dependent                              |

Sources: [parallelism](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/human-docs/parallelism.md)
and [performance tradeoffs](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/human-docs/performance.md).
More sharding buys capacity but adds communication; use the smallest topology
that fits rather than assume more devices or parallelism means more speed.
Our [Mac mastery map](mac-mastery-map.md) remains the local learning entrance.

The documented runtime requires NVIDIA drivers, the NVIDIA Container Toolkit,
and CUDA Docker images for Blackwell or Hopper. Consumer Ampere/Ada single-GPU
LoRA/QLoRA is documented but unvalidated upstream. Published images are x86_64;
even NVIDIA Grace ARM hosts require a different build. There is no documented
Metal, MPS, MLX, or Apple Silicon training path. Docker on this Mac does not
provide the required NVIDIA GPU.
[Installation requirements](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/human-docs/installation.md).

## Research already translated into this repository

All three issues are closed and the corresponding implementations are present
in `main`. This review verified source and history; it did not rerun model
training or native benchmarks.

| Completed work                                                                                    | Local evidence                                                                                                                                                               | Limit of the adoption                                                                                                                                                                                                                                                               |
| ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [#159: agentic trajectory export](https://github.com/PostTrainLLM/posttrainllm/issues/159)        | [Trace recipe](../recipes/from-traces.md), `AgentTrajectoryExport.swift`, `SFTCorpus.swift`, `TrajectoryExportTests.swift`; commit `d43b4c8`                                 | `--export trajectory` preserves calls, observations, full conditioning context and supervision flags. The trainer tokenizes blocks and masks supervised spans. Recorded `output_ids` are retained for future consumers; this is not Halo's complete sampled-token/log-prob RL path. |
| [#161: operation-specific compatibility](https://github.com/PostTrainLLM/posttrainllm/issues/161) | `TinyGPTCheck/ModelCompatibilityContract.swift` and `ModelCheckReport.swift`, `TinyGPTRun/ModelRunner.swift`, `ModelCheckTests.swift`                                        | Separates inspect/download/load/inference/LoRA/agentic predictions from matching device receipts. A successful generation does not verify training or tool use. No distributed compatibility checker was adopted.                                                                   |
| [#162: artifact lifecycle contracts](https://github.com/PostTrainLLM/posttrainllm/issues/162)     | [Artifact lifecycle](../factory/artifact-lifecycle.md), `TinyGPTIO/ArtifactLifecycleManifest.swift`, `ArtifactLifecycleManifestTests.swift`; implementation commit `60787f1` | Records identity, base/tokenizer, production history, runtimes, next actions and relative receipts. Exact resume requires checkpoint, optimizer, scheduler and RNG state; a weights-only artifact permits a warm restart.                                                           |

Paths above are under `native-mac/Sources/` or `native-mac/Tests/`.
The issues explicitly cite Halo's
[rollout contract](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/agent-docs/training-methods/grpo/async-grpo/rollouts.md),
[supported matrix](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/human-docs/supported-matrix.md),
and [checkpoint lifecycle](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/human-docs/checkpoints.md),
respectively. These are adopted ideas, not vendored Halo code or a Halo dependency.

## Techniques worth retaining, without opening new work

- **Trajectory fidelity:** retain context and tool observations, supervise the
  actions that produced an answer, and distinguish attention-valid tokens from
  loss targets. Keep the serving and training templates aligned; parser errors
  can turn actions into ordinary text. Pin exact sampled IDs when the learning
  objective depends on the sampled policy.
- **Asynchronous correctness:** Halo separates Transformers optimization from
  vLLM/SGLang serving, uses Ray environment workers and NCCL weight transfer,
  and overlaps rollouts with training. This introduces policy lag; sampled
  log-prob capture, importance correction, invalid-row accounting and weight-sync
  diagnostics belong to the algorithm's contract, not just orchestration.
  [Async loop](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/agent-docs/training-methods/grpo/async-grpo/README.md),
  [objective and stability](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/agent-docs/training-methods/grpo/async-grpo/objective.md).
- **Portable weights versus exact resume:** a gathered HF model may load for
  inference, an adapter still needs its base, and expert shards need merging.
  Topology changes can turn an exact resume into a warm restart. A serving
  engine can also reject or misread a layout that Transformers accepts.
- **Measure the actual bottleneck:** packing, batch shape, optimizer state and
  communication can matter more than lower compute precision. Treat full-bf16
  optimizer state with stochastic rounding and low-precision MoE kernels as
  hypotheses for a separately approved numerical/performance comparison,
  not automatic upgrades to our reference implementation.

## Benchmark claims and evidence limits

White Circle reports up to roughly **2.8× stock TRL throughput for GPT-OSS-20B
on eight B300s**. Its latest source also includes a Gemma 4 26B-A4B comparison
against Axolotl, NeMo AutoModel, Unsloth, Megatron Bridge and MS-SWIFT on two
B300s, with matched data/labels/order and optimizer hyperparameters, but each
framework's selected configuration. Rates average valid runs; runs with more
than 2% deviation in initial token-weighted loss are excluded. This is a
specific upstream protocol, not a universal ranking or Mac performance result.
[Benchmark setup, tables and harness links](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/agent-docs/optimization/throughput-benchmarks.md).

No Halo installation, GPU test, benchmark reproduction, convergence evaluation,
Mac interoperability test, or model-quality comparison was performed here.
Any future measurement must freeze model/data/template/loss, token accounting,
hardware/topology, precision/optimizer, warmup, memory definition and regression
gate. Compare total run cost and retained capability alongside throughput.

## License and adoption decision

The source declares **LicenseRef-Halo**, not unmodified Apache-2.0. Its
[license](https://github.com/whitecircle/halo/blob/50dab99eafa89bd215b8f342bf7a0259d4ee26b1/LICENSE)
adds terms to Apache-2.0: training-as-a-service revenue above US $20 million
over twelve consecutive months requires a commercial agreement; annual revenue
above that threshold triggers model attribution; redistributed derivatives must
carry the supplemental terms. This records the published terms, without making
an adoption-specific legal determination.

Retain the contracts and source links. Keep the CUDA/distributed runtime,
online RL, new optimizer experiments and model downloads parked. If an owner
opens a fresh factory question, select a frozen baseline and held-out gate,
exact model and data revisions, regression metric, hardware and fixed resource
budget under [the admission rule](../NEXT.md). Only then compare Halo with the
existing Mac implementation or a separately funded NVIDIA run. There is no
implicit next experiment from this review.
