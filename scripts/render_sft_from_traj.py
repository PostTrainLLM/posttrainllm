"""Render captured frontier trajectories -> mlx_lm.lora training text.

Input: MT_DUMP jsonl from bfcl_multiturn_deepseek.py (records {id, tools, messages}).
Each record is rendered through the STUDENT model's own chat template (tools= +
assistant tool_calls + tool results) so the small model learns the agentic loop in
ITS native format. Writes mlx_lm "text" format (data_dir/{train,valid}.jsonl).

Why text (not chat) format: mlx_lm's chat-format loader has no per-example tools
field — it would drop the tool catalog. We bake tools into the rendered text here.

Run: TRAJ=/tmp/ds_hard_traj.jsonl MODEL=<student path> OUT=/tmp/mt_sft \
     python3 scripts/render_sft_from_traj.py
"""
import os, json, random
from transformers import AutoTokenizer

TRAJ = os.environ["TRAJ"]
MODEL = os.environ["MODEL"]
OUT = os.environ.get("OUT", "/tmp/mt_sft")
VAL_FRAC = float(os.environ.get("VAL_FRAC", "0.1"))

tok = AutoTokenizer.from_pretrained(MODEL)

def norm_msg(m):
    """Normalize an OpenAI-style message to what the chat template expects."""
    if m.get("role") == "assistant" and m.get("tool_calls"):
        tcs = []
        for tc in m["tool_calls"]:
            fn = tc["function"]
            args = fn.get("arguments")
            if isinstance(args, str):
                try: args = json.loads(args or "{}")
                except Exception: args = {}
            tcs.append({"type": "function", "function": {"name": fn["name"], "arguments": args}})
        return {"role": "assistant", "content": m.get("content") or "", "tool_calls": tcs}
    if m.get("role") == "tool":
        return {"role": "tool", "content": m.get("content", "")}
    return {"role": m["role"], "content": m.get("content", "")}

def render(rec):
    msgs = [norm_msg(m) for m in rec["messages"]]
    return tok.apply_chat_template(msgs, tools=rec.get("tools"),
                                   tokenize=False, add_generation_prompt=False)

recs = [json.loads(l) for l in open(TRAJ) if l.strip()]
texts = []
for r in recs:
    try:
        texts.append({"text": render(r)})
    except Exception as e:
        print(f"  skip {r.get('id')}: {str(e)[:80]}")

rng = random.Random(0); rng.shuffle(texts)
n_val = max(1, int(len(texts) * VAL_FRAC)) if len(texts) > 10 else 0
val, train = texts[:n_val], texts[n_val:]
os.makedirs(OUT, exist_ok=True)
open(f"{OUT}/train.jsonl", "w").write("".join(json.dumps(t) + "\n" for t in train))
open(f"{OUT}/valid.jsonl", "w").write("".join(json.dumps(t) + "\n" for t in (val or train[:1])))
print(f"rendered {len(texts)}/{len(recs)} -> {OUT}  (train={len(train)} valid={len(val) or 1})")
if texts: print("--- sample (first 600 chars) ---\n" + texts[0]["text"][:600])
