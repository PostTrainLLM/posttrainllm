# Model compatibility check (`model-check`)

Paste a Hugging Face model URL, get a Mac-specific report: **can it run
with your current setup, could it run with changes, what to do next.**
The feature advises only — it never downloads weights, installs
software, converts, or executes models or repository code.

Spec: GitHub issue #156. Implementation: `native-mac/Sources/TinyGPTCheck/`
(service + report schema), `TinyGPT/ModelCheck.swift` (CLI),
`TinyGPTApp/ModelCheck{Controller,View}.swift` (app panel).

## Surfaces

```bash
posttrainllm model-check <hf-url-or-owner/repo>
posttrainllm model-check <hf-url-or-owner/repo> --json
# evaluate against a different Mac instead of this one:
posttrainllm model-check <url> --chip "Apple M4 Pro" --ram-gb 24 --disk-gb 200
```

The app's **Check** workspace renders the same `ModelCheckReport`; CLI
`--json` output and the UI are the same schema by construction — both
call `ModelCheckService.check`.

## Flow

```text
URL + environment
  → GET /api/models/<id>?blobs=true  (manifest, tags, gated, param stats)
  → fetch small files only           (config.json, ≤512 KB cap)
  → CompatibilityRules.assess        (pure functions — fixture-testable)
  → MacEnvironment.detect            (chip/RAM/disk/macOS + runtime probes)
  → ModelCheckReport                 (verdict + evidence + agent prompt)
```

## Verdict vocabulary

| Verdict | Meaning |
| --- | --- |
| `expected_to_work` | verified architecture, no config blockers, estimated footprint fits |
| `changes_required` | reachable, but needs a change (memory, conversion, install, download) |
| `unsupported_on_checked_path` | the posttrainllm MLX-Swift path can't run it — task mismatch (e.g. diffusers), MoE/multimodal/`*ForCausalLM` outside the verified set, or a config-level blocker from `HuggingFaceConfig.unsupportedReason()` |
| `unknown` | repo inaccessible, unrecognized format, or unverifiable — always with the missing evidence named and a copy-ready agent prompt |

Two honesty rules are load-bearing:

- **"Unsupported by the checked runtime" never becomes "impossible on
  this Mac."** Task mismatches say so and list other documented Mac
  paths (diffusers, mlx-lm, Ollama/llama.cpp, transformers, Core ML).
- **All memory figures are estimates** (`estimate: true`, "~" in text).
  Weights come from Hub safetensors stats or file sizes; resident memory
  assumes ~2× weight bytes for bf16/fp16 (fp32 up-convert in
  `HFModelLoader`), ~1.15× for MLX-packed checkpoints.

## Environment detection

`MacEnvironment.detect()` reads sysctl (chip, arch), `ProcessInfo`
(RAM, macOS), and volume capacity (free disk), then probes a bounded
runtime list with 6 s timeouts: `posttrainllm`, `ollama`, `llama-cli`,
`lms`, and one `python3` importlib.metadata sweep covering mlx, mlx-lm,
transformers, diffusers, torch, llama-cpp-python. No probe installs or
loads anything.

Manual overrides (`--chip/--ram-gb/--disk-gb/--macos`, or the app's
"check a different Mac" fields) set `environment.source: "manual"` so a
remote/web context can never pass its specs off as the user's machine.

## Boundaries

- Metadata only. The 401/403 and 404 cases produce `unknown` with the
  limitation named (HF returns 401 for nonexistent repos — the report
  says "requires authentication," not "doesn't exist").
- `HF_TOKEN` is used as a Bearer token for Hub reads and is never copied
  into reports or agent prompts.
- The verified-architecture list (`CompatibilityRules.verifiedArchitectures`)
  is intentionally narrow: `HFConfigConverter` always builds a
  RoPE+RMSNorm+SwiGLU model, so an unlisted `*ForCausalLM` would load
  into the *wrong* architecture silently — `unknown` is the correct
  answer there, with an agent-prompt handoff.

Tests: `native-mac/Tests/TinyGPTCheckTests/` — pure fixtures, no network.
