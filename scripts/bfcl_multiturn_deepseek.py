"""DeepSeek-V4 multi-turn agentic eval — a CLEAN true-frontier backend (OpenAI
function-calling: tools= + tool_calls/tool_call_id), reusing BFCL's executor + checker.
Used to validate the multi-turn gates: DeepSeek-V4-pro aces easy/moderate/hard 100%,
confirming the hard tier as a sound 95%+ gate (4B cliffs to 58%).

Notes: BFCL func-doc types ("dict") are normalized to JSON-schema ("object") — the API
validates strictly. urllib needs a curl User-Agent (Cloudflare 1010). Key from
$DS_KEY_FILE (default /tmp/deepseek_key), NEVER committed.
Usage: MT_DATA=scripts/fixtures/multi_turn_hard_data.jsonl \
       MT_GOLD=scripts/fixtures/multi_turn_hard_gold.jsonl DS_MODEL=deepseek-v4-pro \
       python3 scripts/bfcl_multiturn_deepseek.py 12
"""
import sys, os, json, urllib.request, time
BFCL="/Users/sarthak/.cache/tinygpt/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard"
sys.path.insert(0,BFCL)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker
from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
FUNCDOC=f"{BFCL}/bfcl_eval/data/multi_turn_func_doc"
# Generic OpenAI-function-calling backend. Defaults to DeepSeek; point DS_URL/DS_MODEL at
# any compatible server (e.g. LM Studio at http://localhost:1234/v1/chat/completions) to
# score another model (Gemma, etc.) on the same gate.
DS_URL=os.environ.get("DS_URL","https://api.deepseek.com/chat/completions")
_keyfile=os.environ.get("DS_KEY_FILE","/tmp/deepseek_key")
KEY=open(_keyfile).read().strip() if os.path.exists(_keyfile) else "not-needed"  # local servers need no key
DS_MODEL=os.environ.get("DS_MODEL","deepseek-v4-pro")
DATA=os.environ["MT_DATA"]; GOLD=os.environ["MT_GOLD"]; N=int(sys.argv[1]) if len(sys.argv)>1 else 12
DUMP=os.environ.get("MT_DUMP")  # if set: append checker-PASSING trajectories here (RFT distillation data)
MAX_STEPS=12
SYS=os.environ.get("MT_SYS",
    ("You are an expert in composing functions. At each turn, do your best to complete the tasks "
     "requested by the user within the current turn. Continue to output function calls until you "
     "have fulfilled the user's request to the best of your ability. Once you have no more functions "
     "to call, the system considers the current turn complete and proceeds to the next turn."))
def load_catalog(classes,excluded):
    out=[]
    for c in classes:
        for line in open(f"{FUNCDOC}/{CLASS_FILE_PATH_MAPPING[c].split('.')[-1]}.json"):
            if line.strip():
                fd=json.loads(line)
                if fd.get("name") not in excluded: out.append(fd)
    return out
TYPEMAP={"dict":"object","list":"array","tuple":"array","float":"number","integer":"integer","string":"string","boolean":"boolean","bool":"boolean","any":"string"}
def norm_schema(s):
    if isinstance(s,dict):
        s=dict(s)
        if isinstance(s.get("type"),str): s["type"]=TYPEMAP.get(s["type"],s["type"])
        if isinstance(s.get("properties"),dict): s["properties"]={k:norm_schema(v) for k,v in s["properties"].items()}
        if "items" in s: s["items"]=norm_schema(s["items"])
        return s
    return s
def to_tools(cat): return [{"type":"function","function":{"name":f["name"],"description":f.get("description",""),"parameters":norm_schema(f.get("parameters",{}))}} for f in cat]
def to_callstr(name,args): return f"{name}("+", ".join(f"{k}={v!r}" for k,v in (args or {}).items())+")"
def ds(messages,tools):
    body=json.dumps({"model":DS_MODEL,"messages":messages,"tools":tools,"temperature":0,"max_tokens":700}).encode()
    req=urllib.request.Request(DS_URL,data=body,method="POST",
        headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json","User-Agent":"curl/8.4.0"})
    for a in range(4):
        try:
            with urllib.request.urlopen(req,timeout=120) as r: return json.loads(r.read())["choices"][0]["message"]
        except Exception: time.sleep(3*(a+1))
    return {"content":"","tool_calls":[]}
def run_example(ex,gold):
    cat=load_catalog(ex["involved_classes"],set(ex.get("excluded_function",[]))); tools=to_tools(cat)
    messages=[{"role":"system","content":SYS}]; decoded=[]
    for turn in ex["question"]:
        messages.append({"role":"user","content":" ".join(m["content"] for m in turn if m.get("role")=="user")})
        steps=[]
        for _ in range(MAX_STEPS):
            msg=ds(messages,tools); tcs=msg.get("tool_calls") or []
            am={"role":"assistant","content":msg.get("content") or ""}
            if tcs: am["tool_calls"]=tcs
            messages.append(am)
            if not tcs: break
            callstrs=[]
            for tc in tcs:
                try: args=json.loads(tc["function"]["arguments"] or "{}")
                except Exception: args={}
                callstrs.append(to_callstr(tc["function"]["name"],args))
            steps.append(callstrs)
            try: results,_=execute_multi_turn_func_call(callstrs,ex["initial_config"],ex["involved_classes"],"deepseek",ex["id"],is_evaL_run=False)
            except Exception as e: results=[f"<err {e}>"]*len(tcs)
            for i,tc in enumerate(tcs):
                messages.append({"role":"tool","tool_call_id":tc["id"],"content":json.dumps(results[i] if i<len(results) else "ok")})
        decoded.append(steps if steps else [[]])
    r=multi_turn_checker(decoded,gold["ground_truth"],ex,"multi_turn_base","deepseek")
    valid=bool(r.get("valid")) if isinstance(r,dict) else bool(r)
    return valid,messages,tools
data=[json.loads(l) for l in open(DATA)][:N]; golds={json.loads(l)["id"]:json.loads(l) for l in open(GOLD)}
print(f"DeepSeek {DS_MODEL}  n={len(data)}"+("  DUMP="+DUMP if DUMP else ""),flush=True); ok=n=0
dumpf=open(DUMP,"a") if DUMP else None
for ex in data:
    n+=1
    try:
        valid,messages,tools=run_example(ex,golds.get(ex["id"])); ok+=valid
        if valid and dumpf:  # rejection-sampling: keep ONLY trajectories the checker passed
            dumpf.write(json.dumps({"id":ex["id"],"tools":tools,"messages":messages})+"\n"); dumpf.flush()
    except Exception as e: print("  ERR",ex["id"],str(e)[:90])
    if n%10==0: print(f"  {n}/{len(data)}  pass={100*ok/n:.0f}%",flush=True)
if dumpf: dumpf.close()
print(f"== DeepSeek-V4 task-completion: {ok}/{n} = {100*ok/max(n,1):.1f}% ==")
