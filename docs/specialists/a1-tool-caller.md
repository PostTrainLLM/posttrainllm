# A1 — first tool-calling specialist

**Base:** `qwen3-4b-instruct-2507` · **Method:** LoRA SFT (rank 16, layer-wise
LR decay) · **Ship gate:** +3pp on the Berkeley Function-Calling Leaderboard
(BFCL) over the stock base.

A1 is the north-star validator for the Mac-first specialist factory: prove that
a from-a-laptop LoRA can measurably beat the base on a public function-calling
benchmark.

## Build it

```bash
BFCL_ROOT=~/bfcl DATA=tools.jsonl bash scripts/recipes/a1-tool-caller.sh
```

The recipe (`scripts/recipes/a1-tool-caller.sh`) runs four shipped steps:

1. **Baseline** — `eval-bfcl <base>` → `baseline.jsonl`.
2. **Train** — `sft <base> --data tools.jsonl --rank 16 --steps 2000 --llrd 0.9`
   → `a1.lora`. (`--llrd` is B15 layer-wise LR decay.)
3. **Adapter eval** — `eval-bfcl <base> --lora a1.lora` → `candidate.jsonl`
   (the `--lora` passthrough added for this PRD serves base+adapter for BFCL).
4. **Gate** — `eval-gate --baseline baseline.jsonl --candidate candidate.jsonl
   --threshold 3` (B32); non-zero exit if the adapter doesn't clear +3pp.

## Data

`DATA` is a chatml SFT JSONL of `{instruction, input?, response}` tool-calling
examples (e.g. an xLAM / glaive-function-calling export, or `tinygpt synthesize`
output). The recipe is data-agnostic; the gate is the contract.

## Acceptance

```bash
BFCL_ROOT=~/bfcl ADAPTER=specialists/a1-tool-caller/a1.lora bash evals/a1-acceptance.sh
```

Re-runs the +3pp gate from a clean checkout against a built adapter.

## Status

**Recipe + acceptance harness shipped (2026-06-20); the training run is
pending a GPU Mac + a local BFCL checkout** — `eval-bfcl`/`sft`/`eval-gate`
exist and are wired, but the 4B adapter has not been trained or scored here.
Fill in the achieved BFCL delta + leaderboard row once the run completes.

## Reuse

This recipe is the template for the specialist family: B1 (second domain),
B8 (multilingual), B25 (compression). Cookie-cut the four steps, swap `DATA`
and the eval suite.
