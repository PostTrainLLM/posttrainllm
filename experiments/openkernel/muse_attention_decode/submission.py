# okc: problem=muse_attention_decode
"""Candidate fusion for Muse Spark Open's QK prep and FP8 cache writes.

The Triton kernel adapts SGLang's ``fused_qk_norm.py`` at
``a55ab7d5ae1bba59ac351e55026fe7f7644ecc5f`` (Apache-2.0). It keeps the
BF16 rounding around RoPE and FP8 conversion, and writes live cache row zero.
FA3 attention and SGLang's output norm/gate remain unchanged.
"""

from __future__ import annotations

from typing import TypedDict

import torch
import triton
import triton.language as tl
from sgl_kernel.flash_attn import flash_attn_with_kvcache
from sglang.kernels.ops.kvcache.kvcache import store_cache
from sglang.kernels.ops.muse_spark_v12.fused_qk_norm import FusedQKNorm
from sglang.kernels.ops.muse_spark_v12.norm_gate import rms_norm_gate


FP8 = torch.float8_e4m3fn
RMS_EPS = 1e-5
FP8_MAX = 448.0


class Config(TypedDict):
    batch: int
    q_len: int
    num_q_heads: int
    num_kv_heads: int
    head_dim: int
    page_size: int
    window: int
    rope_theta: float
    qk_scale_factor: float
    sm_scale: float
    kv_scale: float


class Inputs(TypedDict):
    qkv: torch.Tensor
    positions: torch.Tensor
    cache_loc: torch.Tensor
    cache_seqlens: torch.Tensor
    cu_seqlens_q: torch.Tensor
    scheduler_metadata: torch.Tensor | None
    k_cache: torch.Tensor
    v_cache: torch.Tensor
    k_scale: torch.Tensor
    v_scale: torch.Tensor
    page_table: torch.Tensor
    seq_lens: torch.Tensor
    config: Config


_NORMS = {}
_ROPE = {}
ROPE_POSITIONS = 1 << 21


def _qk_norm(hq, hkv, d):
    key = (hq, hkv, d)
    if key not in _NORMS:
        _NORMS[key] = FusedQKNorm(
            head_dim=d, num_q_heads=hq, num_kv_heads=hkv, eps=RMS_EPS
        )
    return _NORMS[key]


def _cos_sin(theta, d, device):
    """[2^21, d] float32 cos | sin, as SGLang's RotaryEmbedding builds it, cached per theta."""
    cache = _ROPE.get(theta)
    if cache is None:
        inv_freq = 1.0 / (
            theta ** (torch.arange(0, d, 2, dtype=torch.float, device=device) / d)
        )
        freqs = torch.einsum(
            "i,j -> ij",
            torch.arange(ROPE_POSITIONS, dtype=torch.float, device=device),
            inv_freq,
        )
        cache = _ROPE[theta] = torch.cat((freqs.cos(), freqs.sin()), dim=-1)
    return cache


@triton.jit
def _fused_qk_cache_kernel(
    QKV,
    Q_OUT,
    POS,
    COS_SIN,
    K_CACHE,
    V_CACHE,
    CACHE_LOC,
    stride_qkv,
    n_rows,
    NUM_Q_HEADS: tl.constexpr,
    NUM_KV_HEADS: tl.constexpr,
    D: tl.constexpr,
    BD: tl.constexpr,
    BLOCK_M: tl.constexpr,
    HAS_ROPE: tl.constexpr,
    EPS: tl.constexpr,
    FP8_LIMIT: tl.constexpr,
):
    rows = tl.program_id(0) * BLOCK_M + tl.arange(0, BLOCK_M)
    row_mask = rows < n_rows
    cols = tl.arange(0, BD)
    mask = row_mask[:, None] & (cols < D)[None, :]
    heads: tl.constexpr = NUM_Q_HEADS + 2 * NUM_KV_HEADS
    token = rows // heads
    head = rows % heads
    is_q = head < NUM_Q_HEADS
    is_k = (head >= NUM_Q_HEADS) & (head < NUM_Q_HEADS + NUM_KV_HEADS)
    is_v = head >= NUM_Q_HEADS + NUM_KV_HEADS

    src = token * stride_qkv + head * D
    raw = tl.load(QKV + src[:, None] + cols[None, :], mask=mask, other=0.0)
    x = raw.to(tl.float32)
    variance = tl.sum(tl.where(mask, x * x, 0.0), axis=1) / D
    rstd = tl.rsqrt(variance + EPS)
    x = x * rstd[:, None]

    if HAS_ROPE:
        # SGLang rounds normalized Q/K to BF16 before applying interleaved RoPE.
        x = x.to(QKV.dtype.element_ty).to(tl.float32)
        partner_cols = cols ^ 1
        partner = tl.load(
            QKV + src[:, None] + partner_cols[None, :], mask=mask, other=0.0
        ).to(tl.float32)
        partner = (partner * rstd[:, None]).to(QKV.dtype.element_ty).to(tl.float32)
        pos = tl.load(POS + token, mask=row_mask, other=0).to(tl.int64)
        freq = cols // 2
        cos = tl.load(COS_SIN + pos[:, None] * D + freq[None, :], mask=mask, other=1.0)
        sin = tl.load(
            COS_SIN + pos[:, None] * D + D // 2 + freq[None, :], mask=mask, other=0.0
        )
        is_even = (cols % 2 == 0)[None, :]
        x = tl.where(is_even, x * cos - partner * sin, partner * sin + x * cos)

    # The FP8 cache path rounds the rotated Q/K to BF16 before E4M3 conversion.
    x = x.to(QKV.dtype.element_ty).to(tl.float32)
    x = tl.where(is_v[:, None], raw.to(tl.float32), x)
    x = tl.minimum(tl.maximum(x, -FP8_LIMIT), FP8_LIMIT)

    loc = tl.load(CACHE_LOC + token, mask=row_mask, other=0).to(tl.int64)
    kv_head = tl.where(is_v, head - NUM_Q_HEADS - NUM_KV_HEADS, head - NUM_Q_HEADS)
    cache_dst = loc * (NUM_KV_HEADS * D) + kv_head * D
    tl.store(
        K_CACHE + cache_dst[:, None] + cols[None, :],
        x,
        mask=mask & is_k[:, None],
    )
    tl.store(
        V_CACHE + cache_dst[:, None] + cols[None, :],
        x,
        mask=mask & is_v[:, None],
    )

    q_dst = (token * NUM_Q_HEADS + head) * D
    tl.store(
        Q_OUT + q_dst[:, None] + cols[None, :],
        x,
        mask=mask & is_q[:, None],
    )


def _block_config(n_rows: int) -> tuple[int, int]:
    if n_rows < 1024:
        return 4, 4
    if n_rows < 8192:
        return 8, 4
    if n_rows < 65536:
        return 16, 4
    return 32, 4


def _fused_q_and_cache(data: Inputs, qkv: torch.Tensor) -> torch.Tensor:
    cfg = data["config"]
    batch, length = cfg["batch"], cfg["q_len"]
    hq, hkv, d = cfg["num_q_heads"], cfg["num_kv_heads"], cfg["head_dim"]
    tokens = batch * length
    n_rows = tokens * (hq + 2 * hkv)
    block_m, warps = _block_config(n_rows)
    q = torch.empty((tokens, hq * d), dtype=FP8, device=qkv.device)
    k_cache = data["k_cache"].view(-1, hkv * d)
    v_cache = data["v_cache"].view(-1, hkv * d)
    theta = cfg["rope_theta"]
    _fused_qk_cache_kernel[(triton.cdiv(n_rows, block_m),)](
        qkv,
        q,
        data["positions"],
        _cos_sin(theta, d, qkv.device) if theta else qkv,
        k_cache,
        v_cache,
        data["cache_loc"],
        qkv.stride(0),
        n_rows,
        hq,
        hkv,
        d,
        triton.next_power_of_2(d),
        block_m,
        HAS_ROPE=bool(theta),
        EPS=RMS_EPS,
        FP8_LIMIT=FP8_MAX,
        num_warps=warps,
    )
    return q.view(tokens, hq, d)


def _scaled_baseline_prep(
    data: Inputs, qkv: torch.Tensor, tokens: int, hq: int, hkv: int, d: int
) -> torch.Tensor:
    cfg = data["config"]
    if cfg["rope_theta"]:
        q, k = _qk_norm(hq, hkv, d)(
            qkv, data["positions"], _cos_sin(cfg["rope_theta"], d, qkv.device)
        )
    else:
        q, k = _qk_norm(hq, hkv, d)(qkv)

    v = qkv[:, (hq + hkv) * d : (hq + 2 * hkv) * d]
    k = k.reshape(tokens, hkv * d)
    k = k / data["k_scale"]
    v = v / data["v_scale"]
    store_cache(
        k.to(FP8).view(torch.uint8),
        v.to(FP8).view(torch.uint8),
        data["k_cache"].view(-1, hkv * d).view(torch.uint8),
        data["v_cache"].view(-1, hkv * d).view(torch.uint8),
        data["cache_loc"],
        reserved_skip_index=-1,
    )
    return q.view(tokens, hq, d).to(FP8)


def kernel_fn(data: Inputs) -> torch.Tensor:
    cfg = data["config"]
    batch, length = cfg["batch"], cfg["q_len"]
    hq, hkv, d = cfg["num_q_heads"], cfg["num_kv_heads"], cfg["head_dim"]
    tokens = batch * length
    qkv = data["qkv"].view(tokens, -1)

    if cfg["kv_scale"] == 1.0:
        q = _fused_q_and_cache(data, qkv)
        descale = {}
    else:
        q = _scaled_baseline_prep(data, qkv, tokens, hq, hkv, d)
        descale = dict(
            k_descale=data["k_scale"].reshape(1, 1).expand(batch, hkv),
            v_descale=data["v_scale"].reshape(1, 1).expand(batch, hkv),
        )

    window = cfg["window"]
    out = flash_attn_with_kvcache(
        q=q,
        k_cache=data["k_cache"],
        v_cache=data["v_cache"],
        page_table=data["page_table"],
        cache_seqlens=data["cache_seqlens"],
        cu_seqlens_q=data["cu_seqlens_q"],
        max_seqlen_q=length,
        softmax_scale=cfg["sm_scale"] * cfg["qk_scale_factor"],
        causal=True,
        window_size=(window - 1, 0) if window else (-1, -1),
        scheduler_metadata=data["scheduler_metadata"],
        **descale,
    )
    if isinstance(out, tuple):
        out = out[0]
    gate = qkv[:, (hq + 2 * hkv) * d :]
    output = rms_norm_gate(
        out.reshape(tokens, hq * d).to(torch.bfloat16),
        gate,
        None,
        head_dim=d,
        eps=RMS_EPS,
        has_norm=True,
    )
    return output.view(batch, length, hq * d)
