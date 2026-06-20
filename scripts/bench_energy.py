#!/usr/bin/env python3
"""B9 — energy per token (J/token).

Samples combined CPU+GPU+ANE power via `powermetrics` while a decode workload
runs against `tinygpt serve`, integrates power over the decode window to get
joules, and divides by tokens generated → J/token. Emits a leaderboard-ready
row (and can append to the SLM leaderboard JSONL).

Needs `sudo` for powermetrics (see scripts/setup_powermetrics_sudoers.sh for a
passwordless drop-in). The energy math is covered by `--self-test` (no sudo):

    python3 scripts/bench_energy.py --self-test

Real run:

    tinygpt serve --model <m> &
    sudo python3 scripts/bench_energy.py --model <m> --label qwen3-4b \\
        --jsonl docs/research/data/energy.jsonl
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def joules(samples):
    """Trapezoidal integral of power(W) over time(s) → joules.
    samples: time-ordered list of {"t": sec, "power_w": W}. Pure fn."""
    if len(samples) < 2:
        return 0.0
    e = 0.0
    for a, b in zip(samples, samples[1:]):
        dt = b["t"] - a["t"]
        e += 0.5 * (a["power_w"] + b["power_w"]) * dt
    return e


def energy_per_token(samples, n_tokens):
    """J/token = ∫power dt / tokens. Returns None if no tokens."""
    if not n_tokens:
        return None
    return joules(samples) / n_tokens


def sample_power_mw():
    """One powermetrics read → combined package power in watts (or None)."""
    try:
        out = subprocess.run(
            ["powermetrics", "-n", "1", "-i", "200", "--samplers", "cpu_power,gpu_power"],
            capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    mw = 0.0
    found = False
    for line in out.splitlines():
        low = line.lower()
        if "combined power" in low or "package power" in low or "power:" in low:
            try:
                val = float(line.split(":")[1].strip().split()[0])
                mw += val; found = True
            except Exception:
                pass
    return mw / 1000.0 if found else None


def run(args):
    samples, stop = [], threading.Event()
    t0 = time.time()

    def poll():
        while not stop.is_set():
            w = sample_power_mw()
            if w is not None:
                samples.append({"t": time.time() - t0, "power_w": w})
            time.sleep(0.2)

    th = threading.Thread(target=poll, daemon=True); th.start()
    # decode workload via bench_decode.py
    out = subprocess.run(
        [sys.executable, str(HERE / "bench_decode.py"),
         "--url", args.url, "--model", args.model,
         "--n", str(args.n), "--warm", "1", "--max-tokens", str(args.max_tokens)],
        capture_output=True, text=True, timeout=600).stdout
    stop.set(); th.join(timeout=1)
    rec = json.loads(out)
    # bench_decode.py emits inter-token-latency count (itl_ms.n = tokens − n_runs)
    # across n_runs; total generated tokens = itl_ms.n + n_runs.
    n_tokens = rec.get("itl_ms", {}).get("n", 0) + rec.get("n_runs", 0)
    jpt = energy_per_token(samples, n_tokens)
    row = {"label": args.label or args.model, "metric": "j_per_token",
           "j_per_token": jpt, "n_tokens": n_tokens,
           "joules": joules(samples), "power_samples": len(samples)}
    print(json.dumps(row, indent=2))
    if not samples:
        print("warning: no power samples — run under sudo (see setup_powermetrics_sudoers.sh)",
              file=sys.stderr)
    if args.jsonl:
        p = Path(args.jsonl); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(row) + "\n")
    return 0


def self_test():
    # constant 10 W for 2 s ⇒ 20 J; over 100 tokens ⇒ 0.2 J/tok
    s = [{"t": 0.0, "power_w": 10.0}, {"t": 1.0, "power_w": 10.0}, {"t": 2.0, "power_w": 10.0}]
    assert abs(joules(s) - 20.0) < 1e-9, joules(s)
    assert abs(energy_per_token(s, 100) - 0.2) < 1e-9
    # ramp 0→10 W over 1 s ⇒ trapezoid 5 J
    r = [{"t": 0.0, "power_w": 0.0}, {"t": 1.0, "power_w": 10.0}]
    assert abs(joules(r) - 5.0) < 1e-9, joules(r)
    assert energy_per_token(s, 0) is None
    print("SELF-TEST OK: joules() + energy_per_token()")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--model")
    ap.add_argument("--label", default=None)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--jsonl", default=None, help="append the J/token row here")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.model:
        ap.error("--model required for a real run (or pass --self-test)")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
