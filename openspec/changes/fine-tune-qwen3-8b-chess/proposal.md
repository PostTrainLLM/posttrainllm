## Why

The specialist factory needs a target that exercises state-to-action learning, verifiable rewards, recovery from model-induced states, and honest Mac-scale cost accounting. A Qwen3-8B chess specialist is a strong factory proof because legality and move quality can be scored deterministically with a chess engine, while the 8B size forces the repo to resolve or explicitly route around its real packed-base QLoRA gap.

## What Changes

- Add a frozen chess-specialist run contract: FEN plus game history in, exactly one UCI move out. Commentary, free-form play, GUI work, and chess-engine replacement are out of scope.
- Add a reproducible data pipeline that turns permissively licensed games and Stockfish-labelled positions into train/dev/test rows, preserves game-level split isolation, includes recovery and adverse positions, and records source hashes and engine settings.
- Add a no-training baseline gate for the exact pinned Qwen3-8B revision before deciding whether adaptation is justified.
- Add deterministic chess evaluation for legal-move rate, tactical task success, engine-relative move quality, short-match outcomes, parse failures, and general-language regression.
- Add a staged recipe: SFT/behavior cloning first, then optional preference or verifiable-reward training only when frozen failure slices justify it. Every stage has a stop rule.
- Require a real packed 4-bit base for 8B adapter training. The current simulated `posttrainllm sft --qlora` path cannot be reported as an 8B QLoRA result; implementation must either complete the native packed-base path or use the established `mlx_lm` fallback while retaining posttrainllm's eval, packaging, and report contracts.
- Emit the standard factory run folder and create `specialists/<id>/` only after a `ship` decision.
- Do not download model weights, install tools, start Stockfish sweeps, train, or run GPU-heavy evaluation as part of this proposal.

## Capabilities

### New Capabilities

- `chess-specialist-run`: Defines the input/output protocol, data provenance and splits, staged post-training recipe, frozen chess and regression gates, Mac performance reporting, and ship/retry/reject contract for a Qwen3-8B chess specialist.

### Modified Capabilities

None. This repository has no existing OpenSpec capability specifications; the change composes existing factory primitives without changing their public contracts.

## Impact

- Expected implementation surfaces: `scripts/` for dataset preparation and engine-backed scoring, `evals/chess/` for small committed fixtures and frozen manifests, `docs/techniques/` for the recipe card, `runs/` for ignored run output, and `specialists/` only after a ship decision.
- Training touches the existing Swift/MLX SFT/PEFT path or the documented Python `mlx_lm` fallback. Native packed-base QLoRA remains a prerequisite if the Swift path is selected.
- Likely development-only tools are a maintained chess rules library and a pinned Stockfish executable. They are justified by the repo's adopt-first policy: legal move generation, FEN/PGN parsing, UCI integration, and engine scoring should not be reimplemented.
- The work is local-only. It does not add a product UI, Pace dependency, deployment, production service, or browser/WebGPU track.
- All model/training/engine sweeps remain operator-approved heavy work and must respect the repo GPU lock and process-cleanup rules.
