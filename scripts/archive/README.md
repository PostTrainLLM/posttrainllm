# Archived scripts

Superseded, historical iteration scripts moved here from `scripts/` to declutter
the active tree. They are **kept, not deleted** — they are part of the project's
journey and several docs reference them (paths now point here). Nothing in the
active pipelines (`v11_pipeline.sh`, `eval_pace_v2.py`, etc.) imports or executes
them; the only live references are prose/lineage comments.

| Group | Files | Superseded by |
|-------|-------|---------------|
| Pace planner data-gen, v3–v8 | `pace-v3-prep.py`, `pace-v4-gold-labels.py`, `pace-v5-*.py`, `pace-v6*.py`, `pace-v8-augment.py` | v9/v10/v11 corpus builders |
| Early Pace eval experiments | `pace-eval-baseline*.py`, `pace-eval-cli.py`, `pace-eval-fixtures.py`, `pace-eval-v6.py` | `eval_pace_v2.py` |
| VLM A/B one-off | `eval_pace_vlm_ab.py` | — (decision recorded in docs) |
| One-off builders | `build-bfcl-pace-12.py` | — |
| Research PoCs | `dist_dp_poc.py`, `game_rl_poc.py` | — (findings in `docs/learn/`) |
| Old experiment runners | `run_remaining_experiments.sh`, `run_all_remaining.sh` | — |
| v7 planner track | `v7-data/`, `v7-eval/` | v8+ track |

Recover any file with its full history via `git log --follow scripts/archive/<file>`.
