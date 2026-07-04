# LoRA Geometry Diagnostics

LoRA geometry is a learning artifact for the factory. It answers:

- Is the skill actually learned by a low-rank effective update?
- Which modules move most?
- Are DoRA/LoRA updates concentrated enough to try lower rank?
- Can we compare failed and successful adapters without rerunning training?

TinyGPT adapters use the TGLA format, so we can inspect effective updates
without loading the base model:

```bash
python3 scripts/lora_geometry.py runs/<id>/<adapter>.lora --out runs/<id>/lora-geometry.json
```

The script reports per-entry:

- configured rank
- realized matrix rank
- stable rank
- Frobenius norm
- spectral norm
- whether DoRA magnitude is present

## How To Use It

For every meaningful adapter family, compare:

1. baseline SFT adapter
2. failed DPO/RL adapter
3. retry adapter
4. optionally a rank-truncated or middle-layer-only variant

If a failed adapter has large movement in the wrong modules or a successful
adapter has very low stable rank, the next candidate should test lower rank or
module targeting before increasing model size.
