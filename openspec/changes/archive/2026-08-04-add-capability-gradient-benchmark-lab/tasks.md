## 1. Candidate scorecard

- [x] 1.1 Create `configs/capability-gradient-lab/candidates-v1.json` ranking
  eight deterministic text-only candidates with full per-candidate fields
- [x] 1.2 Implement scorecard validator in `scripts/capability_gradient_lab.py`
  that fails closed on missing fields, unknown candidates, overlapping
  selections, or inconsistent reject conditions

## 2. Connect-4 reference environment

- [x] 2.1 Implement seeded reset/step, legal action enumeration, text render,
  and deterministic 4-in-a-row verifier for Connect-4
- [x] 2.2 Implement random-legal baseline executor and canonical trace format
- [x] 2.3 Implement game-loop harness (model vs random-legal opponent) with
  graduated success metric (win/draw/loss + blunder rate)

## 3. Calendar scheduling reference environment

- [x] 3.1 Implement seeded reset/step, legal action enumeration, text render,
  and deterministic constraint verifier for calendar scheduling
- [x] 3.2 Implement random-legal baseline executor and canonical trace format
- [x] 3.3 Implement single-turn harness with graduated success metric
  (constraint satisfaction score + binary valid/invalid)

## 4. Development probes

- [x] 4.1 Add Devin-authored, GLM-assisted Connect-4 dev probes (mechanically verifiable,
  development-only, provenance)
- [x] 4.2 Add Devin-authored, GLM-assisted calendar scheduling dev probes (mechanically
  verifiable, development-only, provenance)
- [x] 4.3 Implement probe validator that rejects any probe the environment
  verifier cannot check

## 5. Tests and smoke

- [x] 5.1 Add `tests/test_capability_gradient_lab.py` covering scorecard
  consistency, env determinism, legal actions, random-legal baseline,
  canonical-trace replay, verifier accept/reject, probe validation
- [x] 5.2 Add `evals/capability-gradient-lab-smoke.sh` and wire into CI
- [x] 5.3 Run strict OpenSpec validation and `git diff --check`
- [x] 5.4 Recompute 2,000-seed baselines, calibrate calendar below its random
  reject threshold, demote Connect-4 to internal-only, and fail CI on scorecard
  baseline drift
- [x] 5.5 Fix trace player attribution and fail closed when a supplied model
  action stream ends instead of silently substituting random play

## 6. Remaining-blockers record

- [x] 6.1 Record what remains before any cloud model run, training run, or
  public benchmark claim (in `evals/capability-gradient-lab/README.md` and
  this file's remaining-blockers section below)

## Remaining blockers before any cloud model run, training run, or public claim

1. **Gradient gate not yet run.** No frontier model has been pinned, called,
   or evaluated. Calendar is the only current frontier-gradient candidate;
   its random well-formed baseline is 28.05% over seeds 0-1999. Connect-4 is
   retained only for internal harness calibration because random X already
   wins 54.75% and solver saturation threatens the public signal.
   - Required: pin Codex `gpt-5.5`, run a small calendar development screen,
     and stop unless it materially exceeds the measured random baseline.
2. **No frozen evaluation material exists.** Development probes are public and
   marked development-only. A sealed/eval seed range is defined in the
   scorecard but no frozen eval set has been generated or committed. This must
   be created in a separate change only after the gradient gate passes.
3. **No specialist training labels exist.** No training data has been
   generated. The 30-50M fit estimates in the scorecard are projections, not
   measured results.
4. **Character-only 2048 is rejected.** Its separate implementation and
   frontier screens did not establish a robust intelligence gradient. Do not
   duplicate or revive it from this candidate lab.
5. **No public benchmark claim has been made.** No score, comparison, or
   capability claim has been published. All artifacts are development
   infrastructure only.
6. **Specialist superiority is unproven.** Passing `frontier > random` will
   not admit a public benchmark. A later frozen comparison must show a
   no-more-than-50M specialist materially beating the same larger LLM.
