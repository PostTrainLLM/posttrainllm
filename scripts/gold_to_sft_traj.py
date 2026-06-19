"""Synthesize SFT trajectories directly from BFCL GOLD sequences — no teacher API.

For verifiable multi-turn tasks the gold ground_truth IS the correct trajectory, so we can
behavior-clone it for free instead of paying a frontier teacher (RFT). Per turn: emit the gold
calls as an assistant tool_calls message, execute them via BFCL to get real tool results, append.
Output matches the {id, tools, messages} dump format that render_sft_from_traj.py consumes.

Run: MT_DATA=scripts/fixtures/multi_turn_train_data.jsonl \
     MT_GOLD=scripts/fixtures/multi_turn_train_gold.jsonl \
     MT_OUT=/tmp/gold_traj.jsonl python3 scripts/gold_to_sft_traj.py [N]
"""
import sys, os, json, ast
BFCL="/Users/sarthak/.cache/tinygpt/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard"
sys.path.insert(0,BFCL)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
FUNCDOC=f"{BFCL}/bfcl_eval/data/multi_turn_func_doc"
DATA=os.environ["MT_DATA"]; GOLD=os.environ["MT_GOLD"]; OUT=os.environ["MT_OUT"]
N=int(sys.argv[1]) if len(sys.argv)>1 else 10**9
SYS=os.environ.get("MT_SYS",
    "You are an autonomous tool-using agent. For each user turn: (1) plan the full sequence of "
    "function calls the task needs; (2) execute them, reading each tool result; (3) never repeat "
    "a call that already succeeded; (4) once every requested action is complete, stop and emit no "
    "tool call. Use the tool results to track the current state as you go.")
TYPEMAP={"dict":"object","list":"array","tuple":"array","float":"number","integer":"integer","string":"string","boolean":"boolean","bool":"boolean","any":"string"}
def norm_schema(s):
    if isinstance(s,dict):
        s=dict(s)
        if isinstance(s.get("type"),str): s["type"]=TYPEMAP.get(s["type"],s["type"])
        if isinstance(s.get("properties"),dict): s["properties"]={k:norm_schema(v) for k,v in s["properties"].items()}
        if "items" in s: s["items"]=norm_schema(s["items"])
        return s
    return s
def load_catalog(classes,excluded):
    out=[]
    for c in classes:
        for line in open(f"{FUNCDOC}/{CLASS_FILE_PATH_MAPPING[c].split('.')[-1]}.json"):
            if line.strip():
                fd=json.loads(line)
                if fd.get("name") not in excluded: out.append(fd)
    return out
def to_tools(cat): return [{"type":"function","function":{"name":f["name"],"description":f.get("description",""),"parameters":norm_schema(f.get("parameters",{}))}} for f in cat]
def parse_call(cs):
    node=ast.parse(cs.strip(),mode="eval").body
    name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr
    args={kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
    return name,args

def synth(ex,gold):
    cat=load_catalog(ex["involved_classes"],set(ex.get("excluded_function",[]))); tools=to_tools(cat)
    messages=[{"role":"system","content":SYS}]; gt=gold["ground_truth"]
    for ti,turn in enumerate(ex["question"]):
        user=" ".join(m["content"] for m in turn if m.get("role")=="user")
        messages.append({"role":"user","content":user})
        callstrs=gt[ti] if ti<len(gt) else []
        if not callstrs:  # turn with no action — model should just stop
            messages.append({"role":"assistant","content":""}); continue
        tcs=[]
        for cs in callstrs:
            try: name,args=parse_call(cs)
            except Exception: return None
            tcs.append({"type":"function","function":{"name":name,"arguments":args}})
        messages.append({"role":"assistant","content":"","tool_calls":tcs})
        try: results,_=execute_multi_turn_func_call(callstrs,ex["initial_config"],ex["involved_classes"],"gold",ex["id"],is_evaL_run=False)
        except Exception as e: results=["ok"]*len(callstrs)
        messages.append({"role":"tool","content":json.dumps(results)})
        # CRITICAL: demonstrate the turn-complete STOP signal (assistant emits no tool calls).
        # Without this the model never learns to stop and over-calls at eval — the gap vs a
        # teacher whose trajectories naturally end each turn with a no-call message.
        messages.append({"role":"assistant","content":"All requested actions for this turn are complete."})
    return {"id":ex["id"],"tools":tools,"messages":messages}

data=[json.loads(l) for l in open(DATA)][:N]; golds={json.loads(l)["id"]:json.loads(l) for l in open(GOLD)}
n=ok=0
with open(OUT,"w") as f:
    for ex in data:
        g=golds.get(ex["id"])
        if not g: continue
        n+=1
        rec=synth(ex,g)
        if rec: f.write(json.dumps(rec)+"\n"); ok+=1
print(f"synthesized {ok}/{n} gold trajectories -> {OUT}")
