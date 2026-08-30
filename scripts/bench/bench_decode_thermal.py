#!/usr/bin/env python3
"""C5 — sustained decode + thermal bench.

Wraps scripts/bench/bench_decode.py in a sustained loop (default 30 min) against a
running `posttrainllm serve`, sampling decode tok/s over time plus (optionally,
sudo) `powermetrics` thermal pressure / CPU-die temperature. Writes a
time-series JSONL and reports throughput degradation (first-decile vs
last-decile median tok/s) — the number that says whether the Mac throttles
under a long generation.

Full runs need: a running server (--url), a model, ~30 min, and `sudo` for
powermetrics. The pure aggregation logic is covered by `--self-test`
(no server/sudo needed) so the wrapper can be CI-checked:

    python3 scripts/bench/bench_decode_thermal.py --self-test

Real run:

    posttrainllm serve --model <m> &                 # OpenAI-compatible endpoint
    sudo python3 scripts/bench/bench_decode_thermal.py \\
        --model <m> --minutes 30 --out docs/research/data/decode-thermal-m5.jsonl
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def degradation(series):
    """Given a list of {"t":sec,"tok_s":float} samples (time-ordered),
    return (first_decile_median, last_decile_median, pct_drop).

    pct_drop > 0 means throughput fell over the run (thermal throttling).
    Pure function — the unit under self-test."""
    toks = [s["tok_s"] for s in series if s.get("tok_s")]
    if len(toks) < 2:
        return (None, None, None)
    k = max(1, len(toks) // 10)
    first = statistics.median(toks[:k])
    last = statistics.median(toks[-k:])
    pct = 100.0 * (first - last) / first if first else 0.0
    return (first, last, pct)


def sample_powermetrics():
    """Best-effort one-shot powermetrics read → dict (needs sudo). Returns
    {} when unavailable so the bench still records tok/s without thermal."""
    try:
        out = subprocess.run(
            ["powermetrics", "-n", "1", "-i", "200",
             "--samplers", "smc", "--hide-cpu-duty-cycle"],
            capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return {}
    d = {}
    for line in out.splitlines():
        low = line.lower()
        if "cpu die temperature" in low:
            try: d["cpu_die_c"] = float(line.split(":")[1].strip().split()[0])
            except Exception: pass
        if "thermal pressure" in low:
            d["thermal_pressure"] = line.split(":")[1].strip()
    return d


def one_decode(url, model, max_tokens):
    """Run bench_decode.py once, return steady-state tok/s (or None)."""
    try:
        out = subprocess.run(
            [sys.executable, str(HERE / "bench_decode.py"),
             "--url", url, "--model", model, "--n", "1",
             "--warm", "0", "--max-tokens", str(max_tokens)],
            capture_output=True, text=True, timeout=180).stdout
        rec = json.loads(out)
        # bench_decode.py emits decode_tok_s.{median,...} (steady-state tok/s)
        return rec.get("decode_tok_s", {}).get("median")
    except Exception as e:
        print(f"  decode failed: {e}", file=sys.stderr)
        return None


def run(args):
    out = Path(args.out) if args.out else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        fh = out.open("w")
    else:
        fh = None
    series = []
    t0 = time.time()
    deadline = t0 + args.minutes * 60
    print(f"sustained decode bench: {args.minutes} min, model={args.model}")
    while time.time() < deadline:
        toks = one_decode(args.url, args.model, args.max_tokens)
        rec = {"t": round(time.time() - t0, 1), "tok_s": toks}
        rec.update(sample_powermetrics())
        series.append(rec)
        if fh:
            fh.write(json.dumps(rec) + "\n"); fh.flush()
        print(f"  t={rec['t']:>6}s  tok/s={toks}  {rec.get('cpu_die_c','')}")
    if fh:
        fh.close()
    first, last, pct = degradation(series)
    print(f"\nfirst-decile {first} → last-decile {last} tok/s  (drop {pct:.1f}%)" if pct is not None
          else "\nnot enough samples for a degradation estimate")
    return 0


def self_test():
    # steady → no drop
    flat = [{"t": i, "tok_s": 20.0} for i in range(20)]
    _, _, pct = degradation(flat)
    assert abs(pct) < 1e-9, pct
    # throttling: 25 → 20 tok/s ⇒ 20% drop
    ramp = [{"t": i, "tok_s": 25.0} for i in range(10)] + [{"t": i, "tok_s": 20.0} for i in range(10)]
    f, l, pct = degradation(ramp)
    assert f == 25.0 and l == 20.0 and abs(pct - 20.0) < 1e-6, (f, l, pct)
    # too few samples
    assert degradation([{"t": 0, "tok_s": 1.0}]) == (None, None, None)
    print("SELF-TEST OK: degradation()")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--model")
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--out", default=None, help="time-series JSONL output")
    ap.add_argument("--self-test", action="store_true",
                    help="validate the pure aggregation logic and exit")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.model:
        ap.error("--model is required for a real run (or pass --self-test)")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
