"""Multi-turn / agentic tool-calling eval (see docs/prds/multi-turn-agentic-eval.md).

STATEFUL: reuses BFCL's own multi-turn machinery (steal-first) — the involved_classes
backends, execute_multi_turn_func_call, and multi_turn_checker.

INFERENCE (the fix): uses the model's NATIVE tool-calling chat template — proper
`tools=` catalog + assistant/tool message roles (what Qwen3 was TRAINED on) + BFCL's
own multi-turn behaviour prompt — instead of a hand-rolled text transcript. The model
acts, sees tool results as `tool` messages, and keeps calling until the turn's task is
done; we collect [turn][step][callstr] and hand off to BFCL's checker.

Local MLX only (the clean gate reference): MODEL=<path> python3 bfcl_multiturn_eval.py [n]
"""
import sys, os, json

BFCL_ROOT = os.path.expanduser(
    "~/.cache/tinygpt/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard")
sys.path.insert(0, BFCL_ROOT)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING

_argv = sys.argv; sys.argv = ["bfcl_ast_eval"]
import bfcl_ast_eval as h            # reuse the call parser (extract_calls)
sys.argv = _argv

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
CAT = "multi_turn_base"
MAX_STEPS = 12   # BFCL allows up to 20 agentic steps per user turn
DATA = os.environ.get("MT_DATA", f"{h.BFCL}/BFCL_v4_{CAT}.json")
GOLD = os.environ.get("MT_GOLD", f"{h.BFCL}/possible_answer/BFCL_v4_{CAT}.json")
FUNCDOC = f"{h.BFCL}/multi_turn_func_doc"
MODEL_PATH = os.environ["MODEL"]
MODEL_NAME = MODEL_PATH.rstrip("/").split("/")[-1]

# BFCL's own multi-turn behaviour instruction (constants/default_prompts.py)
SYS = os.environ.get("MT_SYS",
      ("You are an expert in composing functions. At each turn, do your best to complete "
       "the tasks requested by the user within the current turn. Continue to output function "
       "calls until you have fulfilled the user's request to the best of your ability. Once "
       "you have no more functions to call, the system considers the current turn complete "
       "and proceeds to the next turn."))

_model, _tok = load(MODEL_PATH)
_sampler = make_sampler(temp=0.0)

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

def to_tools(catalog):  # BFCL func doc -> OpenAI tools schema the chat template expects
    return [{"type": "function", "function": {"name": f["name"],
             "description": f.get("description", ""), "parameters": f.get("parameters", {})}}
            for f in catalog]

def to_callstr(name, args):
    return f"{name}(" + ", ".join(f"{k}={v!r}" for k, v in (args or {}).items()) + ")"

def gen(messages, tools):
    prompt = _tok.apply_chat_template(messages, tools=tools, add_generation_prompt=True, tokenize=False)
    return generate(_model, _tok, prompt=prompt, sampler=_sampler, max_tokens=512, verbose=False)

def run_example(ex, gold):
    catalog = load_catalog(ex["involved_classes"], set(ex.get("excluded_function", [])))
    tools = to_tools(catalog)
    messages = [{"role": "system", "content": SYS}]
    decoded = []
    for turn in ex["question"]:
        messages.append({"role": "user",
                         "content": " ".join(m["content"] for m in turn if m.get("role") == "user")})
        turn_steps = []
        for _ in range(MAX_STEPS):
            out = gen(messages, tools)
            calls = h.extract_calls(out)
            messages.append({"role": "assistant", "content": out})   # raw, contains <tool_call> blocks
            if not calls:
                break                                                # turn complete
            callstrs = [to_callstr(n, a) for n, a in calls]
            turn_steps.append(callstrs)
            try:
                results, _ = execute_multi_turn_func_call(
                    callstrs, ex["initial_config"], ex["involved_classes"],
                    MODEL_NAME, ex["id"], is_evaL_run=False)
            except Exception as e:
                results = [f"<exec error: {e}>"]
            messages.append({"role": "tool", "content": json.dumps(results)})
        decoded.append(turn_steps if turn_steps else [[]])
    res = multi_turn_checker(decoded, gold["ground_truth"], ex, CAT, MODEL_NAME)
    return bool(res.get("valid", False)) if isinstance(res, dict) else bool(res)

def main():
    data = [json.loads(l) for l in open(DATA)][:N]
    golds = {json.loads(l)["id"]: json.loads(l) for l in open(GOLD)}
    print(f"MULTI-TURN {CAT}  model={MODEL_NAME}  n={len(data)}  (native chat-template + tools)", flush=True)
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
    print("(single-turn ref: Qwen3-4B-2507 bf16 = 88.7; 30B-A3B aced single-turn 96/96)")

if __name__ == "__main__":
    main()
