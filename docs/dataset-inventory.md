# Dataset inventory

Live snapshot of `~/.cache/posttrainllm/datasets/` (not checked into the
repo). Last refreshed 2026-06-17. Sizes are directory totals; row
counts are from decoded JSONLs where available, otherwise marked as
parquet-on-disk.

## Specialist-track training corpora

| Dataset | Path | Size | Decoded JSONL | Use | Status |
|---|---|---:|---|---|---|
| `NousResearch/hermes-function-calling-v1` | `NousResearch/` | 113 MB | `hermes-fc.jsonl` (49.8 MB) | A1 tool-caller SFT (Apache 2.0) | ✅ decoded |
| `Locutusque/function-calling-chatml` | `Locutusque/data/` | 102 MB | `function-calling-chatml.jsonl` (333 MB) | A1 tool-caller SFT | ✅ decoded |
| `Salesforce/xlam-function-calling-60k` | `Salesforce/xlam-function-calling-60k/xlam_function_calling_60k.json` | 91.7 MB | ~60K rows | A1 tool-caller SFT (gated) | ✅ pulled 2026-06-17 (token + license click) |
| `yahma/alpaca-cleaned` | `yahma/` | 82 MB | — | General-instruction SFT baseline | ✅ on disk |
| `Intel/orca_dpo_pairs` | `Intel/` | 67 MB | — | DPO preference data | ✅ on disk |
| `argilla/ultrafeedback-binarized-preferences-cleaned` | `argilla/` | 137 MB | `ultrafeedback.jsonl` | DPO preference data | ✅ decoded |
| `meta-math/MetaMathQA` | `meta-math/` | 663 MB | — | Math specialist SFT | ✅ on disk |
| `iamtarun/python_code_instructions_18k_alpaca` | `iamtarun/data/` | 11 MB | `python-code-instr.jsonl` (18 612 rows) | Code specialist SFT | ✅ decoded |
| `bigcode/the-stack-smol` | `bigcode/the-stack-smol/data/{c,c++,go,java,javascript,python,rust,typescript}/data.json` | ~850 MB | 8 langs (of 30 in repo) | Code specialist pretrain | ✅ pulled 2026-06-17 (token + license click) |
| `HuggingFaceFW/fineweb-edu` | `HuggingFaceFW/` + `fineweb-edu.txt` (230 MB) | 2.2 GB | `fineweb-edu.txt` (50K-row sample) | Pretrain quality baseline | ✅ sampled |

## ScaleDown (B25) corpora — pulled 2026-06-17

| Dataset | Path | Size | Use |
|---|---|---:|---|
| `microsoft/ms_marco` v1.1 | `microsoft/ms_marco/v1.1/` | 207 MB | `(query, doc, answer)` triplets for context-compression training. Test 19.5 MB + train 167 MB + val 20 MB. v2.1 (7 train shards) not pulled — would add ~1 GB if needed. |
| `google-research-datasets/natural_questions` | `google-research-datasets/natural_questions/default/` | 375 MB | NQ training data subset (2 of 287 shards). Full pull would be multi-GB; current subset bounds disk. |

## Eval splits (D5)

| Dataset | Path | Rows | Use |
|---|---|---:|---|
| `openai/gsm8k` (main) | `openai/gsm8k/main/` | 1 319 test / 7 473 train (parquet) | Math reasoning eval (E3 + E4) |
| `HuggingFaceH4/MATH-500` | `HuggingFaceH4/MATH-500/test.jsonl` | 500 | Canonical MATH eval (subject, level, problem, solution, answer) |
| `openai/openai_humaneval` | `openai/openai_humaneval/openai_humaneval/` | 164 (parquet) | Code-gen eval (E5) |
| `google-research-datasets/mbpp` (full) | `google-research-datasets/mbpp/full/` | 974 (parquet, prompt+test+train+val) | Code-gen eval (E5) |
| `princeton-nlp/SWE-bench_Verified` | `princeton-nlp/data/` | 500 (parquet) | Code repair eval (later A1) |

## Indic / multilingual

| Dataset | Path | Size | Use |
|---|---|---:|---|
| `google/IndicGenBench_xquad_in` | `google/IndicGenBench_xquad_in/` | 45 MB | A5 — Indic XQuAD splits across as/bn/gu/en + more |
| `ai4bharat/MILU` | `ai4bharat/MILU/` | 0 B | A5 — MILU is an lm-eval-harness task, not raw rows; harness code is at `_external/MILU/` |

## Pace planner data (in-repo specialist work)

| File | Size | Use |
|---|---:|---|
| `pace-prompts.jsonl` / `pace-prompts-v2.jsonl` / `pace-prompts-v3.jsonl` | 4 KB → 39 KB → 12 KB | Planner prompt corpus (versioned) |
| `pace-labeled.jsonl` / `pace-labeled-v2.jsonl` / `pace-labeled-v3.jsonl` | 13 KB → 116 KB → 25 KB | Labeled planner intents |
| `pace-sft-v2.jsonl` / `pace-sft-v3.jsonl` | 36 KB / 14 KB | SFT pairs for planner |
| `clarify-seeds.jsonl` / `clarify-train-v1.jsonl` / `clarify-dpo-v1.jsonl` | 15 KB / 15 KB / 76 KB | Clarify-action seed + train + DPO |

## External evaluators (source code, not data)

`_external/` holds checked-out harness repos that the `posttrainllm eval-*`
subcommands shell out to:

| Path | Role |
|---|---|
| `_external/gorilla-bfcl/` | BFCL harness — invoked by `posttrainllm eval-bfcl` (E1) |
| `_external/tau-bench/` | τ-bench harness — invoked by `posttrainllm eval-tau-bench` (E2) |
| `_external/MILU/` | lm-eval-harness MILU task config |

## Outstanding gaps

1. **MS-MARCO v2.1** — only v1.1 is pulled; v2.1 has 7 train shards (~1 GB) if B25 needs additional training data.
2. **Natural Questions** — only 2/287 train shards; pull more if B25 needs broader coverage.
3. **the-stack-smol additional langs** — 8/30 pulled (c, c++, go, java, javascript, python, rust, typescript). Add more (haskell, lua, ruby, scala, kotlin, etc.) if the code specialist needs broader exposure.

All other items in PLAN.md Tier D are satisfied.
