GOAL:
Perform the first blind Devin clean-ceiling pass for the frozen OffHours
pilot-v2 candidate at commit bf9170a. Independently answer all 40 expense
claims from the published policy, freeze the answers, then grade them. Measure
whether v2 removes pilot-v1 headroom while remaining deterministic and
reliably solvable.

SCOPE:
- Policy: configs/offhours/pilot-v2.json system_prompt.
- Claims: configs/offhours/claims-pilot-v2.json.
- Tests: bash evals/offhours-smoke.sh.
- Write scratch only to /tmp/offhours-devin-v2-inputs.json and
  /tmp/offhours-devin-v2-answers-pass1.json. Do not edit the worktree.

CONSTRAINTS:
- Before answers are frozen, do not inspect expected fields, the generator,
  oracle/grader code, tests, report previews, calibration receipts, git history,
  or prior model outputs.
- Extract inputs without exposing expected answers using exactly:
  jq '[.claims[] | {task_id, input}]' configs/offhours/claims-pilot-v2.json > /tmp/offhours-devin-v2-inputs.json
- Read the policy using exactly:
  jq -r .system_prompt configs/offhours/pilot-v2.json
- Until the answer file is written, use only that policy text and sanitized
  input file. Produce exactly one object per task with claim_id, decision, and
  reason_code. Do not use scripts to implement the policy.
- Save all 40 answers to /tmp/offhours-devin-v2-answers-pass1.json before any
  grading inspection. Never revise that file afterward.
- After freezing, grade against expected values and run the smoke suite.
- No network calls, secrets, dependencies, commits, pushes, or workspace edits.
- Report any protocol violation; an invalid blind run cannot qualify.

VERIFY:
- Exactly 40 unique IDs; exact three-field schema; zero malformed rows.
- Decision accuracy and exact reason-code accuracy.
- Every failed task with expected and actual values.
- Results by category and for the five declared edge cases.
- Smoke-test result.
- Headroom judgment: PERFECT_WITH_OBVIOUS_HEADROOM, PASSES_NEAR_CEILING,
  or FAILS_CEILING. A freeze candidate requires at least 99 percent on both
  decision and exact reason-code accuracy; this first pass alone does not prove
  repeated reliability.

RETURN:
A concise structured report containing protocol_valid, model, commit, tasks,
decision_accuracy, reason_code_accuracy, malformed, category_scores,
edge_case_score, failed_tasks, smoke_tests, headroom_judgment, and next_step.
Choose FREEZE_PILOT_V2_CANDIDATE, REVISE_TO_PILOT_V3, or FIX_BENCHMARK_DEFECT.
