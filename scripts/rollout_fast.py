"""Fast BATCHED ReST rollout collector — the throughput path for the self-improving loop.

The single-rollout harness (bfcl_multiturn_eval.py) decodes one sequence at a time; the GPU
sits idle. This collector keeps a pool of active rollouts and, each round, generates the next
assistant message for ALL of them in one `batch_generate` call (completion_batch_size concurrent).
Wall-clock per round ≈ one batched decode instead of N serial ones.

CORRECTNESS — BFCL global-state isolation: the executor keys backend instances by
`(model_name, test_id, class)` in module globals and REUSES them across calls (that's how
multi-turn state accumulates). So K rollouts of the SAME task id would share/corrupt one instance.
Fix: each rollout gets a UNIQUE model_name (`<base>_r<idx>`) used for BOTH execution and the
checker, so every rollout has isolated state even when run concurrently; instances are deleted from
globals when the rollout finalizes (no leak). The real `ex["id"]` is kept (the checker parses the
category from it). This is also why the K=1 eval was always clean — the checker runs in a separate
`is_evaL_run` ("_eval") namespace.

Drop-in env-compatible with the harness: MODEL, MT_SYS, MT_TEMP, MT_ROLLOUTS, MT_DUMP_WINS,
MT_DATA, MT_GOLD, plus MT_BATCH (concurrent decode width). NEEDS GPU validation against the
single-rollout harness before trusting (compare solved-set + dumped wins on a small slice).
"""
import sys, os, json, time
BFCL = os.path.expanduser(
    "~/.cache/tinygpt/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard")
sys.path.insert(0, BFCL)
import bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils as mtu
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker
from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
_argv = sys.argv; sys.argv = ["bfcl_ast_eval"]
import bfcl_ast_eval as h            # reuse the validated call parser (extract_calls)
sys.argv = _argv
from mlx_lm import load, batch_generate
from mlx_lm.sample_utils import make_sampler

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
CAT = "multi_turn_base"; MAX_STEPS = 12
DATA = os.environ["MT_DATA"]; GOLD = os.environ["MT_GOLD"]
MODEL_PATH = os.environ["MODEL"]; MODEL_NAME = MODEL_PATH.rstrip("/").split("/")[-1]
SYS = os.environ.get("MT_SYS",
      ("You are an autonomous tool-using agent. For each user turn: plan the calls the task needs, "
       "execute them reading each tool result, never repeat a call that already succeeded, and stop "
       "(emit no tool call) once the request is complete."))
TEMP = float(os.environ.get("MT_TEMP", "0.0"))
ROLLOUTS = int(os.environ.get("MT_ROLLOUTS", "1"))
DUMP = os.environ.get("MT_DUMP_WINS")
BATCH = int(os.environ.get("MT_BATCH", "12"))
FUNCDOC = f"{h.BFCL}/multi_turn_func_doc"

_model, _tok = load(MODEL_PATH)
_sampler = make_sampler(temp=TEMP)

def load_catalog(classes, excluded):
    funcs = []
    for c in classes:
        fname = CLASS_FILE_PATH_MAPPING[c].split(".")[-1] + ".json"
        for line in open(f"{FUNCDOC}/{fname}"):
            if line.strip():
                fd = json.loads(line)
                if fd.get("name") not in excluded: funcs.append(fd)
    return funcs

def to_tools(cat):
    return [{"type": "function", "function": {"name": f["name"],
             "description": f.get("description", ""), "parameters": f.get("parameters", {})}}
            for f in cat]

def to_callstr(name, args):
    return f"{name}(" + ", ".join(f"{k}={v!r}" for k, v in (args or {}).items()) + ")"

def cleanup(model_name):  # drop this rollout's isolated BFCL instances from module globals
    for k in [k for k in list(mtu.__dict__) if model_name in k and k.endswith("_instance")]:
        del mtu.__dict__[k]

class Roll:
    def __init__(self, ex, gold, tools, idx):
        self.ex = ex; self.gold = gold; self.tools = tools
        self.name = f"{MODEL_NAME}_r{idx}"          # unique → isolated BFCL state
        self.messages = [{"role": "system", "content": SYS}]
        self.decoded = []; self.turn_steps = []; self.ti = 0; self.step = 0
        self.status = "gen"; self.valid = False
        self.messages.append({"role": "user", "content": self.uturn(0)})
    def uturn(self, i):
        return " ".join(m["content"] for m in self.ex["question"][i] if m.get("role") == "user")

def end_turn(r):
    r.decoded.append(r.turn_steps if r.turn_steps else [[]])
    r.ti += 1
    if r.ti < len(r.ex["question"]):
        r.messages.append({"role": "user", "content": r.uturn(r.ti)}); r.turn_steps = []; r.step = 0
    else:
        try:
            res = multi_turn_checker(r.decoded, r.gold["ground_truth"], r.ex, CAT, r.name)
            r.valid = bool(res.get("valid")) if isinstance(res, dict) else bool(res)
        except Exception:
            r.valid = False
        r.status = "done"; cleanup(r.name)

def process(r, out):
    calls = h.extract_calls(out)
    r.messages.append({"role": "assistant", "content": out})
    if not calls:
        end_turn(r); return
    callstrs = [to_callstr(n, a) for n, a in calls]
    r.turn_steps.append(callstrs)
    try:
        results, _ = execute_multi_turn_func_call(
            callstrs, r.ex["initial_config"], r.ex["involved_classes"], r.name, r.ex["id"], is_evaL_run=False)
    except Exception as e:
        results = [f"<exec error: {e}>"]
    r.messages.append({"role": "tool", "content": json.dumps(results)})
    r.step += 1
    if r.step >= MAX_STEPS: end_turn(r)

def main():
    data = [json.loads(l) for l in open(DATA)][:N]
    golds = {json.loads(l)["id"]: json.loads(l) for l in open(GOLD)}
    rolls = []; idx = 0
    for ex in data:
        g = golds.get(ex["id"])
        if not g: continue
        cat = load_catalog(ex["involved_classes"], set(ex.get("excluded_function", [])))
        tools = to_tools(cat)
        for _ in range(ROLLOUTS):
            rolls.append(Roll(ex, g, tools, idx)); idx += 1
    n_tasks = len({r.ex["id"] for r in rolls})
    dumpf = open(DUMP, "a") if DUMP else None
    solved = set(); rnd = 0; t0 = time.time()
    print(f"FAST ROLLOUT  tasks={n_tasks} rollouts={ROLLOUTS} temp={TEMP} batch={BATCH}"
          + (f"  DUMP={DUMP}" if DUMP else ""), flush=True)
    while True:
        if dumpf:  # ReST: once a task has a win, skip its remaining rollouts
            for r in rolls:
                if r.status == "gen" and r.ex["id"] in solved:
                    cleanup(r.name); r.status = "skip"
        active = [r for r in rolls if r.status == "gen"]
        if not active: break
        rnd += 1
        prompts = [_tok.apply_chat_template(r.messages, tools=r.tools, add_generation_prompt=True, tokenize=True)
                   for r in active]
        texts = batch_generate(_model, _tok, prompts=prompts, max_tokens=512,
                               sampler=_sampler, completion_batch_size=BATCH).texts
        for r, out in zip(active, texts):
            process(r, out)
            if r.status == "done" and r.valid and r.ex["id"] not in solved:
                solved.add(r.ex["id"])
                if dumpf:
                    dumpf.write(json.dumps({"id": r.ex["id"], "tools": r.tools, "messages": r.messages}) + "\n")
                    dumpf.flush()
        print(f"  round {rnd}: active={len(active)} solved_tasks={len(solved)}/{n_tasks} "
              f"elapsed={time.time()-t0:.0f}s", flush=True)
    if dumpf: dumpf.close()
    print(f"== FAST ROLLOUT: {len(solved)}/{n_tasks} tasks solved (>=1 win in {ROLLOUTS}), "
          f"{rnd} rounds, {time.time()-t0:.0f}s ==")

if __name__ == "__main__":
    main()
