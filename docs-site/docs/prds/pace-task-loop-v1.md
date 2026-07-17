---
title: "Pace Task Loop v1 — long-horizon tasks + the bulk-download benchmark"
description: "Status: PRD (2026-06-10). Triggered by a real user moment: bulk-downloading"
---

# Pace Task Loop v1 — long-horizon tasks + the bulk-download benchmark

Status: PRD (2026-06-10). Triggered by a real user moment: bulk-downloading
files via the Claude browser extension was painfully slow. The standing rule
(memory `pace-does-it-not-claude`): the deliverable is PACE executing the
task, measured — not a script that fakes the outcome.

## Acceptance scenario (also the launch demo)

> User says: **"download all asset packs from quaternius.com"**
> Pace opens the browser, iterates the site, clicks every pack's download,
> tracks progress, and reports done. Stopwatch runs the whole time.

Site facts (scraped 2026-06-10): 82 packs — 71 link to public Google Drive
folders, 11 to itch.io pages. All CC0. A successful v1 = all 71 Drive packs
triggered; itch.io packs may be flagged as "needs account" (an honest
`out_of_scope`/`clarify` is a PASS, silent skip is a FAIL).

## The gap (verified in pace sources)

`PaceActionExecutor.swift` executes single actions and pre-planned sequences
(`executeActionSequence:650`, `executeActionPlan:665`). There is **no
observe → plan → act → re-observe loop** — Pace today is one-shot per
utterance. Long-horizon tasks need:

1. **`PaceTaskLoop`** (new): drive {AX snapshot → planner call → execute →
   settle-wait → re-snapshot} until goal or budget. Step budget (default 50),
   stall detection (same AX hash twice + same proposed action twice → stop and
   ask), per-step latency log.
2. **Progress state in the prompt**: append a compact "done so far" line per
   step (the planner-level fixtures `evals/task-latency-download-v1/` encode
   exactly this pattern — step N's prompt carries steps 1..N-1's outcomes).
3. **Goal check**: planner emits `intent=answer` with "task complete" (v11
   schema supports it) — the loop's exit condition, plus the hard budget.
4. **Browser AX scale**: executor already caps node traversal
   (`maximumNodeCount`); reuse for big web pages, prefer link/button roles.

No new planner training required: v11's grammar already has `action`,
`clarify`, `out_of_scope`, and multi-call `payload.calls` (≤8) — the loop is
pure Swift orchestration around the existing pipeline.

## Benchmark protocol

| Column | How measured |
|---|---|
| Pace (task loop) | wall-clock from utterance to "done", plus per-step breakdown (snapshot ms / planner ms / dispatch ms) |
| Claude extension | user-measured stopwatch, same task |
| Manual human | one timed manual run (the floor) |

Per-step planner budget on shipped config (measured 2026-06-10): int8 serve =
212 tok/s, TTFW 119 ms, ~60-token constrained JSON → **~0.4–0.6 s/decision**.
AX snapshot + dispatch ≈ 0.1–0.2 s. Target: **< 1 s/step**, vs the cloud
extension's ~5–15 s/step. With ~85 steps (71 Drive packs + navigation), Pace
target ≈ **1.5–2 min** of decisions + download time; extension ≈ 10–20 min.

## Milestones

- **T0 (planner-level, runnable now):** step-latency bench on the
  `task-latency-download-v1` fixtures against the int8 v9/v11 serve — proves
  the per-decision budget without touching Swift. Runner:
  `scripts/bench_task_latency.py`.
- **T1 (loop):** `PaceTaskLoop.swift` + progress-state prompting + stall/
  budget guards. Unit tests with a scripted fake AX provider.
- **T2 (live run):** the quaternius scenario end-to-end on the real browser,
  measured, vs user's Claude-extension stopwatch number. This is the
  benchmark row + the demo recording.

Sequencing: T0 after the v11 verdict (GPU free), T1–T2 in the "whatever Pace
needs" phase-2 window — this IS phase-2 work, same tier as WhisperKit.

## Risks

- Drive folder pages are not classic AX surfaces — clicking "Download" opens
  Drive's own UI; may need 2–3 extra steps per pack (budget covers it) or the
  VLM for AX-blind regions (ties into the A/B).
- Popup/permission dialogs mid-run: `confirm_destructive`-style gating
  already exists in v11 intents; the loop surfaces unknown dialogs to the
  user instead of guessing.
- Runaway loops: hard step budget + stall detection are non-negotiable
  (a fast agent that loops forever is worse than a slow one).

## Related

- `evals/task-latency-download-v1/` — planner-level step fixtures
- memory `pace-does-it-not-claude`, `pace-doctrine-2026-06-08`
- `docs/prds/pace-planner-v11-ship-gate.md` — the planner this loop drives
