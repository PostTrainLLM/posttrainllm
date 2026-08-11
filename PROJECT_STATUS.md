# posttrainllm — PROJECT STATUS

Last updated: 2026-08-09

## Why / What

posttrainllm is a **Mac-local specialist factory**.

The active product loop is:

```text
target -> data -> post-training -> eval -> package -> report
```

The browser playground, Python reference, WASM/WebGPU training path, native
Swift/MLX runtime, eval harnesses, and research docs are all assets for that
factory. They are not all active product centers.

For Pace, posttrainllm is a development-time factory and eval lab: it can prepare
planner data, adapters, specialist packages, eval fixtures, and reports. Pace
production must not depend on `posttrainllm serve`, localhost, or this repo's dev
runtime.

Current proof points:

- First registered specialist package:
  `specialists/qwen3-4b-file-ops-distilled`.
- It improves file-ops hard gate from 58% to 100%, but regresses
  out-of-domain breadth from 59.6% to 42.3%.
- Therefore it is a routed specialist, not a general planner.
- Second registered specialist package:
  `specialists/qwen3-4b-rest-fused`.
- Its recorded teacher-free ReST run retains the 100% file-ops gate and raises
  the same breadth family from the stock 59.6% to 65%. It ships as a research
  specialist, not a Pace default; historical performance and raw trace logs
  were not preserved and are disclosed as missing evidence.

The full loop has executed end-to-end with both outcomes: the frozen
`qwen06-sql-hygiene-dpo-v1` run ended in a documented **retry-training**
decision, while `qwen3-4b-rest-fused` now has a canonical assembled run,
package, public weights, and narrow **ship** decision. The latter promotes
existing measured evidence; it does not pretend the missing historical
latency/RAM/tok-s and raw traces were recreated.

## Dependencies

| Surface | Location | Role |
|---|---|---|
| Native CLI | `native-mac/Sources/TinyGPT/` | Main factory surface: train, SFT, DPO, distill, eval, serve, trace, package |
| Native model/runtime libs | `native-mac/Sources/TinyGPTModel/`, `TinyGPTServe/`, `TinyGPTData/` | MLX/HF loading, PEFT, rewards, eval helpers, OpenAI-compatible serving |
| Eval scripts | `evals/`, `scripts/` | No-GPU smokes, BFCL/Pace helpers, benchmark/report scripts |
| Browser site | `browser/` | Public demo and readout surfaces; not the active factory control plane |
| WASM/WebGPU | `wasm/`, `webgpu/`, `browser/src/` | Completed learning/perf track; parked unless factory proof needs it |
| Python reference | `python_ref/` | Correctness/reference path for from-scratch pieces |
| Active roadmap | `docs/NEXT.md` | Current sequence only |
| Factory docs | `docs/factory/` | Run schema, eval protocol, packaging, reports |
| Technique registry | `docs/techniques/` | Method-vs-recipe cards, audit inventory, external teardowns, target-specific experiment backlog |
| Docs hub | `docs/README.md` | Golden path through state, attempts, reviewed products, roadmap, and learning |
| Attempt ledger | `docs/attempt-ledger.md` | Worked/failed/regressed/not-tried attempt history |
| External review ledger | `docs/external-products-reviewed.md` | Products, papers, startups, and techniques reviewed or stolen |
| Learning pipeline | `docs/learning-pipeline.md` | Owner learning sequence tied to active factory work |
| Parked lanes | `docs/parked/` | Explicitly paused work so it does not compete with factory proof |
| Detailed backlog | `docs/prds/`, `docs/PLAN.md` | Historical and deep task inventory; not the first navigation layer |

Important constraints:

- Do not run long GPU/model-training loops without explicit owner approval.
- Respect `~/.cache/posttrainllm/gpu.lock` before training.
- Do not touch secrets, cloud credentials, production configs, or Pace runtime
  wiring unless explicitly asked.
- Prefer no-GPU smokes and fixture checks before heavier validation.

## Timeline

| Date / phase | Status |
|---|---|
| 2026-08-11 Native Mac distribution preparation | Added repeatable arm64 Release app assembly with the branded icon, versioned bundle metadata, hardened-runtime Developer ID signing support, strict signature verification, and a fail-closed notarization helper. The locally verified build remains ad-hoc signed until the personal Developer ID identity and notary profile are installed; no public release was created. |
| 2026-08-09 Everyday benchmark + capability graph | Shipped the dependency-free Everyday Specialist Benchmark contract, three frontier-qualified deterministic task rulers, evidence-linked static cohort report, and additive validated specialist capability graph with policy filtering, verified fallback, privacy-safe traces, residency/resource accounting, and system adapters. The first approved measured system calibration is an explicit rejection: Pace v8 scored 60.7%, Apple on-device fallback 85.7%, no threshold passed the frozen selective gates, and even the perfect-router oracle reached only 96.4% versus the 99% final target. No model was trained, downloaded, deployed, or promoted; the negative result prevents strong standalone leaves from hiding a weak routed system. |
| 2026-08-08 Complete published-model case studies | Reconciled the live PostTrainLLM Hugging Face inventory to six public model repositories and gave every model a first-class evidence page under `/artifacts`: Pace v8's sealed-eval rejection, the routed file-ops win, the ReST breadth recovery, the multibackend negative-transfer failure, the VibeThinker MLX conversion, and the unevaluated agentic distillation. The pages distinguish public weights from ship decisions and explicitly reject Hub request counts as proof of users or successful runs. The production build emits all six as static HTML, Markdown counterparts, sitemap entries, and agent-catalog records. |
| 2026-08-07 Apple Silicon comparison coverage | Added source-complete PostTrainLLM comparisons for Unsloth and Axolotl through the existing editorial, sitemap, canonical, and agent-readable surfaces. Each page cites current primary documentation, distinguishes Mac-native training from partial or in-progress support, and explicitly avoids unsupported speed, memory, or quality claims. Production remains unchanged pending the normal manual deployment path. |
| 2026-08-05 Mac-local specialist field guides | Added five public evidence-first guides for Mac fine-tuning, MLX LoRA/QLoRA, local evaluation, trajectory datasets, and routed small-model specialists. They preserve the research-bench visual system, connect home/recipes/artifacts to the factory loop, and enter the generated sitemap, Markdown, and agent catalog from the same public build. The full build now verifies 331 public HTML/Markdown pairs. |
| 2026-08-05 Character Chess 44.53M masked 10k pilot | **Failed; current Character Chess training lane dropped before 100k.** The owner-approved bounded pilot compiled 12,000 CC0 Lichess-eval rows with zero split overlap and trained on 10,000 general-position terse examples for 2,000 MPS steps using completion-only loss. Validation loss fell `5.8171 -> 1.3831`, and the model learned a real but weak held-out move signal: validation exact was 10.54% versus 6.16% analytic random (+4.38 points); test was 10.33% versus 6.23% (+4.10). That missed the frozen +10-point promotion gate. The decisive transfer screen produced 0 wins, 6 draws, 0 losses against random legal play for the raw policy and the same 0/6/0 for the guarded policy. Guards fired 22 times and changed eight moves, but converted no wins. The displayed 536 is only equality with the single random-floor rung over six games, not a qualified full-ladder or human Elo. Therefore no 100k/1M/2M stage or 4B/9B comparison is justified under this recipe. The failed artifact preserves the why: prompt masking and canonical castling fixed real pipeline bugs; local move prediction improved, but it did not become game-playing strength. Evidence: `evals/chess/character-chess-44m-pilot-10k-v1.json`; raw checkpoint and traces remain gitignored under `runs/chess-44m-pilot-10k-2026-08-05/`. |
| 2026-08-05 Character Chess 44.53M internal Stockfish rating | **Below the calibrated ladder floor: <536 Internal Stockfish-ladder Elo; not human/FIDE Elo.** The fitted 475 estimate (paired-opening bootstrap 416–550) is retained only as a diagnostic extrapolation. With explicit owner approval, five weak policies were calibrated in 60 paired games to Stockfish 18's UCI-1320 floor: random legal 536, 50% random/Skill-0 732, 25% random 851, 10% random 1027, and UCI-1320 fixed at 1320. The eight-position memorization checkpoint then played 30 balanced games across three openings and all five rungs: 0 wins, 9 draws, 21 losses, 15 games per color, 100% legal execution, no forfeits, and 90% natural completion. It drew all six random games, scored one draw against each mixed rung, and lost all six UCI-1320 games. Excluding three artificial 160-ply draws gives a 457 extrapolation. The result is decisive for this checkpoint: constraint selection guarantees legality but eight-position training did not create chess intelligence. Calibration took 24.54 seconds; candidate matches took 123.30 seconds with 1,985,118,208-byte peak RSS. The GPU lock was released and no process remains. No 10k pilot, 4B/9B same-ladder comparison, human-Elo claim, deployment, commit, or push occurred. Evidence: `evals/chess/character-chess-44m-stockfish-rating-v1.json`; full local traces remain under `runs/chess-44m-stockfish-rating-2026-08-05/`. |
| 2026-08-05 Qwen Chess serving-policy reproduction scaffold | Independently reproduced the current public serving/evaluation ideas without copying weights or claiming the 8B result: the owned checkpoint already uses always-score legal argmax; a separate engine-free one-ply policy can deliver mate-in-one, avoid opponent mate-in-one, and avoid immediate draws in clearly won positions while recording every guard fire and intervention. Added an evaluation-only Stockfish 18 cp-loss grader (average, ≥100 cp blunder, ≥300 cp severe blunder), corrected below-ladder rating semantics, and froze matched terse/commentary 10k, 100k, 1M, and 2M composition stages. Raw and guarded policies require separate ratings; any serving-policy change invalidates the old rating. No new training, data download, Stockfish sweep, model load, deployment, commit, or push occurred. |
| 2026-08-05 Character Chess 44.53M tiny-overfit | **Passed the correctness gate; not chess-strength evidence.** With explicit owner approval, a bounded stream read nine CC0 Lichess evaluation records, accepted eight positions, and rejected one below the 10,000-knode floor. The eight sequences were repeated 64 times and the exact 44,527,616-parameter byte model trained on MPS under the cooperative GPU lock. Exact legal-target recall was non-monotonic—87.5% at step 50, 75% at step 100, then 100% at step 150—while recorded validation token loss fell from 5.5723 to 0.4884. The temporary dip is expected because token cross-entropy is not the discrete legal-candidate ranking objective; at step 150 all eight targets ranked first and the minimum target margin was +0.9763. Training stopped 50 steps before the cap after 307,200 tokens, 81.31 staged training seconds, and 608,665,600-byte peak RSS. The 549,286,640-byte resumable checkpoint remains local/gitignored; its SHA-256 is recorded. GPU lock was released and no process remains. No 10k pilot, large compile, held-out strength claim, Elo, model comparison, deployment, commit, or push occurred. Evidence: `evals/chess/character-chess-44m-tiny-overfit-v1.json`. |
| 2026-08-05 Character Chess sub-50M reproduction scaffold | **Offline reference path completed before the separately approved tiny run; no strength reproduced.** The external Qwen Chess “30M” was verified as a corpus-size milestone on Qwen3-8B, not a 30M-parameter model. This repo now independently provides a fail-closed CC0 Lichess-evaluation compiler, deterministic split-text rendering into the existing Python trainer, disjoint held-out identities and provenance manifests, an exactly counted 44,527,616-parameter byte-model config, a lazy Python-checkpoint legal-candidate evaluator, a frozen tiny-overfit/pilot/qualification recipe, and paired-color weak-Stockfish ladder infrastructure. The six-record compiler fixture accepted two valid labels and counted four explicit rejections. A bounded Stockfish 18 integration smoke completed four eight-ply paired games with 100% candidate legality and balanced colors; all move-capped as draws and correctly remained `unrated`. Final audit corrected the first estimator, which overcounted each MLP's biases by 35,840 parameters overall, and the first engine smoke exposed an invalid attempt to configure python-chess's managed `Ponder` option; both now have regression coverage. No large download, million-row compile, rung calibration, sustained match sweep, deployment, commit, or push occurred. Those steps remain separately owner-gated. Evidence: `openspec/changes/build-50m-character-chess-specialist/`, `docs/learn/reproducing-qwen-chess-under-50m.md`, and `evals/chess/strength-ladder-smoke-v1.json`. |
| 2026-08-05 Specialist factory walkthrough | **Static orientation surface complete locally; not deployed.** Added `/learn` as a six-chapter, source-linked journey through `target -> data -> post-training -> eval -> package -> report`, with canonical docs, exact implementation entrypoints, and current case files for an improvement, a routed regression, the rejected Character 2048 ruler, and still-unqualified Character Chess evidence. The page renders fully without client JavaScript and the existing publication tooling includes it in the sitemap, Markdown counterparts, `llms.txt`, and agent-readable catalog (331 application/docs pages total in the current dirty worktree build). Primary Learn navigation now routes through the walkthrough while the full curriculum remains directly linked. No model call, training, new result, deployment, commit, or push occurred. Evidence: `browser/src/pages/learn.astro`, `openspec/changes/add-specialist-factory-walkthrough/`, and `.fleet/evidence/factory-walkthrough/`. |
| 2026-08-05 Extensible character-game arena | **Candidate arena infrastructure complete; every current rating remains unqualified.** A versioned adapter registry now normalizes existing Character Chess head-to-head evidence and Character 2048 paired-score evidence into one deterministic report without model calls. The four chess games produce a regularized diagnostic Arena Elo of 1585.0 for Qwen3 4B and 1415.0 for Qwen3.5 9B, but both policies remain `unrated`: the pool has only 4/30 required games and a 50% forfeit rate versus the frozen ≤10% limit, and both nominal 4B wins are 9B notation forfeits. Character 2048 correctly receives no Elo; Claude Opus 4.8 is +10.67 paired score over random across 3 complete pairs (95% interval -8 to +28) and Claude Sonnet 5 is -1.0 across 4 pairs (-14 to +13), both below the 30-pair qualification minimum. The browser arena switches rating vocabulary by competition family, links to every replay, and exposes qualification before rank. No inference, training, network call, or cross-game universal score occurred. Evidence: `evals/game-arena/candidate-v1.json` and `/benchmarks/arena`. |
| 2026-08-05 Character Chess development gate | **Gate 0 passed for frozen-suite design; no specialist was trained.** A deterministic 20-position, engine-generated tactical screen produced a real capability gradient under the same strict characterwise FEN + sorted legal-UCI prompt: calibrated random legal play averaged 6.7375% over 2,000 cohorts; Qwen3 4B scored 0% exact / 95% legal at 294 ms mean; Qwen3.5 9B scored 10% exact / 90% legal at 577 ms; and the Codex `gpt-5.5` development alias scored 65% exact / 100% legal at 23.69 s. Direct API spend was $0 through the free Codex CLI and local MLX; per-call subscription/quota cost was not exposed or normalized. The frontier margin is +58.26 points over calibrated random and +55 points over the strongest local model, so unlike Character 2048, this ruler admits further benchmark design. It is **not yet a publishable benchmark**: the frontier alias is mutable and does not approach the repo's ~100% frozen-suite ceiling requirement, the positions are development-only and engine-generated, and no human-authored theme coverage exists. Four paired 4B-vs-9B games are replayable but deliberately non-ranking evidence: the two nominal 4B wins are 9B notation forfeits and the two draws are 14-ply repetitions. The browser archive now exposes Puzzle Arena and Match Arena with exact inputs, raw outputs, legality, latency, and downloadable traces. Next action: design a held-out, human-audited frozen suite, pin a frontier identity that aces it, then separately approve a 30–50M training recipe. Evidence: `evals/chess/` and `/benchmarks/chess`. |
| 2026-08-05 Character Chess expanded candidate audit | **Candidate data expanded; frontier-ceiling gate failed; no specialist training.** A predeclared generator produced 100 new non-overlapping positions. Stockfish 18 MultiPV at depths 16 and 20 kept the same top move for 100/100; 86 passed the 150 cp gap and PV-legality gate, and a deterministic 40-position slice was screened. Exact/assigned-position scores were GPT-5.5 medium 70% (40), GPT-5.4 medium 75% (40), GPT-5.4-mini 80% (10), Claude Sonnet 5 65% (20), Claude Opus 4.8 70% (10), and free Devin GLM-5.2 70% (20). GPT-5.5 high reasoning regressed to 60% (40), so additional reasoning did not establish a frontier ceiling. The calibrated random mean was 6.6825%; its displayed 12.5% representative cohort was the calibration's 95th percentile, not expected performance. Every executed move passed a python-chess legal-set membership check; provider failures/timeouts redirected, yielding 100% executed-move legality even where raw availability was lower. The admitted pool is ready for human miss review, **not freezing or small-model grading**. Evidence: `evals/chess/candidate-model-matrix-v1.json`, `evals/chess/deep-label-verification-v1.json`, and `/benchmarks/chess`. |
| 2026-08-04 Capability-gradient candidate lab | Added a no-model lab ranking eight deterministic text-only candidates and implementing two reference environments. An initial Devin draft was rejected on its quantitative claims; a second adversarial Devin audit and parent correction now make every implemented baseline replayable in CI over 2,000 seeds. **Calendar scheduling ranks first only as a frontier-gradient candidate:** calibrated random well-formed proposals succeed 28.05%, with 2.45% truly unsatisfiable instances. **Connect-4 is internal calibration only:** random X wins 54.75%, and solver/shallow-tactic saturation makes it unsafe as the public specialist proof. The scorecard now treats `frontier > random` and `<=50M specialist > larger LLM` as separate required gates. No frontier call, frozen suite, data, or training has run for either candidate. |
| 2026-08-04 Character 2048 capability-gradient screen | **Failed benchmark artifact; intentionally retained.** The deterministic character-only environment, strict/constrained adapters, local replays, and cloud provenance checks are complete, but the expected intelligence advantage did not reproduce and the ruler failed Gate 0. Pinned Claude Sonnet 5 completed four 32-move constrained games at 184 mean score versus 185 for paired random legal play (0.995x, paired bootstrap 95% CI -14 to 12.625). Pinned Claude Opus 4.8 completed three games at 196 versus 185.33 (1.058x, below the 1.10x bar) before a transient API disconnect invalidated game four. The Opus attempt cost $7.74 and is directional only; Sonnet cost $2.72 and is the valid screen. No 30-seed suite, synthetic trajectories, or 30–50M specialist training will run for this formulation. The public gallery preserves the attempt and its replays as negative evidence, not as a successful or complete reproduction. Evidence: `evals/game-2048/frontier-screening-sonnet-v1.json` and `evals/game-2048/frontier-screening-opus-v1.json`. |
| 2026-08-04 Canonical live run evidence | Added opt-in lifecycle integration for the next real factory target: Swift `sft --factory-run` records a bounded train summary, local time, and unshipped adapter only after a successful save; `eval-gate --factory-run` records one frozen primary suite's same-invocation baseline/candidate pair; `eval-compare --factory-run` derives compatible slice metrics without changing decision state. A pure `TinyGPTIO` boundary and no-model smoke prove `data-ready -> training -> trained -> evaluating -> evaluated` with no invented `decision.json`. Existing invocations are unchanged. No model was loaded or trained; one bounded live verification remains gated on the next owner-approved run. |
| 2026-07-31 Public agent indexing | Completed the source-level public discovery contract without deploying it: one post-build inventory now merges 24 application/research pages, 297 documentation pages, and 3 deterministic report cards. The shared inventory generates a 324-route sitemap, substantive Markdown counterparts, compact agent catalogs, and `llms.txt` indexes while keeping feeds, JSON evidence, local runs, models, private artifacts, and unpublished evidence outside the page sitemap. Report cards now carry canonical, social, robots, and structured metadata without changing `decision.json` authority. The 324-page build/check, 188 report-card checks, deterministic publication gate, and strict archived OpenSpec validation pass; no training, model loading, release, or deployment occurred. |
| 2026-07-29 Owned product changelog | Added a same-origin `/changelog` with concise, newest-first outcomes drawn only from verified factory milestones. The shared site header now exposes the page, while Roadmap routes to GitHub Issues and Source to the canonical repository. No model, training, runtime, or deployment behavior changed. |
| 2026-07-25 Autocorrect pilot | Completed tasks 5.4-5.5 with owner approval; GPU lock held and released, no lingering process. Trained on the pilot manifest's 12 train-split rows (4 development rows monitored, never trained on) and scored on the unchanged frozen `eval-v1.jsonl`. **The pilot regressed:** error reduction `+0.0625 -> -0.8125` (delta -0.875), meaning output moved further from the clean reference than the noisy input was; unnecessary edit rate 0.839 against a 0.005 bar; protected spans 0.867 -> 0.800. The failure mode is **overcorrection, not copy bias** — the model became a paraphraser (`remeber` -> `remind you`, `teh team` -> `your team`, `tomorroww` -> `tomorrow morning`) while leaving `repourt` unfixed; structural slices (casing, name, number, url) stayed clean at 1.0. Evidence: `evals/autocorrect/pilot-result-v1.json`. **Recipe defect found:** the run stopped at step 50 of 300 on `stop_on_clean_preservation_below: 0.995`, but the base's own zero-shot clean preservation is 0.667, so that ship-grade bar fires at the first evaluation regardless of training — the pilot is truncated evidence, not a fair test of the 300-step recipe. **Tasks 5.6-5.7 (edit-aware objective) are explicitly rejected** by this evidence: they up-weight edit positions, targeting the opposite of the measured failure and pushing toward task 5.7's own reject condition. No further training should run under `adapter-recipe-v1`; a v2 must separate training stop rules from ship bars, add data, and add a meaning-change guard. |
| 2026-07-25 Autocorrect tiny-overfit gate | Completed task 5.3 with owner approval; GPU lock acquired and released. The gate **passed**: exact match 1.0 at step 50 of a 200-step budget, loss 1.585 -> 0.030 with no non-finite step, 0.28 min wall time, 1,135 MiB peak RSS on MPS. Evidence in `evals/autocorrect/tiny-overfit-result-v1.json`; adapters stay in gitignored `runs/`. **The headline number is weaker than it looks:** all 8 fixture rows derive from one source document, so every target is the identical string and exact match 1.0 is reachable by memorizing one sentence. The gate proves the training path runs end to end and has capacity to fit the fixture; it is not evidence of correction ability. A forward-only diagnostic probe on unseen inputs confirmed the adapter did not collapse to a constant emitter, but showed copy bias (unseen typo copied through), memorization leakage (spurious `Please` prefix), and one instruction echo. No stop rule fired; no decision recorded, because a precondition gate is not a candidate outcome. First trained autocorrect adapter exists locally; no quality, packaging, or ship claim. |
| 2026-07-25 Autocorrect adapter recipe and training path | Completed tasks 5.1-5.2 of `build-mac-local-autocorrect-specialist` with no training. `evals/autocorrect/adapter-recipe-v1.json` freezes the ordinary supervised recipe (FLAN-T5-small, LoRA r8/alpha16 on `q`/`v` across encoder self-, decoder self-, and decoder cross-attention, AdamW 1e-3, float32, seed 20260725, batch 4, 200/300 steps, checkpoints every 50, and five stop rules). `scripts/autocorrect_adapter.py` implements the encoder-decoder path with a dependency-free stdlib layer and a lazily imported torch layer; LoRA is hand-rolled so torch, transformers, and peft stay off the project dependency surface. Measured forward-only on CPU against the real pinned base with zero optimizer steps: 48 adapted modules, 344,064 trainable parameters (0.4471%), logits bit-identical after injection (max absolute delta 0.0), no base tensor modified. 19 offline tests pass (`bash evals/autocorrect-adapter-smoke.sh`); the 10 torch-backed tests build a tiny randomly-initialized T5 and skip visibly where torch is absent, so CI reports 9/19 passed with 10 skipped rather than a false green. The suite proves load parity, frozen base, the `dL/dA == 0 while dL/dB != 0` gradient signature, save/load round-trip and fail-closed drift detection, padding masked to -100, refusal to truncate, and detection of twelve recipe mutations. Both autocorrect smokes added to the CI evals job. **No adapter was trained; `train` refuses without an explicit operator-approval flag.** Contract in `docs/factory/autocorrect-adapter-recipe.md`; concepts in `docs/learn/encoder-decoder-adapters.md`. |
| 2026-07-25 Autocorrect foundation and base bake-off | Completed tasks 1.1-4.5 of `build-mac-local-autocorrect-specialist`: correction contract and gates, 18-row original MIT smoke ruler, strict evaluator, leakage/provenance checks, Mac keyboard simulator, tiny/pilot manifests, Codex frontier calibration, and the owner-approved three-base offline bake-off. On an M5 Pro / 48 GB Mac, T5-small rewrote/translated text and ByT5-small repeated input while breaching both latency gates. FLAN-T5-small was selected only as the smallest plausibly trainable base: 6.25% zero-shot error reduction, 66.67% clean preservation, 86.67% protected-span preservation, 584 MiB peak RSS, 29.1 ms median one-token TTFT, and 124.5 ms median greedy end-to-end. Complete predictions, per-row timing/tokenization, strict slices, and runtime pins are committed in `evals/autocorrect/base-bakeoff-v1.json`. The 14-test foundation suite and strict OpenSpec validation pass. No training, adapter, package, or ship claim exists. |
| 2026-07-25 Durable factory-run lifecycle | Implemented `add-durable-factory-run-lifecycle`: new lifecycle-v1 runs emit authoritative `run-status.json` with legal phases, monotonic revisions, bounded transition/failure provenance, expected-revision CAS, short-lived locks, and atomic replacement. Verified advisory `current-run.json` / `latest-run.json` pointers are rebuilt from status scans; current automatically selects the most recently updated valid non-terminal run. `factory-run init/status/transition/list/reconcile` stay metadata-only, reconciliation defaults dry-run, and stale active runs remain active-with-warning until explicit operator action. Native render/validation, Python assembly success/failure, manual Mac app discovery, and privacy-safe Foundry receipts consume the shared contract. Legacy folders remain compatible and imports record only proven evidence. `decision.json` and explicit human publication/deployment authority are unchanged. No model load, GPU work, training, network operation, dependency, deploy, commit, or push. |
| 2026-07-25 Fine-Tune Report Card | Shipped `add-fine-tune-report-card`: a portable, versioned before/after proof contract compiled offline from evidence that already exists in the repo. `scripts/build_fine_tune_report_card.py` ingests either a canonical run folder or a committed specialist package and emits `report-card.json` plus a self-contained static page from one validated payload; `scripts/check_fine_tune_report_card.py` is the publication gate; `native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift` is the typed schema boundary, decoded against real compiler output by `evals/fine-tune-report-card-smoke.sh`. Every value carries an explicit measurement state (measured/derived/historical/skipped/missing/not-applicable), so absent latency/RAM/cost renders as *not recorded* rather than zero and a one-sided delta stays missing. Three real cards published to `/report-cards` and linked from `/artifacts` with outcome labels: file-ops distilled and ReST fused (`routed-ship`, historical evidence) and the SQL routed POC (`report-only`, measured). **No published card claims a verified ship** — that is the honest result, and each card lists its own blockers. Added optional run fragments `eval-validity.json` and `cost.json` (absent-tolerant) plus optional `artifact.routing_constraint`; before them a verified ship was unreachable by construction. Fails closed: leakage, an incomplete ship claim, or a regressing ship without a disclosed routing constraint exits non-zero and writes no artifact. 166 unit checks + 9 fixture outcome classes + a drift guard, wired into the CI evals job. No training, model load, GPU eval, upload, or release-policy change. |
| 2026-07-19 Foundry evidence receipts | Shipped `automate-posttrainllm` (fleet-automation-closure Store): privacy-safe evidence contract + receipt pipeline for the Foundry control plane. `docs/factory/foundry-evidence.md` is the canonical per-surface contract; `scripts/foundry_receipt.py` emits sanitized receipts (git, registry, run folders, nightly markers, CI); `scripts/check_foundry_receipt.py` validates shape, provenance completeness, manual publication authority, and absence of private payloads; `evals/foundry-receipt-smoke.sh` + `tests/test_foundry_receipt.py` (11 tests) prove private datasets/prompts/checkpoints/outputs cannot enter receipts. Existing public artifacts' quality claims are correctly blocked because their `eval_report.json` lack explicit `source_revision` — surfaced as a blocked gap, not papered over. No new production dependency, no auto-publication, no deploy. |
| 2026-07-16 Fine-Tune Report Card OpenSpec | Drafted `add-fine-tune-report-card`: compile existing factory-run evidence into versioned JSON and a static public before/after report with explicit regressions, leakage/eval validity, performance, missing/historical values, and ship/retry/reject semantics. The draft performs no training, model loading, GPU eval, upload, implementation, or release. |
| 2026-07-13 ReST candidate promotion | Promoted public `qwen3-4b-rest-fused` weights into the second registered specialist package. Canonical metadata run passes the strict publish check with a narrow research-specialist ship decision: file-ops depth 100%, breadth 65% vs stock 59.6%. Added BFCL standalone/monorepo path resolution. Historical timing/RAM/tok-s and raw traces remain explicitly unavailable; no heavy rerun or Pace wiring was performed. |
| 2026-07-11 ref-anchored DPO retries (×2) | Executed two full GPU factory loops on the frozen qwen06-sql-hygiene target. **(1)** Ref-anchored DPO (50 steps, lr 5e-6) **fixed the SimPO collapse** — composed exec 0.860 → 0.900 (SimPO retry was 0.080), DPO-alone healthy 0.120, step-1 loss 0.6931 ≈ log 2. **(2)** Higher-pressure retry (beta 0.3, 200 steps, lr 1e-5) drove loss to 0.0073 and exec to 0.920, but clean-SQL stayed 0.000. **Definitive: composed rank-4 DPO cannot fix output-format hygiene at any tested pressure** (both keep a prose wrapper while execution only rises). Decision **retry-data**. Diagnosis correction: SFT targets are already 108/108 bare SELECT — the `Answer:` wrapper is the base Qwen3-0.6B prose prior, so the fix is generation-strength (stronger SFT or inference steering / output post-process), not a data rebuild. Execution is not the problem (0.860 → 0.920); only the wrapper is. Both runs assembled via `scripts/assemble_factory_run.py` (validate + publish-check pass); runs gitignored. |
| 2026-07-11 ground-up learning roadmap completed | Shipped: all 10 curriculum modules now have polished sessions (added `session-09-tensors`, `session-10-attention`, `session-11-evals-rewards` for the previously reference-only Modules 3/7/10), plus `docs/learn/coverage-map.md` mapping every shipped subsystem to a learning anchor. Guarded by `scripts/check_learning_roadmap.py` (`bash evals/learning-roadmap-smoke.sh`). |
| 2026-07-04 first full factory decision | Shipped: frozen `qwen06-sql-hygiene-dpo-v1` candidate trained (SimPO), evaluated composed against the reproduced frozen baseline, and decided **retry-training** (policy collapse: exec 0.860 → 0.080). Schema-valid run in `runs/2026-07-03-sql-hygiene-dpo-qwen06/`. Also landed: DoRA-aware `bake-lora`, routed-SQL perf harness, clean-SQL scorer. |
| 2026-07-03 canonical factory loop | Verified: `scripts/render_sql_factory_run.py` renders the canonical run folder (config, dataset, eval-baseline, eval-candidate, decision, artifact, train.log, report.md). Native CLI `posttrainllm factory-run render/validate` mirrors the same path. Run schema defined in `docs/factory/run-schema.md`. Actual training/eval remains operator-dependent (GPU + Xcode metal compiler required). |
| Original Phases 1-4 | Complete: Python reference, transformer, training loop, eval basics |
| Phase 5 | Complete: LoRA/adapter paths and PEFT bundle |
| Phase 6 | Complete: dataset manifests, HF integration, GitHub fetcher, synthesis |
| Phase 7 | Complete: browser systems, WASM SIMD, OPFS, gallery |
| Phase 8 | Complete: WebGPU training path and gated fast paths |
| Phase 9 | Complete: browser benchmark/eval and numerics-gate framework |
| Phase 10 | Complete: public browser readiness and docs consolidation |
| 2026-05-31 Mac runtime wave | Shipped: Swift/MLX CLI, serve/agent, Ollama/Continue-compatible surfaces |
| 2026-06-06 factory reframe | Active north star became Mac specialist factory |
| 2026-06-08 eval methodology gate | Shipped: baseline re-stamping, uncertainty, fake Pace/eval methods |
| 2026-06-19 planner lock | Shipped: stock Qwen3-4B-Instruct-2507 bf16 remains general Pace planner |
| 2026-06-20 factory/eval PRD wave | Shipped many scaffold/eval slices; most remaining work needs real training/evals |
| 2026-07-02 cleanup | Active navigation reset around factory loop; non-core lanes parked |

## Products

| Product / artifact | State |
|---|---|
| Factory CLI | Main product surface. It has commands for data prep, post-training, eval, traces, packaging, reporting, canonical factory-run render/validate/publish checks, and metadata-only lifecycle init/status/transition/list/reconcile. |
| Factory run artifacts | Target shape defined in `docs/factory/run-schema.md`; new lifecycle-v1 runs carry durable `run-status.json` plus repairable current/latest pointers, while legacy folders remain compatible. `runs/` is local-output and gitignored. |
| Specialist packages | Two public-weight packages are registered: routed file-ops distillation and the breadth-recovering ReST research specialist. |
| Public artifact registry | First-class release list lives in `docs/factory/public-artifacts.md`; website surface is `/artifacts`; every artifact carries blockers beside evidence. |
| Fine-tune report cards | Portable before/after proof per artifact: versioned JSON plus a self-contained static page at `/report-cards/<slug>.html`, compiled offline from recorded evidence with explicit measurement states. Contract in `docs/factory/report-card.md`. |
| Eval gates | Strong fixture/no-GPU layer exists. Live GPU/full-suite gates remain operator-dependent. |
| Browser playground | Live demo and proof of from-scratch/browser track. Its 331 public application, documentation, and report-card pages share generated sitemap, Markdown, and agent-catalog coverage, including five Mac-local specialist field guides. Explanatory controls now have visible keyboard focus and programmatic dialog relationships, while all data-source tabs remain discoverable on narrow screens. Product work remains parked behind the active factory loop. |
| PostTrainLLM app | GUI shell over the CLI. Now covers the factory-loop experiment commands: Factory tab runs pretrain/finetune/**DPO**/**distill**; new **Runs** tab runs **factory-run** (validate/publish-check), **eval-gate**, **eval-compare**, **eval-sql**, and **generate** — all via a shared `CLICommandRunner` shell-out. Data-prep, quantization/export, and most interpretability commands remain CLI-only by design (batch/one-off, not interactive). A local arm64 Release bundle can be assembled under `build/`; trusted direct distribution still requires the personal Developer ID and notarization credentials. |
| Pace outputs | Dev-time artifacts only: data, grammar/eval assets, adapter/model package metadata, reports. |

## Features (shipped)

Factory primitives:

- Native Mac app packaging: repeatable Release bundle assembly embeds the
  SwiftPM resources, CLI, MLX Metal library, and branded icon; supports
  versioned metadata and hardened-runtime Developer ID signing; and refuses
  notarization unless both a Developer ID signature and named Keychain profile
  are present.
- Everyday specialist evaluation and routing: a versioned three-task benchmark
  with generalist/adapted/system tracks, frontier qualification, privacy-safe
  receipts, deterministic reporting, and a validated development capability
  graph. The first measured selective cascade is retained as a
  `no-feasible-policy` result, not promoted as a win.
- Public specialist education: five canonical guides connect fine-tuning,
  MLX adaptation, evaluation, trajectory data, and routed-specialist decisions
  to the existing factory artifacts; each build emits matching HTML, Markdown,
  sitemap, and agent-catalog entries.
- Training and post-training: `train`, `finetune`, `sft`, `dpo`, `distill`,
  `es`, PEFT variants, LoRA/DoRA/QLoRA scaffolding, sequence packing,
  gradient checkpointing, NEFTune, z-loss, WSD, LLRD, spike recovery.
- Data: dataset registry/download, HF inspect/load, GitHub fetcher,
  Magpie/synthesis, tokenizer training, extractor data, trace conversion,
  correction-to-data tools, quality filtering, dedupe.
- Evals: `eval-gate`, `eval-compare`, BFCL, tau-bench, HumanEval, lm-eval,
  SQL, router, MILU/Indic, MTEB, review, ScaleDown V1, escalation evals.
- Runtime/serving: OpenAI-compatible `serve`, Ollama-compatible endpoints,
  agent loop, constrained JSON/FSM generation, trajectory recording, prompt
  cache, cloud escalation path.
- Packaging/runtime: export to MLX, safetensors/CoreML helpers, quantized
  inference paths, GGUF/AWQ/GPTQ readers, HQQ/GPTQ tools, merge/bake-lora.
- Reporting/readouts: eval result JSON, browser eval leaderboard, SAE
  timeline, benchmark scripts, specialist package model-card pattern.
- Complete published-model case studies: all six public PostTrainLLM Hugging
  Face model repositories have dedicated `/artifacts/<slug>` pages. Routed
  wins, rejected/regressed models, conversion-only releases, and missing-eval
  checkpoints use the same evidence/blocker/next-action structure; Hub request
  counters are not treated as adoption.
- Fine-Tune Report Card: `scripts/build_fine_tune_report_card.py` compiles a
  canonical run folder or a committed specialist package into a versioned
  `report-card.json` plus a deterministic self-contained public page;
  `scripts/check_fine_tune_report_card.py` is the publication gate;
  `scripts/publish_report_cards.py` regenerates the committed cohort and
  detects drift. Typed mirror in
  `native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift`. Contract in
  `docs/factory/report-card.md`, cohort review in
  `docs/factory/report-card-cohort.md`; covered by
  `evals/fine-tune-report-card-smoke.sh`,
  `tests/test_fine_tune_report_card.py`, and
  `tests/report_card_fixtures.py`.
- Foundry evidence receipts: `scripts/foundry_receipt.py` emits sanitized
  receipts (git, registry, run folders, nightly markers, CI) and
  `scripts/check_foundry_receipt.py` validates shape, provenance
  completeness, manual publication authority, and absence of private
  payloads. Contract in `docs/factory/foundry-evidence.md`; covered by
  `evals/foundry-receipt-smoke.sh` and `tests/test_foundry_receipt.py`.
- Autocorrect encoder-decoder adapter path (untrained):
  `scripts/autocorrect_adapter.py` implements hand-rolled LoRA over a T5-family
  base with a dependency-free stdlib layer (recipe validation, target
  resolution, example building, LR/checkpoint schedule, stop-rule state
  machine) and a lazily imported torch layer (injection, adapter IO, batch
  encoding, one step). `evals/autocorrect/adapter-recipe-v1.json` is the frozen
  recipe; `autocorrect_adapter.py verify-base` is the forward-only load-parity
  check against the real pinned checkpoint. Contract in
  `docs/factory/autocorrect-adapter-recipe.md`, concepts in
  `docs/learn/encoder-decoder-adapters.md`; covered by
  `evals/autocorrect-adapter-smoke.sh` and `tests/test_autocorrect_adapter.py`.
  Training is refused without an explicit operator-approval flag.
- Durable factory-run lifecycle: pure-IO
  `native-mac/Sources/TinyGPTIO/FactoryRunLifecycle.swift` owns lifecycle-v1
  status, legal/alternate transitions, expected-revision CAS, metadata locks,
  atomic snapshots, advisory discovery pointers, stale-active warnings,
  reconciliation, and honest legacy import. The metadata-only CLI, native
  render/folder validation, Python assembler, manual Mac app discovery, and
  Foundry receipt projection share that boundary. Contract and recovery guide
  in `docs/factory/run-lifecycle.md`; no automatic resume, publication,
  deployment, or replacement of `decision.json`.

Completed/parked learning tracks:

- Browser GPT training from scratch with WASM/WebGPU.
- WebGPU fast paths and numerics gates.
- ANE/CoreML experiments with documented constraints and negative results.
- VLM and Tier 5 research planning/scaffolds.
- Interpretability tools: SAE, ROME, MEMIT, tuned/logit lens, activation
  patching.

## Work queue

Open work is tracked only in [GitHub Issues](https://github.com/PostTrainLLM/posttrainllm/issues).
An open issue is a to-do, a linked pull request is in progress, and merge plus
issue closure makes the work done.
