# Pace intent routing — sealed V1

This is the first official task in the Everyday Specialist Benchmark. The
shared 63-instance set is synthetic, maintainer-adjudicated, locally held, and
never committed. Every entry saw the exact same instance-set revision and ran
two passes. Normalized exact-match overlap against the v5 training and held-out
corpora was zero.

The frontier gate passed: Codex `gpt-5.5` scored 100% against the deterministic
exact-label scorer, above the frozen 99% qualification threshold.

## Result

| Entry | Track | Accuracy | Frontier capability retained | Unknown recall | Mean warm latency | Consistency |
|---|---|---:|---:|---:|---:|---:|
| Codex `gpt-5.5` | frontier anchor | 100.0% | 100.0% | 100.0% | 519 ms amortized batch | 100% |
| Qwen3-4B-Instruct-2507 4-bit | generalist | **93.7%** | **93.7%** | **77.8%** | 211 ms | 100% |
| Apple FoundationModels | generalist | 92.1% | 92.1% | 77.8% | 522 ms | 100% |
| Pace Intent Router v8 | adapted specialist | 57.1% | 57.1% | 55.6% | **3.8 ms** | 100% |

Codex latency is the amortized time for a structured batch and is not directly
comparable with the per-instance local timings. Among local entries, Qwen is
the capability winner. Pace v8 is about 55x faster than Qwen but misses too
many fresh real-user-like phrasings to replace it or Apple on this gate.

## Decision

Reject Pace v8 as the production intent-routing winner. Its previous 95.5%
result remains valid only for the source-matched synthetic holdout; it does not
generalize to this sealed distribution. Keep the model as the latency floor and
as evidence that the current synthetic generator overfit its template families.

For the next specialist iteration, generate new public-development examples
from the failure *themes*, never from the raw sealed prompts. Any trained
successor needs a newly generated sealed V2 set before an official claim; V1
must not become training data.

## Evidence

- [Frontier qualification](receipts/pace-intent-frontier-v1.json)
- [Qwen3 4B](receipts/qwen3-4b-intent-sealed-v1.json)
- [Apple FoundationModels](receipts/apple-foundation-models-intent-sealed-v1.json)
- [Pace Intent Router v8](receipts/pace-intent-router-v8-sealed-v1.json)

Receipts contain hashes, aggregate scores, leakage/custody evidence, and result
hashes only. Raw instances and model outputs remain in maintainer-held ignored
storage.
