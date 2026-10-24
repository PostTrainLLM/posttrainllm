# okc: problem=muse_bf16_proj
"""Single-token BF16 GEMV plus the measured small-token router.

Other dense shapes follow the official SGLang dispatch
baseline at a55ab7d5ae1bba59ac351e55026fe7f7644ecc5f (Apache-2.0).
See docs/learn/openkernel.md for provenance and the required H200 checks.
"""

from typing import TypedDict

import torch
import torch.nn.functional as F
import triton
import triton.language as tl
from sglang.srt.layers.quantization.unquant import _bf16_gemm_dispatch_impl


class Weights(TypedDict):
    qkv_gate: torch.Tensor  # bfloat16 [2304, 8192]
    o: torch.Tensor  # bfloat16 [8192, 1024]
    pooler: torch.Tensor  # bfloat16 [4096, 8192]
    unpooler: torch.Tensor  # bfloat16 [8192, 4096]
    router: torch.Tensor  # float32 [256, 8192]


class Config(TypedDict):
    m: int
    n: int  # output width; the unpooler's is 1024 up to 8 tokens (this GPU's slice), else 8192
    k: int
    layer: str  # which weight: "qkv_gate", "o", "pooler", "unpooler" or "router"


class Inputs(TypedDict):
    x: torch.Tensor  # bfloat16 [m, k]
    config: Config


def prepare(weights: Weights) -> dict[str, torch.Tensor]:
    """Preserve every weight; the rules explicitly permit the router hi/lo pair."""
    state = {name: w.contiguous() for name, w in weights.items()}
    hi = weights["router"].to(torch.bfloat16)
    lo = (weights["router"] - hi.float()).to(torch.bfloat16)
    state["router_hi"] = hi.contiguous()
    state["router_lo"] = lo.contiguous()
    state["router_hi_t"] = hi.t().contiguous()
    state["router_lo_t"] = lo.t().contiguous()
    return state


@triton.jit(do_not_specialize=["M"])
def _router_partials(
    X,
    HI,
    LO,
    PARTIALS,
    M,
    N: tl.constexpr,
    K: tl.constexpr,
    STRIDE_M: tl.constexpr,
    STRIDE_K: tl.constexpr,
    BM: tl.constexpr,
    BN: tl.constexpr,
    BK: tl.constexpr,
    SPLIT_K: tl.constexpr,
):
    rows = tl.program_id(0) * BM + tl.arange(0, BM)
    cols = tl.program_id(1) * BN + tl.arange(0, BN)
    split = tl.program_id(2)
    ks = split * BK + tl.arange(0, BK)
    acc_hi = tl.zeros((BM, BN), dtype=tl.float32)
    acc_lo = tl.zeros((BM, BN), dtype=tl.float32)
    for block in range(tl.cdiv(K, BK * SPLIT_K)):
        offsets = ks + block * BK * SPLIT_K
        x = tl.load(
            X + rows[:, None] * STRIDE_M + offsets[None, :] * STRIDE_K,
            (rows[:, None] < M) & (offsets[None, :] < K),
            other=0,
        )
        weight_offsets = cols[None, :] * K + offsets[:, None]
        mask = (cols[None, :] < N) & (offsets[:, None] < K)
        hi = tl.load(HI + weight_offsets, mask, other=0)
        lo = tl.load(LO + weight_offsets, mask, other=0)
        acc_hi = tl.dot(x, hi, acc_hi)
        acc_lo = tl.dot(x, lo, acc_lo)
    tl.store(
        PARTIALS + split * M * N + rows[:, None] * N + cols[None, :],
        acc_hi + acc_lo,
        (rows[:, None] < M) & (cols[None, :] < N),
    )


@triton.jit
def _dense_gemv(
    X,
    W,
    OUT,
    N: tl.constexpr,
    K: tl.constexpr,
    X_STRIDE: tl.constexpr,
    W_ROW_STRIDE: tl.constexpr,
    W_K_STRIDE: tl.constexpr,
    BN: tl.constexpr,
    BK: tl.constexpr,
):
    rows = tl.program_id(0) * BN + tl.arange(0, BN)
    ks = tl.arange(0, BK)
    acc = tl.zeros((BN, BK), dtype=tl.float32)
    for block in range(tl.cdiv(K, BK)):
        offsets = block * BK + ks
        x = tl.load(X + offsets * X_STRIDE, offsets < K, other=0).to(tl.float32)
        w = tl.load(
            W + rows[:, None] * W_ROW_STRIDE + offsets[None, :] * W_K_STRIDE,
            (rows[:, None] < N) & (offsets[None, :] < K),
            other=0,
        ).to(tl.float32)
        acc += w * x[None, :]
    tl.store(OUT + rows, tl.sum(acc, axis=1), rows < N)


def kernel_fn(data: Inputs, state: dict[str, torch.Tensor]) -> torch.Tensor:
    """Compute every call from fresh inputs, branching only on public shapes."""
    x, config = data["x"], data["config"]
    layer, n = config["layer"], config["n"]
    if layer != "router":
        w = state[layer][:n]
        if x.shape[0] == 1 and x.dtype == w.dtype == torch.bfloat16:
            out = torch.empty((1, n), dtype=torch.bfloat16, device=x.device)
            _dense_gemv[(triton.cdiv(n, 4),)](
                x,
                w,
                out,
                n,
                x.shape[1],
                x.stride(1),
                w.stride(0),
                w.stride(1),
                BN=4,
                BK=1024,
                num_warps=4,
            )
            return out
        return _bf16_gemm_dispatch_impl(x, w, None)
    m, k = x.shape
    # Tiny batches favor the baseline FP32 GEMV; fusion wins at 8–16 tokens.
    if m <= 4:
        return F.linear(x.float(), state["router"][:n])
    if m > 16:
        acc = torch.mm(x, state["router_hi_t"], out_dtype=torch.float32)
        acc += torch.mm(x, state["router_lo_t"], out_dtype=torch.float32)
        return acc
    # Keep enough independent work for H200's 132 SMs at small M. Fixed
    # buckets apply to nearby shapes too; no autotuning during graph capture.
    splits = 16
    partials = torch.empty((splits, m, n), dtype=torch.float32, device=x.device)
    _router_partials[(triton.cdiv(m, 16), triton.cdiv(n, 32), splits)](
        x,
        state["router_hi"],
        state["router_lo"],
        partials,
        m,
        n,
        k,
        x.stride(0),
        x.stride(1),
        BM=16,
        BN=32,
        BK=128,
        SPLIT_K=splits,
        num_warps=4,
        num_stages=2,
    )
    # Each partial is fully written on this call. No atomics, persistent
    # activation state, cross-call reuse, or uninitialised accumulation.
    return partials.sum(dim=0)
