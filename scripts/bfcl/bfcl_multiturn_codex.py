"""Multi-turn agentic eval with a CODEX (gpt-5.5) frontier backend — FREE under the user's
Codex subscription, replacing the paid DeepSeek API for frontier-ceiling validation + teacher
trajectories.

Codex is an agent CLI, not a chat-completions endpoint, so we drive it single-shot per step:
each step we hand it the system prompt + tool catalog + the running transcript and force a JSON
answer via `codex exec --output-schema` (the next tool calls, or done). We execute the calls
through BFCL's own executor and feed results back — reusing the same executor + checker as the
other backends. `--output-schema` is what makes the agent emit clean tool-call JSON instead of
prose (the failure mode of hand-rolled transcripts with weaker models).

Usage: MT_DATA=...veryhard_data.jsonl MT_GOLD=...veryhard_gold.jsonl \
       [MT_DUMP=/tmp/codex_traj.jsonl] python3 scripts/bfcl/bfcl_multiturn_codex.py 12
"""
import sys, os, json, subprocess, tempfile
BFCL="/Users/sarthak/.cache/posttrainllm/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard"
sys.path.insert(0,BFCL)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker
from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
FUNCDOC=f"{BFCL}/bfcl_eval/data/multi_turn_func_doc"
DATA=os.environ["MT_DATA"]; GOLD=os.environ["MT_GOLD"]; N=int(sys.argv[1]) if len(sys.argv)>1 else 12
DUMP=os.environ.get("MT_DUMP")
CODEX_MODEL=os.environ.get("CODEX_MODEL","gpt-5.5")
REASONING=os.environ.get("CODEX_REASONING","medium")
MAX_STEPS=12
SYS=os.environ.get("MT_SYS",
    "You are an autonomous tool-using agent. Plan the full sequence of calls a turn needs, then "
    "emit them; never repeat a call that already succeeded; when the turn's task is fully done, "
    "return done=true with an empty tool_calls list.")

# next-action schema. OpenAI strict structured-output requires additionalProperties:false on
# EVERY object and forbids free-form objects, so `arguments` is a JSON STRING (parsed below) —
# which is how real tool_calls encode arguments anyway.
SCHEMA={"type":"object","properties":{
    "tool_calls":{"type":"array","items":{"type":"object","properties":{
        "name":{"type":"string"},"arguments":{"type":"string"}},
        "required":["name","arguments"],"additionalProperties":False}},
    "done":{"type":"boolean"}},"required":["tool_calls","done"],"additionalProperties":False}

def parse_args(s):
    if isinstance(s,dict): return s
    try: return json.loads(s) if s else {}
    except Exception: return {}

def load_catalog(classes,excluded):
    out=[]
    for c in classes:
        for line in open(f"{FUNCDOC}/{CLASS_FILE_PATH_MAPPING[c].split('.')[-1]}.json"):
            if line.strip():
                fd=json.loads(line)
                if fd.get("name") not in excluded: out.append(fd)
    return out
def to_callstr(name,args): return f"{name}("+", ".join(f"{k}={v!r}" for k,v in (args or {}).items())+")"

def codex_gen(prompt):
    with tempfile.NamedTemporaryFile("w",suffix=".json",delete=False) as sf:
        json.dump(SCHEMA,sf); schema_path=sf.name
    out_path=tempfile.mktemp(suffix=".json")
    # codex exec is non-interactive (no -a/--ask-for-approval flag; that's top-level only).
    cmd=["codex","exec","-m",CODEX_MODEL,"-c",f"model_reasoning_effort={REASONING}",
         "-s","read-only","--skip-git-repo-check",
         "--output-schema",schema_path,"-o",out_path,prompt]
    try:
        subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=300,check=False)
        txt=open(out_path).read().strip() if os.path.exists(out_path) else ""
        return json.loads(txt) if txt else {"tool_calls":[],"done":True}
    except Exception:
        return {"tool_calls":[],"done":True}
    finally:
        for p in (schema_path,out_path):
            try: os.remove(p)
            except OSError: pass

def render_prompt(SYS, tools, history, user_msg):
    toollines="\n".join(f"- {f['name']}: {json.dumps(f.get('parameters',{}).get('properties',{}))}" for f in tools)
    h="\n".join(history)
    return (f"{SYS}\n\nAvailable tools (name: params):\n{toollines}\n\n"
            f"Conversation so far:\n{h}\n\nCurrent user request: {user_msg}\n\n"
            "Respond with JSON: the next tool_calls to run now (each {name, arguments}), and "
            "done=false if more calls are still needed this turn, or an empty list with done=true "
            "when the request is fully satisfied.")

def run_example(ex,gold):
    cat=load_catalog(ex["involved_classes"],set(ex.get("excluded_function",[])))
    decoded=[]; history=[]
    for turn in ex["question"]:
        user_msg=" ".join(m["content"] for m in turn if m.get("role")=="user")
        history.append(f"USER: {user_msg}")
        steps=[]
        for _ in range(MAX_STEPS):
            resp=codex_gen(render_prompt(SYS,cat,history,user_msg))
            calls=resp.get("tool_calls") or []
            if not calls:
                break
            callstrs=[to_callstr(c.get("name"),parse_args(c.get("arguments"))) for c in calls]
            steps.append(callstrs)
            history.append("ASSISTANT called: "+"; ".join(callstrs))
            try: results,_=execute_multi_turn_func_call(callstrs,ex["initial_config"],ex["involved_classes"],"codex",ex["id"],is_evaL_run=False)
            except Exception as e: results=[f"<err {e}>"]*len(callstrs)
            history.append("TOOL results: "+json.dumps(results))
            if resp.get("done"): break
        decoded.append(steps if steps else [[]])
    r=multi_turn_checker(decoded,gold["ground_truth"],ex,"multi_turn_base","codex")
    valid=bool(r.get("valid")) if isinstance(r,dict) else bool(r)
    return valid,decoded

data=[json.loads(l) for l in open(DATA)][:N]; golds={json.loads(l)["id"]:json.loads(l) for l in open(GOLD)}
print(f"Codex {CODEX_MODEL} (reasoning={REASONING})  n={len(data)}",flush=True); ok=n=0
dumpf=open(DUMP,"a") if DUMP else None
for ex in data:
    n+=1
    try:
        valid,decoded=run_example(ex,golds.get(ex["id"])); ok+=valid
        if valid and dumpf: dumpf.write(json.dumps({"id":ex["id"],"decoded":decoded})+"\n"); dumpf.flush()
    except Exception as e: print("  ERR",ex["id"],str(e)[:90])
    print(f"  {n}/{len(data)}  pass={100*ok/n:.0f}%",flush=True)
if dumpf: dumpf.close()
print(f"== Codex task-completion: {ok}/{n} = {100*ok/max(n,1):.1f}% ==")
