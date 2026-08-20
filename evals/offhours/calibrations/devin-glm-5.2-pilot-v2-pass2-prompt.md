GOAL:
Run a second independent blind reliability pass on the frozen OffHours
pilot-v2 candidate at commit bf9170a. Answer all 40 clean claims from the
published policy, freeze the answers, then grade them.

SCOPE:
- Read the policy only with: jq -r .system_prompt configs/offhours/pilot-v2.json
- Extract inputs only with: jq '[.claims[] | {task_id, input}]' configs/offhours/claims-pilot-v2.json > /tmp/offhours-devin-v2-inputs-pass2.json
- Save frozen answers to /tmp/offhours-devin-v2-answers-pass2.json.
- Run bash evals/offhours-smoke.sh only after answers are frozen.
- Do not edit the worktree.

CONSTRAINTS:
- Before freezing answers, do not inspect expected fields, generator, oracle,
  tests, reports, calibration receipts, git history, prior outputs, or any
  pass-1 scratch file. Do not use code to implement the policy.
- Use only the policy text and sanitized pass-2 input file while deciding.
- Return exactly one object per task with claim_id, decision, and reason_code.
- Write all 40 answers before grading and never revise the answer file.
- After freezing, grade against expected values and run smoke tests.
- No network, secrets, dependency changes, commits, pushes, or repo writes.
- Any blind-protocol violation invalidates the pass.

VERIFY:
Report protocol validity, model, commit, exact task/schema counts, decision and
reason-code accuracy, per-category scores, five-edge-case score, every failure,
and smoke status. A reliability pass requires at least 99 percent on both
accuracy metrics with zero malformed rows.

RETURN:
A concise structured report and one decision: PASS_RELIABILITY or
FAIL_RELIABILITY.
