# Model run (`model-run`)

Paste a Hugging Face model URL, get a **measured** answer: the best
installed runtime downloads the model, generates a bounded sample, and
prints the command that keeps the session going. The executor half of
[`model-check`](model-check.md) — the checker's verdict is a prediction;
`model-run` turns it into evidence with a real load.

Spec: GitHub issue #157. Implementation: `native-mac/Sources/TinyGPTRun/`
(runner planning + bounded subprocesses), `TinyGPT/ModelRun.swift` (CLI
shim).

```bash
posttrainllm model-run Qwen/Qwen3-0.6B
posttrainllm model-run Qwen/Qwen3-0.6B-GGUF
posttrainllm model-run <url> --chat --prompt "hi" --max-tokens 64
posttrainllm model-run <url> --runtime native|mlx-lm|ollama|lms|llama-cli
```

## Flow

```text
model-check report (real check, full machinery)
  → gated?            stop unless HF_TOKEN is set, name the fix
  → RunnerPlanner     ordered candidates from formats + verdict +
                      which runtimes probe as installed
  → execute each      bounded subprocess: timeout, captured output,
                      killed on expiry; failure falls through to the
                      next candidate — a runtime that probes as
                      installed can still be broken
  → verify + handoff  "ran on <runtime> — verified, not predicted"
                      + the exact command to keep chatting
```

## Runner table

| Repo shape                        | Order                                       |
| --------------------------------- | ------------------------------------------- |
| safetensors + checked path OK     | native `hf-load` → mlx-lm                   |
| safetensors + checked path failed | mlx-lm only (native could load *wrong*)     |
| GGUF                              | ollama → lms → llama-cli                    |
| gated, no HF_TOKEN                | none — names the license + token step       |

GGUF is never routed to native: `gguf-load` validates structure only —
it cannot generate. Unknown/unsupported architectures stay off native
for the same reason: a wrong-architecture load can fail *silently*.

## Cleanup contract

model-run never leaves a process running: a spawned `ollama serve` is
terminated after the run, an `lms`-loaded model is unloaded, every
subprocess has a hard timeout. Models stay downloaded — to the
posttrainllm cache (`~/.cache/posttrainllm/models/<id>`), the HF cache
(mlx-lm, llama-cli), or LM Studio's store (`lms get`).

## Environment realities observed (2026-09-22, this Mac)

The fallthrough exists because installed ≠ working — all three of these
were hit live while building the feature:

- `ollama run hf.co/…` → `blocked redirect to a different host` — ollama
  0.34.2 refuses the Xet-bridge CDN redirect most HF repos now issue.
- `lms load` → `No LM Runtime found for model format 'gguf'` — the LM
  Studio install lacked a GGUF runtime plugin.
- `python3 -m mlx_lm` → `ModuleNotFoundError: huggingface_hub` — the
  dist was present but broken; metadata probing can't see that.

llama-cli's own `-hf` downloader completed the same pull ollama
refused, so GGUF repos still reach a verified run on this machine.
