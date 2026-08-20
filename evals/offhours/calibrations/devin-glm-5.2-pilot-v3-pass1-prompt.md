GOAL:
Perform the first blind Devin saturation pass for the frozen OffHours pilot-v3
level at commit f945d758fdcbab1eebdbbb5e0a53ecbb357a28f7. Independently
answer all 40 expense claims from the published policy, freeze the answers, and
then grade them. Determine whether the first difficulty increase above the
three-pass-perfect pilot-v2 ceiling remains reliably solvable.

SCOPE:
- Policy: configs/offhours/pilot-v3.json system_prompt.
- Claims: configs/offhours/claims-pilot-v3.json.
- Tests: bash evals/offhours-smoke.sh.
- Write scratch only to /tmp/offhours-devin-v3-inputs-pass1.json and
  /tmp/offhours-devin-v3-answers-pass1.json. Do not edit the worktree.

CONSTRAINTS:
- Before answers are frozen, do not inspect expected fields, the generator,
  oracle or grader code, tests, report previews, calibration receipts, git
  history, or prior model outputs.
- Extract inputs without exposing expected answers using exactly:
  jq '[.claims[] | {task_id, input}]' configs/offhours/claims-pilot-v3.json > /tmp/offhours-devin-v3-inputs-pass1.json
- Read the policy using exactly:
  jq -r .system_prompt configs/offhours/pilot-v3.json
- Until the answer file is written, use only that policy text and sanitized
  input file. Do not use scripts, calculators, spreadsheets, generated code,
  or external tools to implement or solve the policy. Produce exactly one
  object per task with claim_id, decision, and reason_code.
- Save all 40 answers to /tmp/offhours-devin-v3-answers-pass1.json before any
  grading inspection. Never revise that file afterward.
- After freezing, grade against expected values and run the smoke suite.
- No network calls, secrets, dependencies, commits, pushes, or workspace edits.
- Report any protocol violation; an invalid blind run cannot establish either
  a pass or a saturation failure.

VERIFY:
- Exactly 40 unique IDs; exact three-field schema; zero malformed rows.
- Decision accuracy and exact reason-code accuracy.
- Every failed task with expected and actual values.
- Results by category and for the five declared edge cases.
- Smoke-test result.
- Headroom judgment: PASSES_NEAR_CEILING or FAILS_SATURATION_LEVEL.
  A pass requires at least 99 percent decision accuracy, at least 99 percent
  exact reason-code accuracy, zero malformed outputs, and no consistently
  failed task. One pass alone does not prove repeated reliability.

RETURN:
A concise structured report containing protocol_valid, model, commit, tasks,
decision_accuracy, reason_code_accuracy, malformed, category_scores,
edge_case_score, failed_tasks, smoke_tests, headroom_judgment, and next_step.
Choose REPEAT_PILOT_V3_FOR_RELIABILITY, RETAIN_AS_FIRST_SATURATION_FAILURE, or
FIX_BENCHMARK_DEFECT.
