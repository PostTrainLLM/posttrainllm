#!/usr/bin/env python3
"""B17 — verify a `posttrainllm sae-to-saelens` export actually loads in SAELens.

Usage: python3 scripts/sae_saelens_roundtrip.py <saelens-dir> [d_in] [d_sae]

Loads the exported directory with the real `sae_lens.SAE`, checks the config
dims, and runs an encode→decode forward so the weights are exercised. Exits
non-zero on any failure. Requires `pip install sae_lens`.
"""
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: sae_saelens_roundtrip.py <saelens-dir> [d_in] [d_sae]", file=sys.stderr)
        return 2
    path = sys.argv[1]
    exp_d_in = int(sys.argv[2]) if len(sys.argv) > 2 else None
    exp_d_sae = int(sys.argv[3]) if len(sys.argv) > 3 else None

    import torch
    from sae_lens import SAE

    sae = SAE.load_from_disk(path)
    cfg = sae.cfg
    d_in = getattr(cfg, "d_in", None)
    d_sae = getattr(cfg, "d_sae", None)
    print(f"loaded SAE: d_in={d_in} d_sae={d_sae} arch={getattr(cfg, 'architecture', '?')}")

    if exp_d_in is not None:
        assert d_in == exp_d_in, f"d_in {d_in} != expected {exp_d_in}"
    if exp_d_sae is not None:
        assert d_sae == exp_d_sae, f"d_sae {d_sae} != expected {exp_d_sae}"

    # exercise the weights: encode → decode round-trips the residual dim
    x = torch.randn(4, d_in, dtype=next(sae.parameters()).dtype)
    feats = sae.encode(x)
    assert feats.shape == (4, d_sae), f"encode shape {tuple(feats.shape)} != (4,{d_sae})"
    recon = sae.decode(feats)
    assert recon.shape == x.shape, f"decode shape {tuple(recon.shape)} != {tuple(x.shape)}"

    print("ROUND-TRIP OK: posttrainllm SAE loads + runs in SAELens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
