# Contributing

Entry points for building, testing, and linting. The directory map is in
[`README.md`](README.md); working rules for agents are in [`AGENTS.md`](AGENTS.md).

Before running anything long — training, benchmarks, install or compile loops —
read the GPU-safety section of `AGENTS.md`.

## Prerequisites

| Surface | Needs |
|---|---|
| `native-mac/` | macOS + Xcode 27+, Metal toolchain (`xcodebuild -downloadComponent MetalToolchain`) |
| `browser/`, `docs-site/` | Node 22.12+, pnpm 10 |
| `python_ref/`, `tests/` | Python 3.11+ (`torch`, `numpy`; `python_ref/requirements.txt`) |
| `wasm/` | Emscripten SDK, pinned to 5.0.7 in CI |
| `scripts/*/` Rust crates | A stable Rust toolchain (edition 2024) |

## Build

```bash
# Mac CLI + app (the primary surface)
cd native-mac
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift build -c release
# binary at native-mac/.build/release/posttrainllm

# Browser playground (also builds docs-site and merges it in under /docs)
cd browser && pnpm install && pnpm run build

# WASM kernels — only when C++ under wasm/ changes. CI byte-compares the
# committed browser/public/tinygpt*.{js,wasm}, so rebuild with the pinned emsdk.
bash wasm/build_wasm.sh && bash wasm/build_wasm64.sh
```

## Test

```bash
pnpm test                     # browser unit tests + evals/common-smoke.sh
pytest tests/                 # cross-cutting Python tests
cd native-mac && xcodebuild test -scheme posttrainllm-Package -destination 'platform=macOS'
bash evals/<name>-smoke.sh    # a single eval suite
```

Tests live in four places, by design:

- `tests/` — cross-cutting Python and Node checks. Most import modules out of
  `scripts/` directly, so they follow that layout rather than `python_ref/`.
- `native-mac/Tests/` — XCTest, three targets.
- `browser/src/__tests__/` — vitest, with a coverage ratchet in
  `browser/vitest.config.ts`.
- `evals/*.sh` — end-to-end smoke suites. Ten run in CI; the rest are run on
  demand. `evals/_common.sh` provides shared helpers and locates or builds the
  Swift binary.

## Lint and quality gates

```bash
pnpm run quality   # everything below, in order
```

| Command | Checks |
|---|---|
| `pnpm run format:check` | prettier |
| `pnpm run lint` | ruff, rustfmt, prettier |
| `pnpm run typecheck` | `tsc --noEmit` in `browser/` |
| `pnpm run quality:unused` | knip + vulture |
| `pnpm run quality:complexity` | lizard, against a fixed baseline |
| `pnpm run quality:duplication` | jscpd, against a fixed baseline |
| `pnpm run quality:cycles` | import cycles (knip, pycycle, cargo) |
| `pnpm run quality:dependencies` | `pnpm audit` across all three packages |

Two things to know about these gates:

1. **They are diff-scoped.** `scripts/code-health-files.mjs` limits the
   formatters and linters to files changed against `origin/main`, so the repo
   has never been formatted wholesale and untouched legacy files stay exempt.
2. **The complexity and duplication gates are baselines, not thresholds.** They
   compare against hardcoded numbers in `scripts/check-*.mjs`. When a change
   improves a number, the script says so — lower the baseline in the same PR.

Swift is formatted separately and is opt-in by rule:

```bash
swiftformat --lint native-mac/Sources native-mac/Tests
```

## Conventions

- **Configs are the source of truth.** Exact specs live in `configs/*.json`;
  reference them rather than restating numbers in code or docs.
- **Respect the build order:** Python reference → WASM → WebGPU. Don't build a
  browser path before the Python reference for that component is correct.
- **Docs have one home.** Everything lives under `docs/`; `docs-site/` is only a
  presentation layer and owns no content. If you move a doc, add a row to
  [`docs/MAP.md`](docs/MAP.md).
- **Model weights are committed deliberately.** `browser/public/gallery/*.bin`
  and the compiled `tinygpt*.wasm` are shipped artifacts, un-ignored on purpose —
  Cloudflare Pages never rebuilds them. CI has drift jobs that police them.

## CI

`.github/workflows/ci.yml` runs on push and PR to `main`: `mac`,
`swift-quality`, `python`, `code-health`, `evals`, plus the `gallery-drift` and
`wasm-drift` guards.

Two gaps worth knowing: the `browser` job is disabled (`if: false`) while that
surface is parked, so vitest, the Astro build, and the bundle-size budget do not
gate PRs — only `tsc --noEmit` does, via `code-health`. And `deploy.yml` is
`workflow_dispatch` only, so the production build first runs at deploy time.
