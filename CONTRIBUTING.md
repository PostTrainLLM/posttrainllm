# Contributing

Entry points for building, testing, and linting. The directory map is in
[`README.md`](README.md); working rules for agents are in [`AGENTS.md`](AGENTS.md).

Before running anything long — training, benchmarks, install or compile loops —
read the GPU-safety section of `AGENTS.md`.

## Prerequisites

| Surface                  | Needs                                                                               |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `native-mac/`            | macOS + Xcode 27+, Metal toolchain (`xcodebuild -downloadComponent MetalToolchain`) |
| `browser/`, `docs-site/` | Node 22.12+, pnpm 10.33.2 (pinned in the root `packageManager`)                     |
| `python_ref/`, `tests/`  | Python 3.11+ (`torch`, `numpy`; `python_ref/requirements.txt`)                      |
| `wasm/`                  | Emscripten SDK, pinned to 5.0.7 in CI                                               |
| `scripts/*/` Rust crates | A stable Rust toolchain (edition 2024)                                              |

## Build

```bash
# Mac CLI + app (the primary surface)
cd native-mac
xcrun swift build -c release
# binary at native-mac/.build/release/posttrainllm

# Browser playground (also builds docs-site and merges it in under /docs).
# One workspace install from the repo root covers browser/ and docs-site/.
pnpm install
pnpm --dir browser run build

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

For a release visual check, serve the production build in one terminal and run
the responsive audit in another:

```bash
pnpm --dir browser exec astro preview --host 127.0.0.1 --port 4173
pnpm --dir browser run visual:audit
```

The audit exercises the core learning routes at 390, 768, and 1440 px, checks
console/network failures and horizontal overflow, verifies registry counts and
filters, and refreshes `artifacts/design/lab/`. Set `E2E_URL` to audit a live
deployment and `EVIDENCE_DIR` to keep live screenshots outside the worktree.

Tests live in four places, by design:

- `tests/` — cross-cutting Python and Node checks. Most import modules out of
  `scripts/` directly, so they follow that layout rather than `python_ref/`.
- `native-mac/Tests/` — XCTest, three targets.
- `browser/src/__tests__/` — vitest, with a coverage ratchet in
  `browser/vitest.config.ts`.
- `evals/*.sh` — end-to-end smoke suites. Fifteen run in CI; the rest are run on
  demand. `evals/_common.sh` provides shared helpers and locates or builds the
  Swift binary.

## Lint and quality gates

```bash
pnpm run quality   # everything below, in order
```

| Command                         | Checks                               |
| ------------------------------- | ------------------------------------ |
| `pnpm run format:check`         | prettier                             |
| `pnpm run lint`                 | ruff, rustfmt, prettier              |
| `pnpm run typecheck`            | `tsc --noEmit` in `browser/`         |
| `pnpm run quality:unused`       | knip + vulture                       |
| `pnpm run quality:complexity`   | lizard, against a fixed baseline     |
| `pnpm run quality:duplication`  | jscpd, against a fixed baseline      |
| `pnpm run quality:cycles`       | import cycles (knip, pycycle, cargo) |
| `pnpm run quality:dependencies` | `pnpm audit` over the workspace      |

Two things to know about these gates:

1. **They are diff-scoped.** `scripts/quality/code-health-files.mjs` limits the
   formatters and linters to files changed against `origin/main`, so the repo
   has never been formatted wholesale and untouched legacy files stay exempt.
2. **The complexity and duplication gates are baselines, not thresholds.** They
   compare against hardcoded numbers in `scripts/quality/check-*.mjs`. When a change
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
  [`docs/MAP.md`](docs/MAP.md) and a redirect in `browser/astro.config.mjs` so
  the published URL keeps working.
- **`scripts/` is grouped by topic**, and each folder is a flat import surface.
  See [`scripts/README.md`](scripts/README.md) before adding or moving one.
- **One workspace.** `browser/` and `docs-site/` are pnpm workspace members, so
  dependency changes and `pnpm.overrides` belong in the root `package.json`.
- **Model weights are committed deliberately.** `browser/public/gallery/*.bin`
  and the compiled `tinygpt*.wasm` are shipped artifacts, un-ignored on purpose —
  Cloudflare Pages never rebuilds them. CI has drift jobs that police them.

## CI

`.github/workflows/ci.yml` runs on push and PR to `main`: `browser`, `mac`,
`swift-quality`, `python`, `code-health`, `evals`, plus the `gallery-drift` and
`wasm-drift` guards. The browser job gates type checking, unit coverage, the
full Astro/docs build, and the bundle-size budget. The mac job builds the CLI,
runs its discovery contract, and executes the Xcode test suite.

Deployment remains deliberately separate: `deploy.yml` is
`workflow_dispatch` only, so publishing the verified build still requires an
explicit release action.
