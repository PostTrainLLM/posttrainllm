"""Multi-turn / agentic tool-calling eval (see docs/prds/multi-turn-agentic-eval.md).

STATEFUL: reuses BFCL's own multi-turn machinery (steal-first) — the involved_classes
backends, execute_multi_turn_func_call, and multi_turn_checker. We generate the model's
calls turn-by-turn (executing them to feed tool results back into the conversation),
collect them as [turn][step][callstr], and hand off to BFCL's checker which re-executes
(separately namespaced) and compares end-to-end state + call order.

Backends: BACKEND=frontier (claude -p) | local (MODEL=path). Usage:
  BACKEND=frontier python3 scripts/bfcl_multiturn_eval.py [n]
"""
import sys, os, json

BFCL_ROOT = os.path.expanduser(
    "~/.cache/tinygpt/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard")
sys.path.insert(0, BFCL_ROOT)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING

# reuse our single-turn harness for the model backend (gen + call parser)
_argv = sys.argv
sys.argv = ["bfcl_ast_eval"]
import bfcl_ast_eval as h
sys.argv = _argv

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
CAT = "multi_turn_base"
DATA = f"{h.BFCL}/BFCL_v4_{CAT}.json"
GOLD = f"{h.BFCL}/possible_answer/BFCL_v4_{CAT}.json"
FUNCDOC = f"{h.BFCL}/multi_turn_func_doc"
MODEL_NAME = (os.environ.get("MODEL", "frontier").rstrip("/").split("/")[-1]) or "frontier"

def load_catalog(involved_classes, excluded):
    funcs = []
    for c in involved_classes:
        fname = CLASS_FILE_PATH_MAPPING[c].split(".")[-1] + ".json"
        for line in open(f"{FUNCDOC}/{fname}"):
            if line.strip():
                fd = json.loads(line)
                if fd.get("name") not in excluded:
                    funcs.append(fd)
    return funcs

def to_callstr(name, args):
    return f"{name}(" + ", ".join(f"{k}={v!r}" for k, v in (args or {}).items()) + ")"

SYS = ("You are an AUTONOMOUS tool-using agent. For the current user turn you must "
       "COMPLETE THE ENTIRE requested task yourself by issuing function calls — the user "
       "will NOT prompt you again for intermediate steps. After each call you see its "
       "result; keep issuing the NEXT call(s) until the full task is done (a task often "
       "needs SEVERAL calls in sequence — e.g. cd, then mkdir, then mv). You may call "
       "read-only functions (ls, cat, pwd, get_*) to inspect state before acting. "
       "Emit calls as <tool_call>{\"name\":<fn>,\"arguments\":{<args>}}</tool_call> (one per "
       "call). ONLY when the turn's task is fully complete, reply with the single token "
       "DONE and no tool call.")

MAX_STEPS = 8   # agentic steps within ONE user turn (call -> see results -> call again)

def render(catalog, transcript, user_turn, step_history):
    convo = ""
    for u, calls, results in transcript:
        convo += f"User: {u}\nAssistant: {' '.join(calls) or '(no call)'}\nTool results: {results}\n"
    convo += f"User: {user_turn}\n"
    for calls, results in step_history:                  # intra-turn steps so far
        convo += f"Assistant: {' '.join(calls)}\nTool results: {results}\n"
    if step_history:
        convo += ("(The task for the CURRENT user turn is NOT finished until fully satisfied. "
                  "Given the tool results above, issue the NEXT call(s) to make progress. "
                  "Reply DONE with no tool call ONLY if everything the user asked for this turn "
                  "is already complete.)")
    return SYS, "# AVAILABLE FUNCTIONS\n" + json.dumps(catalog) + "\n\n# CONVERSATION\n" + convo

def run_example(ex, gold):
    catalog = load_catalog(ex["involved_classes"], set(ex.get("excluded_function", [])))
    decoded, transcript = [], []
    for turn in ex["question"]:
        user_turn = " ".join(m["content"] for m in turn if m.get("role") == "user")
        turn_steps, step_history = [], []
        for _ in range(MAX_STEPS):                       # agentic loop: act -> observe -> act
            system, user = render(catalog, transcript, user_turn, step_history)
            calls = h.extract_calls(h.gen(system, user))
            if not calls: break                          # model considers the turn done
            callstrs = [to_callstr(n, a) for n, a in calls]
            turn_steps.append(callstrs)
            try:
                results, _ = execute_multi_turn_func_call(
                    callstrs, ex["initial_config"], ex["involved_classes"],
                    MODEL_NAME, ex["id"], is_evaL_run=False)
            except Exception as e:
                results = [f"<exec error: {e}>"]
            step_history.append((callstrs, results))
        decoded.append(turn_steps if turn_steps else [[]])
        last_results = step_history[-1][1] if step_history else ""
        transcript.append((user_turn, [c for s in turn_steps for c in s], last_results))
    res = multi_turn_checker(decoded, gold["ground_truth"], ex, CAT, MODEL_NAME)
    return bool(res.get("valid", False)) if isinstance(res, dict) else bool(res)

def main():
    data = [json.loads(l) for l in open(DATA)][:N]
    golds = {json.loads(l)["id"]: json.loads(l) for l in open(GOLD)}
    print(f"MULTI-TURN {CAT}  backend={os.environ.get('BACKEND','frontier')} model={MODEL_NAME}  n={len(data)}", flush=True)
    ok = n = 0
    for ex in data:
        g = golds.get(ex["id"])
        if not g: continue
        n += 1
        try:
            ok += run_example(ex, g)
        except Exception as e:
            print(f"  [{ex['id']}] ERROR {e}", flush=True)
        if n % 5 == 0: print(f"  {n}/{len(data)}  task-completion={100*ok/n:.0f}%", flush=True)
    print(f"\n== MULTI-TURN task-completion: {ok}/{n} = {100*ok/max(n,1):.1f}% ==")
    print("(single-turn ref: Qwen3-4B-2507 bf16 = 88.7; frontier should ace — else fix the eval)")

if __name__ == "__main__":
    main()
