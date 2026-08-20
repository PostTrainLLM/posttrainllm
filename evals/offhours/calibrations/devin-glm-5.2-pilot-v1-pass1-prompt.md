GOAL:
Perform the first empirical Devin clean-ceiling pass for the frozen OffHours
pilot-v1 expense-claim ruler. Independently answer all 40 claims from the
published policy, freeze those answers, then grade them. Determine whether this
ruler is already near the hardest deterministic task set you can solve
reliably, or whether pilot-v2 must become harder before smaller-model testing.

SCOPE:
- Worktree: the current clean detached checkout of posttrainllm at 216aa02.
- Policy: configs/offhours/pilot-v1.json system_prompt.
- Claims: configs/offhours/claims-pilot-v1.json.
- Tests: bash evals/offhours-smoke.sh.
- Write calibration scratch only to /tmp/offhours-devin-inputs.json and
  /tmp/offhours-devin-answers-pass1.json. Do not edit the worktree.

CONSTRAINTS:
- This is a blind clean-task calibration, not a code implementation task.
- Before answers are frozen, do not inspect any expected field, oracle/grader
  implementation, test assertion, report preview, or prior OffHours result.
- Extract inputs without exposing expected answers using exactly:
  jq '[.claims[] | {task_id, input}]' configs/offhours/claims-pilot-v1.json > /tmp/offhours-devin-inputs.json
- Read only the system_prompt policy and that sanitized input file while
  deciding answers.
- Produce exactly one answer per task with claim_id, decision, and reason_code.
  Save the complete array to /tmp/offhours-devin-answers-pass1.json before any
  grading or oracle inspection.
- After the answer file exists, you may inspect expected values and use local
  scripts to grade it. Do not revise the frozen answer file afterward.
- Then run bash evals/offhours-smoke.sh. No network calls, secrets, dependency
  changes, commits, pushes, or workspace edits.
- Be honest if the blind protocol was violated; such a run is invalid.

VERIFY:
- Confirm the answer file has exactly 40 unique claim IDs and valid schema.
- Report decision accuracy and exact reason-code accuracy separately.
- List every failed task ID with expected and actual structured values.
- Report the smoke-test result.
- Judge headroom using evidence: PERFECT_WITH_OBVIOUS_HEADROOM,
  PASSES_NEAR_CEILING, or FAILS_CEILING. The public ceiling threshold is at
  least 99 percent clean decision accuracy; one pass is preliminary evidence,
  not reliability across five runs.

RETURN:
A concise structured report with protocol_valid, model identifier, commit,
tasks, decision_accuracy, reason_code_accuracy, malformed, failed_tasks,
smoke_tests, headroom_judgment, and next_step. Explicitly choose either
FREEZE_PILOT_V1_CANDIDATE or REVISE_TO_PILOT_V2_BEFORE_SMALLER_MODEL.
