# scripts/

Tooling for the factory: data prep, training drivers, scorers, report
compilers, and the repo's own quality gates.

## Layout

| Folder | What lives there |
|---|---|
| `quality/` | The `pnpm run quality` gates — format, lint, complexity, duplication, cycles, unused code, dependency risk, Swift coverage |
| `factory/` | Report cards, foundry receipts, factory-run assembly and publish checks |
| `research/` | Autocorrect, capability graph, capability-gradient lab, everyday benchmark |
| `offhours/` | The OffHours context-interference benchmark |
| `chess/` | Chess specialist: corpus, training, Elo, gates, candidate matrices |
| `games/` | 2048 and the game arena |
| `sql/` | SQL specialist: dataset building, scoring, routed generation, perf |
| `pace/` | Pace planner and intent router |
| `bfcl/` | BFCL / tool-calling evaluation |
| `bench/` | Latency, decode, energy, and thermal benchmarks |
| `pipelines/` | Multi-step shell drivers (`v11_pipeline.sh`, `nightly.sh`, scoring runs) |
| `release/` | Mac app bundling, notarization, icons, manual deploy |
| `docs-checks/` | Docs and attempt-ledger enforcement |
| `ane/`, `vlm/`, `data-prep/`, `recipes/`, `nightly/` | Focused lanes, unchanged |
| `hf-downloader/`, `tokenizer-trainer/`, `parquet-decoder/`, `humaneval-sandbox/` | Rust crates, each with its own `Cargo.toml` |
| `archive/` | Superseded one-offs, kept for lineage — see its README |
| `fixtures/` | JSONL test data used by the scripts above |

Files that don't belong to one lane stay at the top level.

## Imports

Each folder is a flat import surface: a script run from `scripts/<group>/`
can `import` its siblings by bare name, because Python puts the script's own
directory on `sys.path`.

Two consequences worth knowing:

- **Tests** add `scripts/` *and every subfolder* to `sys.path` before importing
  script modules by name. Copy that block from any `tests/test_*.py` if you add
  a test that imports a script.
- **Cross-folder imports** need the sibling folder added explicitly. Four
  scripts do this today (for example `chess/chess_sft_train.py` importing from
  `research/`); each carries a one-line `sys.path.insert` with a comment. Prefer
  keeping a module in the folder that uses it over adding a fifth.

Scripts that resolve the repo root do it with
`Path(__file__).resolve().parents[2]` — two levels up from `scripts/<group>/`.
