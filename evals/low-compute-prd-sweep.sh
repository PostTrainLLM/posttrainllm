#!/usr/bin/env bash
# Low-compute PRD sweep for the factory-first backlog.
#
# This is the repeatable evidence command for the P1-P3 items that can be
# checked without model training, GPU sweeps, sudo powermetrics, or live model
# servers. It intentionally excludes acceptance gates that require BFCL, a real
# adapter, a batching backend, sudo, or long model runs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOK="${EXTRACTOR_BPE_TOKENIZER:-/tmp/gpt2-tok}"

ensure_gpt2_tokenizer_fixture() {
  if [ -f "$TOK/tokenizer.json" ] &&
     [ -f "$TOK/config.json" ] &&
     [ -f "$TOK/tokenizer_config.json" ] &&
     [ -f "$TOK/vocab.json" ] &&
     [ -f "$TOK/merges.txt" ]; then
    return 0
  fi

  if [ "${TINYGPT_FETCH_TOKENIZER_FIXTURE:-1}" != "1" ]; then
    echo "SKIP: C4 tokenizer fixture missing at $TOK and TINYGPT_FETCH_TOKENIZER_FIXTURE=0"
    return 1
  fi

  echo "== preparing GPT-2 tokenizer fixture at $TOK =="
  mkdir -p "$TOK"
  for file in tokenizer.json config.json tokenizer_config.json vocab.json merges.txt; do
    curl -fsSL "https://huggingface.co/gpt2/resolve/main/$file" -o "$TOK/$file"
  done
}

run() {
  echo
  echo "== $* =="
  "$@"
}

run bash "$ROOT/evals/eval-gate-smoke.sh"
run bash "$ROOT/evals/quickstart-smoke.sh"
run bash "$ROOT/evals/traces-to-data-smoke.sh"
run bash "$ROOT/evals/factory-run-folder-smoke.sh"
run bash "$ROOT/evals/factory-run-live-evidence-smoke.sh"
run bash "$ROOT/evals/everyday-benchmark-smoke.sh"
run bash "$ROOT/evals/router-bakeoff-smoke.sh"
run bash "$ROOT/evals/b26-deferred-parity-smoke.sh"
run bash "$ROOT/evals/escalate-smoke.sh"
run bash "$ROOT/evals/b34-throughput-smoke.sh"
run bash "$ROOT/evals/swift-pure-model-smoke.sh"
run bash "$ROOT/evals/automix-smoke.sh"
run bash "$ROOT/evals/quality-filter-smoke.sh"
run bash "$ROOT/evals/compress-smoke.sh"
run bash "$ROOT/evals/scaledown-smoke.sh"
run bash "$ROOT/evals/determinism-smoke.sh"
run bash "$ROOT/evals/interp-replay-smoke.sh"
run bash "$ROOT/evals/project-validate-smoke.sh"
run bash "$ROOT/evals/export-mlx-smoke.sh"
run bash "$ROOT/evals/eval-sql-smoke.sh"
run bash "$ROOT/evals/sql-poc-smoke.sh"
run bash "$ROOT/evals/sql-poc-expanded-smoke.sh"
run bash "$ROOT/evals/sql-factory-run-smoke.sh"
run bash "$ROOT/evals/sql-spider-execution-smoke.sh"
run bash "$ROOT/evals/milu-smoke.sh"
run bash "$ROOT/evals/review-smoke.sh"
run bash "$ROOT/evals/reasoning-classifier-smoke.sh"
run python3 "$ROOT/scripts/bench/bench_energy.py" --self-test
run python3 "$ROOT/scripts/bench/bench_decode_thermal.py" --self-test

if ensure_gpt2_tokenizer_fixture; then
  run bash "$ROOT/evals/extractor-bpe-smoke.sh"
fi

echo
echo "LOW-COMPUTE PRD SWEEP PASS"
