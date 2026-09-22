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
  → tensor names                     (model.safetensors.index.json, or a
                                      Range-read of a shard's JSON header —
                                      a 200 full-file response is refused;
                                      weight bytes are never fetched)
  → CompatibilityRules.assess        (pure functions — fixture-testable)
  → MacEnvironment.detect            (chip/RAM/disk/macOS + runtime probes)
  → ModelCheckReport                 (verdict + evidence + agent prompt)
```

**Tensor-name layout** is the structural check that upgrades name-guessing
into evidence: `HFModelLoader` consumes the standard HF convention
(`model.layers.N.self_attn.{q,k,v,o}_proj`, `mlp.{gate,up,down}_proj`,
`model.embed_tokens`, `model.norm`, `lm_head`), so the checker counts how
many tensors match. An unlisted architecture whose tensors match (e.g.
OLMo-2: 73% match) becomes `changes_required` with `hf-load` named as the
verification step — `unknown` is reserved for genuinely unreadable or
nonstandard layouts (GPT-2's `h.N.attn.c_attn`: 0% match). Legacy config
schemas (`n_head`/`n_embd`/`n_layer`, missing `n_inner` → 4×hidden) are
normalized before the strict parse.

**Gated repos are assessable.** `GET /api/models/<id>` embeds the parsed
config, `transformersInfo`, `cardData`, the file manifest, and
safetensors param stats even without auth — only per-file reads (config,
headers) 401. The checker uses the API-embedded config as a fallback, so
a gated Llama/Gemma still gets a real verdict (`changes_required`, with
"accept license + HF_TOKEN" as the named access step) rather than
`unknown`. Truly private repos (404/401 on the API itself) remain
`unknown`.

Other detection paths: **PEFT/LoRA adapters** (`adapter_model.*`,
`adapter_config.json` → base model) get a "compatibility is the base
model's" verdict with a `model-check` handoff to the base; **remote-code
repos** (`auto_map`, `transformersInfo.custom_class`) are a named
`unsupported_on_checked_path` — repo-shipped modeling code is never
executed by policy; **GGUF headers** are Range-read for
`general.architecture` + `file_type`, so quant support is verified
against what `GGUFReader` actually dequantizes (F32/F16/Q4_0/Q8_0/BF16 —
K-quants report honestly as needing llama.cpp/Ollama).

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
  `HFModelLoader`), ~1.15× for MLX-packed checkpoints, plus a KV-cache
  allowance at an 8k-token reference context.

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

## `model-run` — close the loop

`posttrainllm model-run <url>` runs the check, picks the best installed
runtime, downloads, executes a bounded sample, and reports measured
success. Runner order: GGUF → Ollama (`ollama run hf.co/<id>`, with
`ollama serve` auto-start and a local-GGUF + `ollama create` fallback
when hf.co pulls hit Xet-CDN redirect blocks); compatible safetensors →
native `hf-load` (the real verification step); other safetensors →
`python3 -m mlx_lm`. Failures cascade to the next runner with the real
error surfaced. `--chat` drops into an interactive session; `--runtime`
forces a specific one; gated repos require HF_TOKEN first.

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
