# External Products And Research Reviewed

This page records products, startups, papers, and blogs that changed the posttrainllm
roadmap. It is a teardown ledger: what we learned, what we stole, what we
rejected, and what still needs a local experiment.

## Review Standard

Every external review should answer:

- What is the source?
- What claim or technique matters?
- Is it method-level or recipe-level?
- What is the posttrainllm translation?
- Did we adopt, scaffold, try, reject, or park it?
- What is the next smallest experiment?

## Reviewed Sources

| Source | What Mattered | posttrainllm Translation | Status | Next Action |
|---|---|---|---|---|
| TrainLoop AI | Case studies emphasize failed-attempt accounting, slice metrics, trace review, candidate selection, batch-first post-training, policy lag, and LoRA geometry | Added technique registry, SQL candidate-selection tooling, slice metrics, trace review, batch plan renderer, LoRA geometry docs/tooling | `scaffolded` | Run SQL candidate-selection model experiment |
| TrainLoop NollaMD case study | Multiple-choice/candidate-selection framing can unlock sparse tasks where open generation is too hard | Use SQL candidate selection before open SQL generation | `scaffolded` | Build/train/eval candidate-selection SQL recipe |
| TrainLoop OAPL writeup | Batch rollouts + offline scoring + compact update; policy lag can stabilize learning | Add batch post-training plan and defer OAPL-style run until reward surface is clean | `scaffolded` | Use after candidate-selection has evidence |
| TrainLoop LoRA writeup | Effective-update geometry and controlled rank/layer analysis matter | Add LoRA geometry diagnostics and plan a controlled rank sweep | `scaffolded` | Attach `lora-geometry.json` to next adapter run |
| TrainLoop Mercor coding-agent post | Coding-native harnesses can beat bespoke tool APIs for knowledge-work agents | Keep future coding-agent/product work file/code-native | `parked` | Revisit when coding-agent product becomes active |
| Baseten post-training positioning | Post-training is custom data + RL/reward shaping + performance + infra, not generic fine-tune UI | Reframed posttrainllm as Mac-local specialist factory | `adopted` | Keep factory docs centered on data/post-training/eval/perf/package/report |
| Hugging Face model hub / SQL specialists | Small public SQL models create realistic baselines | Compared against `cssupport/t5-small-awesome-text-to-sql`; scanned `prem-1B-SQL`, Qwen SQL variants, SQLCoder | `tried` | Add public execution benchmark before claiming serious SQL competitiveness |
| Defog SQLCoder / Arctic Text2SQL class models | Strong SQL systems report execution accuracy on serious SQL benchmarks, not only exact string match | Treat BIRD/Spider execution as required next public SQL gate | `adopted` | Build/run Spider or BIRD Mini execution gate |
| Apple on-device Foundation Models | Useful as a free routing floor, not a capability dependency | Documented measured limitations and ruled out adapter dependency | `rejected-for-core` | Keep our own model/eval gate as differentiation |
| Castform RL fine-tune platform | Composite rewards and trace-driven data loops | Mapped into composite reward, trace-to-data, reasoning-depth classification | `partially-adopted` | Integrate reward framework with training loops before RLVR |
| Cline / agent context hierarchy research | Structured-output enforcement and context hierarchy patterns | Added deferred tools/context hierarchy learnings | `partially-adopted` | Revisit only when coding-agent product returns |
| Gigatoken | SIMD, cache-heavy bulk BPE can make first-pass tokenization dramatically faster on large corpora, including Qwen on Apple Silicon | No current blocker solved; keep as an optional offline data-prep accelerator, not a core/default tokenizer | `parked` | Revisit only for multi-GB corpora or measured tokenization above 10% of run time; require exact token-ID parity and bounded peak-RSS checks on the real tokenizer/corpus |
| Needle 2 | A 44.9M call-only model combines top-five tool retrieval, schema-constrained decoding, confidence escalation, bounded context, quantization, and a roughly 14 MB packaged Mac artifact | A 94-case local smoke produced only 34.0% tool exactness. An oracle task-family catalog ablation reached 38.3% overall but regressed Pace to 6/28 and retained three out-of-scope false actions | `reviewed-rejected` | Stop before mobile-actions, integration, or fine-tuning; catalog restriction is a latency lever, not a capability rescue |
| parakeet.wgsl | Raw WebGPU + SIMD-WASM browser inference for Parakeet TDT 0.6B, with public kernels, package format, cache, converter, and benchmark harness | The pinned package transcribed a 17m 10s public fixture in 7.2–7.8 seconds on Apple WebGPU; 29 cached assets totaled 405,252,493 bytes and warm output was deterministic with no external request observed | `validated-proof` | Run a small shared reference-transcribed comparison against WhisperKit before integration; keep the 386.5 MiB download explicit and optional |

## Gaps Exposed By Reviews

1. The old roadmap had methods, but not enough recipes.
2. External teardown was ad hoc; it must become mandatory before major runs.
3. Attempt results were scattered across specialist docs, run reports, and
   public artifacts.
4. Public claims need serious benchmark alignment: exact match is not enough for
   SQL, and self-reported external metrics must be labeled as directional.
5. Docs need validators so discipline is enforced, not just written.

## Required Review Before A New Target

Before picking a new factory target, do a short teardown:

1. Three competitor/startup examples.
2. Three relevant papers/blogs.
3. Three techniques worth trying.
4. Three techniques rejected and why.
5. One cheapest local recipe selected for the first run.

Store the result here or in a target-specific file under `docs/techniques/`.
