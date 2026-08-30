"""Templated hard-tier multi-turn task generator (GorillaFileSystem backend).

Two jobs:
  1. A LARGE held-out validation set (confirm a hard-tier win isn't 12-task gate-overfit).
  2. Distillation SOURCE tasks: run a frontier teacher over these, keep passing
     trajectories, SFT the small model (see bfcl_multiturn_deepseek.py --dump).

Tasks are deterministic + idempotent (mkdir/cd/touch/mv/cp/rm/rmdir — NEVER echo,
which over-calls + blanks files). Every task's gold is validated as-model via
multi_turn_checker before it is written. IDs use the 8xxxxx range so they never
collide with the fixed 6xxx gate (no train/test contamination on exact instances).

Run: python3 scripts/bfcl/gen_multiturn_trajdata.py [N=300] [seed=0]
Writes scripts/fixtures/multi_turn_hardgen_{data,gold}.jsonl
"""
import json, sys, os, random
sys.path.insert(0, os.path.expanduser(
    "~/.cache/posttrainllm/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard"))
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker

def fs(c): return {"GorillaFileSystem": {"root": {"workspace": {"type": "directory", "contents": c}}}}
def F(t=""): return {"type": "file", "content": t}
def D(c=None): return {"type": "directory", "contents": c or {}}

DIRWORDS = ["src", "docs", "lib", "data", "app", "core", "utils", "tests", "build", "assets",
            "config", "models", "views", "static", "templates", "logs", "tmp", "backup", "archive",
            "raw", "clean", "input", "output", "vendor", "scripts", "bin", "dist", "public"]
FILEWORDS = ["main", "test", "app", "util", "index", "readme", "notes", "config", "setup",
             "run", "log", "data", "report", "draft", "final", "user", "post", "model", "view"]
EXTS = ["py", "txt", "md", "csv", "json", "log", "js", "css"]

def rname(rng, pool, used):
    for _ in range(50):
        n = rng.choice(pool)
        if n not in used:
            used.add(n); return n
    n = rng.choice(pool) + str(rng.randint(1, 99))
    used.add(n); return n

def rfile(rng, used):
    return rname(rng, FILEWORDS, used) + "." + rng.choice(EXTS)

# Each template returns (initial_contents, turns:list[str], ground_truth:list[list[str]]).
def t_deep_nest(rng):
    depth = rng.randint(3, 6); used = set()
    dirs = [rname(rng, DIRWORDS, used) for _ in range(depth)]
    f = rfile(rng, used)
    calls = []
    for d in dirs:
        calls += [f"mkdir(dir_name='{d}')", f"cd(folder='{d}')"]
    calls.append(f"touch(file_name='{f}')")
    chain = "; inside it ".join(f"'{d}'" for d in dirs)
    return {}, [f"Create directory {chain}; and inside the deepest one an empty file '{f}'."], [calls]

def t_many_files(rng):
    n = rng.randint(5, 9); used = set()
    fs_ = [rfile(rng, used) for _ in range(n)]
    return {}, [f"Create empty files {', '.join(repr(x) for x in fs_)}."], \
           [[f"touch(file_name='{x}')" for x in fs_]]

def t_tree_build(rng):
    used = set(); proj = rname(rng, DIRWORDS, used)
    d1 = rname(rng, DIRWORDS, used); d2 = rname(rng, DIRWORDS, used)
    f1 = rfile(rng, used); f2 = rfile(rng, used); f3 = rfile(rng, used)
    turns = [f"Create directory '{proj}' and go in.",
             f"Create directories '{d1}' and '{d2}'.",
             f"Go into '{d1}' and create files '{f1}' and '{f2}'.",
             f"Go up one level, into '{d2}', and create '{f3}'."]
    gt = [[f"mkdir(dir_name='{proj}')", f"cd(folder='{proj}')"],
          [f"mkdir(dir_name='{d1}')", f"mkdir(dir_name='{d2}')"],
          [f"cd(folder='{d1}')", f"touch(file_name='{f1}')", f"touch(file_name='{f2}')"],
          [f"cd(folder='..')", f"cd(folder='{d2}')", f"touch(file_name='{f3}')"]]
    return {}, turns, gt

def t_move_batch(rng):
    n = rng.randint(3, 5); used = set()
    fs_ = [rfile(rng, used) for _ in range(n)]
    arch = rname(rng, DIRWORDS, used)
    init = {x: F(str(i)) for i, x in enumerate(fs_)}
    turns = [f"Create a directory '{arch}'.",
             f"Move {', '.join(repr(x) for x in fs_)} into '{arch}'."]
    gt = [[f"mkdir(dir_name='{arch}')"],
          [f"mv(source='{x}', destination='{arch}')" for x in fs_]]
    return init, turns, gt

def t_nested_with_file(rng):
    used = set(); top = rname(rng, DIRWORDS, used)
    a = rname(rng, DIRWORDS, used); b = rname(rng, DIRWORDS, used); f = rfile(rng, used)
    turns = [f"Create directory '{top}'; go in; create '{a}' and '{b}' directories; "
             f"go into '{a}' and create '{f}'."]
    gt = [[f"mkdir(dir_name='{top}')", f"cd(folder='{top}')", f"mkdir(dir_name='{a}')",
           f"mkdir(dir_name='{b}')", f"cd(folder='{a}')", f"touch(file_name='{f}')"]]
    return {}, turns, gt

def t_per_dir_files(rng):
    used = set(); dirs = [rname(rng, DIRWORDS, used) for _ in range(3)]
    files = [rfile(rng, used) for _ in range(3)]
    turns = [f"Create directories {', '.join(repr(d) for d in dirs)}."]
    gt0 = [f"mkdir(dir_name='{d}')" for d in dirs]
    gt = [gt0]
    for i, (d, f) in enumerate(zip(dirs, files)):
        turns.append(f"Inside '{d}' create '{f}'.")
        step = [f"cd(folder='{d}')", f"touch(file_name='{f}')"] if i == 0 else \
               [f"cd(folder='..')", f"cd(folder='{d}')", f"touch(file_name='{f}')"]
        gt.append(step)
    return {}, turns, gt

def t_copy_then_logs(rng):
    used = set(); fs_ = [rfile(rng, used) for _ in range(rng.randint(2, 3))]
    backup = rname(rng, DIRWORDS, used); logs = rname(rng, DIRWORDS, used); lf = rfile(rng, used)
    init = {x: F(str(i)) for i, x in enumerate(fs_)}
    turns = [f"Create directory '{backup}'; copy {', '.join(repr(x) for x in fs_)} into it; "
             f"then create a directory '{logs}' and an empty file '{lf}' inside '{logs}'."]
    gt = [[f"mkdir(dir_name='{backup}')"] +
          [f"cp(source='{x}', destination='{backup}')" for x in fs_] +
          [f"mkdir(dir_name='{logs}')", f"cd(folder='{logs}')", f"touch(file_name='{lf}')"]]
    return init, turns, gt

def t_move_then_copy(rng):
    used = set(); f1 = rfile(rng, used); f2 = rfile(rng, used)
    final = rname(rng, DIRWORDS, used); cp2 = rfile(rng, used)
    init = {f1: F("a"), f2: F("b")}
    turns = [f"Create directory '{final}'; move both '{f1}' and '{f2}' into '{final}'; "
             f"then go into '{final}' and make a copy of '{f1}' named '{cp2}'."]
    gt = [[f"mkdir(dir_name='{final}')", f"mv(source='{f1}', destination='{final}')",
           f"mv(source='{f2}', destination='{final}')", f"cd(folder='{final}')",
           f"cp(source='{f1}', destination='{cp2}')"]]
    return init, turns, gt

def t_cleanup(rng):
    used = set(); tmp = rname(rng, DIRWORDS, used)
    fs_ = [rfile(rng, used) for _ in range(rng.randint(2, 3))]
    init = {tmp: D({x: F("") for x in fs_})}
    turns = [f"Go into '{tmp}', delete {', '.join(repr(x) for x in fs_)}, "
             f"go back up, and remove the now-empty '{tmp}' directory."]
    gt = [[f"cd(folder='{tmp}')"] + [f"rm(file_name='{x}')" for x in fs_] +
          [f"cd(folder='..')", f"rmdir(dir_name='{tmp}')"]]
    return init, turns, gt

def t_two_versions(rng):
    used = set(); v1 = rname(rng, DIRWORDS, used); v2 = rname(rng, DIRWORDS, used)
    f1 = rfile(rng, used); f2 = rfile(rng, used); f3 = rfile(rng, used)
    turns = [f"Create a directory '{v1}', go in, create files '{f1}' and '{f2}'; "
             f"go up; create '{v2}', go in, create file '{f3}'."]
    gt = [[f"mkdir(dir_name='{v1}')", f"cd(folder='{v1}')", f"touch(file_name='{f1}')",
           f"touch(file_name='{f2}')", f"cd(folder='..')", f"mkdir(dir_name='{v2}')",
           f"cd(folder='{v2}')", f"touch(file_name='{f3}')"]]
    return {}, turns, gt

TEMPLATES = [t_deep_nest, t_many_files, t_tree_build, t_move_batch, t_nested_with_file,
             t_per_dir_files, t_copy_then_logs, t_move_then_copy, t_cleanup, t_two_versions]

# --- veryhard tier: long-horizon (6-8 turns), navigation-heavy, mechanical (no reasoning),
#     so frontier still aces it but the gap to a small model grows with horizon length.
class Builder:
    """Tracks a virtual cwd so multi-turn cd-navigation gold sequences are correct by
    construction. Each method appends the call to the current turn and updates state."""
    def __init__(self): self.turns=[["",[]]]; self.depth=0  # turns: [prompt, [calls]]
    def newturn(self, prompt): self.turns.append([prompt, []])
    def _add(self, call): self.turns[-1][1].append(call)
    def mkdir(self, d): self._add(f"mkdir(dir_name='{d}')")
    def cd(self, d): self._add(f"cd(folder='{d}')"); self.depth+=1
    def up(self): self._add("cd(folder='..')"); self.depth=max(0,self.depth-1)
    def touch(self, f): self._add(f"touch(file_name='{f}')")
    def mv(self, s, d): self._add(f"mv(source='{s}', destination='{d}')")
    def cp(self, s, d): self._add(f"cp(source='{s}', destination='{d}')")
    def rm(self, f): self._add(f"rm(file_name='{f}')")
    def build(self):
        turns=[t for t in self.turns if t[1]]  # drop empty leading turn
        return [t[0] for t in turns], [t[1] for t in turns]

def vt_deep_branch(rng):
    """Build a deep chain, branch at two levels, files at several depths — 6 turns of nav."""
    u=set(); b=Builder()
    a,c,d,e,f = (rname(rng,DIRWORDS,u) for _ in range(5))
    f1,f2,f3,f4 = (rfile(rng,u) for _ in range(4))
    b.newturn(f"Create directory '{a}' and go into it; inside it create '{c}' and go into '{c}'.")
    b.mkdir(a); b.cd(a); b.mkdir(c); b.cd(c)
    b.newturn(f"Create '{d}', go into it, and create file '{f1}'.")
    b.mkdir(d); b.cd(d); b.touch(f1)
    b.newturn(f"Go back up to '{c}', create '{e}', and create file '{f2}'.")
    b.up(); b.mkdir(e); b.touch(f2)
    b.newturn(f"Go into '{e}' and create files '{f3}' and '{f4}'.")
    b.cd(e); b.touch(f3); b.touch(f4)
    gf=rfile(rng,u)
    b.newturn(f"Go all the way back up to '{a}' (two levels) and create a file '{gf}'.")
    b.up(); b.up(); b.touch(gf)
    turns,gt=b.build()
    return {}, turns, gt

def vt_big_project(rng):
    u=set(); b=Builder()
    proj,src,tests,docs = (rname(rng,DIRWORDS,u) for _ in range(4))
    s1,s2,s3,t1,t2,d1 = (rfile(rng,u) for _ in range(6))
    b.newturn(f"Create a project directory '{proj}' and go into it.")
    b.mkdir(proj); b.cd(proj)
    b.newturn(f"Create directories '{src}', '{tests}', and '{docs}'.")
    b.mkdir(src); b.mkdir(tests); b.mkdir(docs)
    b.newturn(f"Go into '{src}' and create files '{s1}', '{s2}', and '{s3}'.")
    b.cd(src); b.touch(s1); b.touch(s2); b.touch(s3)
    b.newturn(f"Go back up, into '{tests}', and create files '{t1}' and '{t2}'.")
    b.up(); b.cd(tests); b.touch(t1); b.touch(t2)
    b.newturn(f"Go back up, into '{docs}', and create '{d1}'.")
    b.up(); b.cd(docs); b.touch(d1)
    turns,gt=b.build()
    return {}, turns, gt

def vt_reorg(rng):
    u=set(); b=Builder()
    files=[rfile(rng,u) for _ in range(5)]
    da,db = rname(rng,DIRWORDS,u), rname(rng,DIRWORDS,u)
    init={x:F(str(i)) for i,x in enumerate(files)}
    b.newturn(f"Create directories '{da}' and '{db}'.")
    b.mkdir(da); b.mkdir(db)
    b.newturn(f"Move '{files[0]}', '{files[1]}', and '{files[2]}' into '{da}'.")
    for x in files[:3]: b.mv(x, da)
    b.newturn(f"Move '{files[3]}' and '{files[4]}' into '{db}'.")
    for x in files[3:]: b.mv(x, db)
    cpn=rfile(rng,u)
    b.newturn(f"Go into '{da}' and make a copy of '{files[0]}' named '{cpn}'.")
    b.cd(da); b.cp(files[0], cpn)
    turns,gt=b.build()
    return init, turns, gt

def vt_build_then_prune(rng):
    u=set(); b=Builder()
    top = rname(rng,DIRWORDS,u); subs=[rname(rng,DIRWORDS,u) for _ in range(3)]
    f1,f2 = rfile(rng,u), rfile(rng,u)
    b.newturn(f"Create directory '{top}' and go in.")
    b.mkdir(top); b.cd(top)
    b.newturn(f"Create directories '{subs[0]}', '{subs[1]}', and '{subs[2]}'.")
    for s in subs: b.mkdir(s)
    b.newturn(f"Go into '{subs[0]}', create files '{f1}' and '{f2}'.")
    b.cd(subs[0]); b.touch(f1); b.touch(f2)
    b.newturn(f"Delete '{f1}'. Then go back up and remove the empty directory '{subs[2]}'.")
    b.rm(f1); b.up(); b._add(f"rmdir(dir_name='{subs[2]}')")
    cpn=rfile(rng,u)
    b.newturn(f"Make a copy of '{f2}' (still inside '{subs[0]}') named '{cpn}'.")
    b.cd(subs[0]); b.cp(f2, cpn)
    turns,gt=b.build()
    return {}, turns, gt

VERYHARD_TEMPLATES = [vt_deep_branch, vt_big_project, vt_reorg, vt_build_then_prune]

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    tier = sys.argv[3] if len(sys.argv) > 3 else "hardgen"
    templates = VERYHARD_TEMPLATES if tier == "veryhard" else TEMPLATES
    rng = random.Random(seed)
    os.makedirs("scripts/fixtures", exist_ok=True)
    data, gold = [], []
    tid = 800000; tried = bad = 0
    while len(data) < N and tried < N * 6:
        tried += 1
        tmpl = templates[tried % len(templates)]
        init, turns, gt = tmpl(rng)
        ex = {"id": f"multi_turn_base_{tid}",
              "question": [[{"role": "user", "content": u}] for u in turns],
              "initial_config": fs(init), "involved_classes": ["GorillaFileSystem"], "path": []}
        g = {"id": ex["id"], "ground_truth": gt}
        # gold-as-model must validate, else the task is malformed — skip it
        ok = multi_turn_checker([[t] for t in gt], gt, ex, "multi_turn_base", "gt").get("valid")
        if not ok:
            bad += 1; continue
        data.append(ex); gold.append(g); tid += 1
    base = f"scripts/fixtures/multi_turn_{tier}"
    open(f"{base}_data.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in data))
    open(f"{base}_gold.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in gold))
    print(f"wrote {len(data)} tasks -> {base}_*.jsonl (rejected {bad} malformed); seed={seed} tier={tier}")

if __name__ == "__main__":
    main()
