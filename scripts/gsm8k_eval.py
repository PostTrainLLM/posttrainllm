"""Tiny self-contained GSM8K eval — independently sanity-check a model's reasoning claims.

No lm-eval-harness, no `posttrainllm serve`: load an mlx model, pull GSM8K test rows from the HF
datasets-server, let the model reason (long max_tokens), extract the final integer, score.
Built to vet "crazy benchmark" claims (e.g. VibeThinker-3B) on our own infra.

Run: MODEL=<mlx path> [GSM_N=50] [GSM_MAXTOK=3072] python3 scripts/gsm8k_eval.py
"""
import os, re, json, urllib.request

MODEL = os.environ["MODEL"]
N = int(os.environ.get("GSM_N", "50"))
MAXTOK = int(os.environ.get("GSM_MAXTOK", "3072"))
TEMP = float(os.environ.get("GSM_TEMP", "0.0"))

def fetch_gsm8k(n):
    rows, off = [], 0
    while len(rows) < n:
        url = ("https://datasets-server.huggingface.co/rows?dataset=openai/gsm8k"
               f"&config=main&split=test&offset={off}&length={min(100, n-len(rows))}")
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.4.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        batch = [r["row"] for r in data.get("rows", [])]
        if not batch: break
        rows += batch; off += len(batch)
    return rows[:n]

def gold_answer(ans):
    return int(ans.split("####")[-1].strip().replace(",", ""))

def extract_pred(text):
    m = re.findall(r"\\boxed\{\s*(-?[\d,]+)", text)        # \boxed{N}
    if m: return _to_int(m[-1])
    if "####" in text:                                     # GSM8K-style marker
        tail = text.split("####")[-1]
        nums = re.findall(r"-?[\d,]+", tail)
        if nums: return _to_int(nums[0])
    nums = re.findall(r"-?[\d,]+(?:\.\d+)?", text)          # fallback: last number
    return _to_int(nums[-1]) if nums else None

def _to_int(s):
    try: return int(round(float(s.replace(",", ""))))
    except Exception: return None

def main():
    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_sampler
    model, tok = load(MODEL)
    sampler = make_sampler(temp=TEMP)
    rows = fetch_gsm8k(N)
    name = MODEL.rstrip("/").split("/")[-1]
    print(f"GSM8K  model={name}  n={len(rows)}  max_tokens={MAXTOK} temp={TEMP}", flush=True)
    ok = 0
    for i, r in enumerate(rows, 1):
        msgs = [{"role": "user", "content": r["question"]
                 + "\nSolve step by step, then give the final answer after '####'."}]
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        out = generate(model, tok, prompt=prompt, sampler=sampler, max_tokens=MAXTOK, verbose=False)
        pred, gold = extract_pred(out), gold_answer(r["answer"])
        ok += (pred is not None and pred == gold)
        if i % 10 == 0: print(f"  {i}/{len(rows)}  acc={100*ok/i:.0f}%", flush=True)
    print(f"== GSM8K {name}: {ok}/{len(rows)} = {100*ok/max(len(rows),1):.1f}% ==")

if __name__ == "__main__":
    main()
