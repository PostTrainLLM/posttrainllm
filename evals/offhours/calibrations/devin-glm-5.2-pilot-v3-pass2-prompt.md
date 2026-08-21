GOAL:
Run blind OffHours pilot-v3 saturation pass 2 at commit
f945d758fdcbab1eebdbbb5e0a53ecbb357a28f7. Freeze 40 answers, then grade.

SCOPE:
- Read only configs/offhours/pilot-v3.json system_prompt and sanitized claim
  inputs before freeze.
- Scratch: /tmp/offhours-devin-v3-inputs-pass2.json and
  /tmp/offhours-devin-v3-answers-pass2.json.
- Do not edit the worktree.

BLIND PROTOCOL:
1. Run exactly:
   jq '[.claims[] | {task_id, input}]' configs/offhours/claims-pilot-v3.json > /tmp/offhours-devin-v3-inputs-pass2.json
2. Run exactly: jq -r .system_prompt configs/offhours/pilot-v3.json
3. Before freeze, do not inspect expected fields, generator, oracle, grader,
   tests, reports, receipts, history, or prior outputs. No network.
4. Use only the policy and sanitized inputs. Do not use scripts, calculators,
   spreadsheets, code, or external tools to solve the policy.
5. Do not narrate or show calculations. Write answers directly to the answer
   file. Every answer object must have exactly these keys: claim_id, decision,
   reason_code. task_id is not an output key. You may build the file
   incrementally, but do not inspect expected data until it contains all 40
   unique answers and you have frozen it.
6. After freeze, never revise the answer file. Grade exact field names,
   decisions, and reason codes against expected values, then run
   bash evals/offhours-smoke.sh.

PASS GATE:
At least 99% decisions, at least 99% exact reason codes, zero malformed output,
no consistently failed task, valid protocol, and passing smoke tests.

RETURN:
Only a compact final report: protocol_valid, model, commit, tasks,
decision_accuracy, reason_code_accuracy, malformed, category_scores,
edge_case_score, failed_tasks, smoke_tests, headroom_judgment, next_step.
Use PASSES_NEAR_CEILING or FAILS_SATURATION_LEVEL, then choose
REPEAT_PILOT_V3_FOR_RELIABILITY, RETAIN_AS_FIRST_SATURATION_FAILURE, or
FIX_BENCHMARK_DEFECT.
