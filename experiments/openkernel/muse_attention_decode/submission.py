# okc: problem=muse_attention_decode
"""Paged split-K attention with the existing fused QK/cache prep.

The Triton kernel adapts SGLang's ``fused_qk_norm.py`` at
``a55ab7d5ae1bba59ac351e55026fe7f7644ecc5f`` (Apache-2.0). It keeps the
BF16 rounding around RoPE and FP8 conversion, and writes live cache row zero.
Unsupported shapes/scales retain FA3; SGLang's output norm/gate is unchanged.
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


@triton.jit
def _paged_attention_partials(
    Q,
    K,
    V,
    TABLE,
    LENGTHS,
    CU_Q,
    K_SCALE,
    PARTIAL_OUT,
    PARTIAL_STATS,
    HQ: tl.constexpr,
    HKV: tl.constexpr,
    GROUP: tl.constexpr,
    ROWS: tl.constexpr,
    SPLITS: tl.constexpr,
    WINDOW: tl.constexpr,
    SM_SCALE: tl.constexpr,
    TABLE_COLS: tl.constexpr,
    CACHE_PAGES: tl.constexpr,
    QT: tl.constexpr,
    QH: tl.constexpr,
    QD: tl.constexpr,
    KP: tl.constexpr,
    KH: tl.constexpr,
    KD: tl.constexpr,
    VP: tl.constexpr,
    VH: tl.constexpr,
    VD: tl.constexpr,
    TB: tl.constexpr,
    TP: tl.constexpr,
    LS: tl.constexpr,
    CS: tl.constexpr,
    BM: tl.constexpr,
    BN: tl.constexpr,
):
    batch = tl.program_id(0)
    head = tl.program_id(1)
    split = tl.program_id(2)
    rows = tl.arange(0, BM)
    dims = tl.arange(0, 64)
    columns = tl.arange(0, BN)
    query_start = tl.load(CU_Q + batch * CS)
    query_length = tl.load(CU_Q + (batch + 1) * CS) - query_start
    seqlen = tl.load(LENGTHS + batch * LS)
    query_token = rows // GROUP
    query_head = head * GROUP + rows % GROUP
    valid_query = (rows < ROWS) & (query_token < query_length)
    query_pos = seqlen - query_length + query_token
    q = tl.load(
        Q
        + (query_start + query_token)[:, None] * QT
        + query_head[:, None] * QH
        + dims[None, :] * QD,
        valid_query[:, None],
        other=0.0,
    ).to(tl.bfloat16)
    scale = SM_SCALE * tl.load(K_SCALE)

    first_key = 0
    if WINDOW > 0:
        first_key = tl.maximum(0, seqlen - query_length - WINDOW + 1)
    block_count = tl.cdiv(tl.maximum(0, seqlen - first_key), BN)
    blocks_per_split = tl.cdiv(block_count, SPLITS)
    start = first_key + split * blocks_per_split * BN
    stop = tl.minimum(seqlen, start + blocks_per_split * BN)

    row_max = tl.full((BM,), -float("inf"), tl.float32)
    row_sum = tl.zeros((BM,), tl.float32)
    acc = tl.zeros((BM, 64), tl.float32)
    for block in range(start, stop, BN):
        key_pos = block + columns
        valid_key = (key_pos < seqlen) & (key_pos < TABLE_COLS)
        page = tl.load(TABLE + batch * TB + key_pos * TP, valid_key, other=-1).to(
            tl.int64
        )
        valid_key = valid_key & (page >= 0) & (page < CACHE_PAGES)
        safe_page = tl.maximum(page, 0)
        k = tl.load(
            K + safe_page[None, :] * KP + head * KH + dims[:, None] * KD,
            valid_key[None, :],
            other=0.0,
        ).to(tl.bfloat16)
        v = tl.load(
            V + safe_page[:, None] * VP + head * VH + dims[None, :] * VD,
            valid_key[:, None],
            other=0.0,
        ).to(tl.bfloat16)
        # FP8 Q/K/V convert losslessly to BF16. Both dots accumulate in FP32.
        scores = tl.dot(q, k) * scale
        visible = valid_query[:, None] & valid_key[None, :]
        visible = visible & (key_pos[None, :] <= query_pos[:, None])
        if WINDOW > 0:
            visible = visible & (key_pos[None, :] >= query_pos[:, None] - WINDOW + 1)
        scores = tl.where(visible, scores, -float("inf"))
        new_max = tl.maximum(row_max, tl.max(scores, axis=1))
        # An entirely masked row/split has max=-inf and sum=0. Subtract a
        # finite value there, so neither alpha nor P evaluates -inf - -inf.
        safe_max = tl.where(new_max == -float("inf"), 0.0, new_max)
        alpha = tl.exp(row_max - safe_max)
        p = tl.exp(scores - safe_max[:, None])
        row_sum = row_sum * alpha + tl.sum(p, axis=1)
        acc = acc * alpha[:, None]
        # FA3's FP8 path converts its softmax probabilities to FP8 before PV.
        # BF16 probabilities are finer; max/sum and PV accumulation stay FP32.
        acc = tl.dot(p.to(tl.bfloat16), v, acc)
        row_max = new_max

    partial_row = ((batch * HKV + head) * SPLITS + split) * ROWS + rows
    tl.store(
        PARTIAL_OUT + partial_row[:, None] * 64 + dims[None, :],
        acc,
        (rows < ROWS)[:, None],
    )
    tl.store(PARTIAL_STATS + partial_row * 2, row_max, rows < ROWS)
    tl.store(PARTIAL_STATS + partial_row * 2 + 1, row_sum, rows < ROWS)


@triton.jit
def _merge_attention_partials(
    PARTIAL_OUT,
    PARTIAL_STATS,
    CU_Q,
    V_SCALE,
    OUT,
    HQ: tl.constexpr,
    HKV: tl.constexpr,
    GROUP: tl.constexpr,
    ROWS: tl.constexpr,
    SPLITS: tl.constexpr,
    CS: tl.constexpr,
):
    batch = tl.program_id(0)
    head = tl.program_id(1)
    row = tl.program_id(2)
    splits = tl.arange(0, SPLITS)
    dims = tl.arange(0, 64)
    partial_row = ((batch * HKV + head) * SPLITS + splits) * ROWS + row
    maxima = tl.load(PARTIAL_STATS + partial_row * 2)
    sums = tl.load(PARTIAL_STATS + partial_row * 2 + 1)
    maximum = tl.max(maxima, axis=0)
    safe_maximum = tl.where(maximum == -float("inf"), 0.0, maximum)
    weights = tl.exp(maxima - safe_maximum)
    denominator = tl.sum(sums * weights, axis=0)
    partials = tl.load(PARTIAL_OUT + partial_row[:, None] * 64 + dims[None, :])
    numerator = tl.sum(partials * weights[:, None], axis=0)
    out = numerator / tl.where(denominator > 0, denominator, 1.0)
    out *= tl.load(V_SCALE)
    query_start = tl.load(CU_Q + batch * CS)
    query_end = tl.load(CU_Q + (batch + 1) * CS)
    token = query_start + row // GROUP
    query_head = head * GROUP + row % GROUP
    tl.store(OUT + (token * HQ + query_head) * 64 + dims, out, token < query_end)


def _splitk_attention(data: Inputs, q: torch.Tensor) -> torch.Tensor | None:
    """Bounded page-one/GQA8 path; dispatch only on public shape/config metadata."""
    cfg = data["config"]
    batch, length = cfg["batch"], cfg["q_len"]
    hq, hkv, d = cfg["num_q_heads"], cfg["num_kv_heads"], cfg["head_dim"]
    k, v = data["k_cache"], data["v_cache"]
    table, lengths, cu_q = (
        data["page_table"],
        data["cache_seqlens"],
        data["cu_seqlens_q"],
    )
    sm_scale = cfg["sm_scale"] * cfg["qk_scale_factor"]
    if not (
        batch > 0
        and hkv > 0
        and hq == hkv * 8
        and length in (1, 8)
        and (length == 1 or (cfg["window"] > 0 and batch * length <= 8))
        and d == 64
        and cfg["page_size"] == 1
        and cfg["kv_scale"] == 1.0
        and cfg["window"] >= 0
        and 0 < sm_scale < float("inf")
        and q.dtype == k.dtype == v.dtype == FP8
        and q.shape == (batch * length, hq, d)
        and k.ndim == v.ndim == 4
        and k.shape == v.shape
        and k.shape[1:] == (1, hkv, d)
        and table.ndim == 2
        and table.shape[0] == batch
        and table.shape[1] > 0
        and lengths.shape == (batch,)
        and cu_q.shape == (batch + 1,)
        and data["k_scale"].numel() == data["v_scale"].numel() == 1
    ):
        return None

    # Keep FA3 for long-context verification and larger verification batches;
    # those regimes regressed in the broad split-K H200 check.
    group = hq // hkv
    rows = length * group
    block_n = 64 if cfg["window"] else 128
    capacity = table.shape[1]
    if cfg["window"]:
        capacity = min(capacity, cfg["window"] + length - 1)
    splits = min(
        128,
        triton.next_power_of_2(triton.cdiv(512, batch * hkv)),
        triton.next_power_of_2(triton.cdiv(capacity, block_n)),
    )
    # Scored shapes need at most 8.25 MiB. Bound nearby shapes as well rather
    # than constructing unbounded per-context scratch or a dense score matrix.
    if batch * hkv * splits * rows * (d + 2) * 4 > 32 * 1024 * 1024:
        return None
    partials = torch.empty(
        (batch, hkv, splits, rows, d), dtype=torch.float32, device=q.device
    )
    stats = torch.empty(
        (batch, hkv, splits, rows, 2), dtype=torch.float32, device=q.device
    )
    out = torch.empty((batch * length, hq, d), dtype=torch.bfloat16, device=q.device)
    _paged_attention_partials[(batch, hkv, splits)](
        q,
        k,
        v,
        table,
        lengths,
        cu_q,
        data["k_scale"],
        partials,
        stats,
        HQ=hq,
        HKV=hkv,
        GROUP=group,
        ROWS=rows,
        SPLITS=splits,
        WINDOW=cfg["window"],
        SM_SCALE=sm_scale,
        TABLE_COLS=table.shape[1],
        CACHE_PAGES=k.shape[0],
        QT=q.stride(0),
        QH=q.stride(1),
        QD=q.stride(2),
        KP=k.stride(0),
        KH=k.stride(2),
        KD=k.stride(3),
        VP=v.stride(0),
        VH=v.stride(2),
        VD=v.stride(3),
        TB=table.stride(0),
        TP=table.stride(1),
        LS=lengths.stride(0),
        CS=cu_q.stride(0),
        BM=max(16, triton.next_power_of_2(rows)),
        BN=block_n,
        num_warps=4,
        num_stages=2,
    )
    _merge_attention_partials[(batch, hkv, rows)](
        partials,
        stats,
        cu_q,
        data["v_scale"],
        out,
        HQ=hq,
        HKV=hkv,
        GROUP=group,
        ROWS=rows,
        SPLITS=splits,
        CS=cu_q.stride(0),
        num_warps=4,
    )
    return out


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
    out = _splitk_attention(data, q)
    if out is None:
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
