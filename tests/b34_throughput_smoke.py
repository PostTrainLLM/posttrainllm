#!/usr/bin/env python3
"""B34 no-model throughput smoke.

This proves the eval-driver side can exercise an OpenAI-compatible endpoint
with bounded concurrency and produce a throughput report. It deliberately uses
a local threaded mock instead of a model server, so it does not satisfy the real
B34 acceptance gate; the real gate still needs tinygpt vs mlx-server/oMLX on a
fixed BFCL/tau suite.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import http.server
import json
import socket
import threading
import time
import urllib.error
import urllib.request


class Handler(http.server.BaseHTTPRequestHandler):
    delay = 0.08

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        if length:
            self.rfile.read(length)
        time.sleep(self.delay)
        body = json.dumps({
            "id": "mock",
            "object": "text_completion",
            "choices": [{"text": "ok"}],
        }).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _fmt: str, *_args: object) -> None:
        return


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def request(url: str, idx: int) -> str:
    payload = json.dumps({
        "model": "tinygpt-b34-mock",
        "prompt": f"fixture {idx}",
        "max_tokens": 1,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return str(data["choices"][0]["text"])
        except (ConnectionError, urllib.error.URLError) as error:
            last_error = error
            time.sleep(0.02)
    raise RuntimeError(f"request {idx} failed after retries: {last_error}")


def run_sequential(url: str, n: int) -> float:
    start = time.perf_counter()
    for idx in range(n):
        request(url, idx)
    return time.perf_counter() - start


def run_concurrent(url: str, n: int, concurrency: int) -> float:
    start = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(lambda idx: request(url, idx), range(n)))
    assert results == ["ok"] * n
    return time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=24)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--delay-ms", type=float, default=80)
    parser.add_argument("--min-speedup", type=float, default=3.0)
    parser.add_argument("--out")
    args = parser.parse_args()

    Handler.delay = args.delay_ms / 1000.0
    port = free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/v1/completions"
    time.sleep(0.05)

    try:
        sequential = run_sequential(url, args.requests)
        concurrent = run_concurrent(url, args.requests, args.concurrency)
    finally:
        server.shutdown()
        server.server_close()

    speedup = sequential / max(concurrent, 1e-9)
    report = {
        "backend": "threaded-openai-mock",
        "requests": args.requests,
        "concurrency": args.concurrency,
        "delay_ms": args.delay_ms,
        "sequential_seconds": round(sequential, 4),
        "concurrent_seconds": round(concurrent, 4),
        "speedup": round(speedup, 3),
        "passed": speedup >= args.min_speedup,
        "min_speedup": args.min_speedup,
        "note": "No-model B34 smoke; real acceptance still needs a live batching backend.",
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text, end="")
    if not report["passed"]:
        return 1
    print(
        f"SMOKE OK: B34 bounded concurrency {report['speedup']:.2f}x "
        f"({report['requests']} requests, concurrency={report['concurrency']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
