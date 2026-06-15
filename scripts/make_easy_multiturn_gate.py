"""Author an EASY multi-turn agentic gate (single GorillaFileSystem backend, trivial
deterministic state-changing tasks) where a strong model aces ~95-100% — a SOUND
frontier-ceiling gate for multi-turn (multi_turn_base is too hard, frontier caps ~50-70%).
Writes scripts/fixtures/multi_turn_easy_{data,gold}.jsonl. Run via:
  MT_DATA=scripts/fixtures/multi_turn_easy_data.jsonl \\
  MT_GOLD=scripts/fixtures/multi_turn_easy_gold.jsonl MODEL=<path> python3 scripts/bfcl_multiturn_eval.py 16
Reference: 30B-A3B 16/16=100%, Qwen3-4B-2507 bf16 15/16=93.8%."""
import json
def fs(c): return {"GorillaFileSystem":{"root":{"workspace":{"type":"directory","contents":c}}}}
def F(t=""): return {"type":"file","content":t}
def D(c=None): return {"type":"directory","contents":c or {}}
T = [
 ("9001", {}, ["Create a directory named 'reports'."], [["mkdir(dir_name='reports')"]]),
 ("9002", {}, ["Create an empty file called 'notes.txt'."], [["touch(file_name='notes.txt')"]]),
 ("9003", {"old.txt":F("hi")}, ["Rename the file 'old.txt' to 'new.txt'."], [["mv(source='old.txt', destination='new.txt')"]]),
 ("9004", {}, ["Create a directory 'images' and an empty file 'readme.txt'."], [["mkdir(dir_name='images')","touch(file_name='readme.txt')"]]),
 ("9005", {"temp.txt":F("x")}, ["Delete the file 'temp.txt'."], [["rm(file_name='temp.txt')"]]),
 ("9006", {"a.txt":F("data")}, ["Make a copy of 'a.txt' called 'b.txt'."], [["cp(source='a.txt', destination='b.txt')"]]),
 ("9007", {"junk":D()}, ["Remove the empty directory 'junk'."], [["rmdir(dir_name='junk')"]]),
 ("9008", {}, ["Create files 'a.txt' and 'b.txt'."], [["touch(file_name='a.txt')","touch(file_name='b.txt')"]]),
 ("9009", {}, ["Create a directory 'data', then create an empty file 'x.txt' inside it."],
   [["mkdir(dir_name='data')","cd(folder='data')","touch(file_name='x.txt')"]]),
 ("9010", {}, ["Create a directory called 'logs'.","Now create an empty file 'app.log' inside 'logs'."],
   [["mkdir(dir_name='logs')"],["cd(folder='logs')","touch(file_name='app.log')"]]),
 ("9011", {"draft.txt":F("v1")}, ["Write 'final version' into 'draft.txt' (overwrite it)."], [["echo(content='final version', file_name='draft.txt')"]]),
 ("9012", {"report.txt":F("q"), "archive":D()}, ["Move 'report.txt' into the 'archive' directory."], [["mv(source='report.txt', destination='archive')"]]),
 ("9013", {}, ["Make a directory 'project' and another directory 'docs'."], [["mkdir(dir_name='project')","mkdir(dir_name='docs')"]]),
 ("9014", {"notes.txt":F("hello")}, ["Make a copy of 'notes.txt' named 'notes_backup.txt'."], [["cp(source='notes.txt', destination='notes_backup.txt')"]]),
 ("9015", {"a.txt":F("1"),"b.txt":F("2")}, ["Delete both 'a.txt' and 'b.txt'."], [["rm(file_name='a.txt')","rm(file_name='b.txt')"]]),
 ("9016", {}, ["Create a directory 'app'.","Inside 'app', create a directory named 'lib'."],
   [["mkdir(dir_name='app')"],["cd(folder='app')","mkdir(dir_name='lib')"]]),
]
data=[]; gold=[]
for tid,c,turns,gt in T:
    ex={"id":f"multi_turn_base_{tid}","question":[[{"role":"user","content":u}] for u in turns],
        "initial_config":fs(c),"involved_classes":["GorillaFileSystem"],"path":[]}
    data.append(ex); gold.append({"id":ex["id"],"ground_truth":gt})
open("scripts/fixtures/multi_turn_easy_data.jsonl","w").write("".join(json.dumps(x)+"\n" for x in data))
open("scripts/fixtures/multi_turn_easy_gold.jsonl","w").write("".join(json.dumps(x)+"\n" for x in gold))
# self-check: gold-as-model all valid
import sys; sys.path.insert(0,"/Users/sarthak/.cache/tinygpt/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard")
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker
bad=[ex["id"] for ex,g in zip(data,gold) if not multi_turn_checker([[t] for t in g["ground_truth"]],g["ground_truth"],ex,"multi_turn_base","gt").get("valid")]
print(f"authored {len(data)} tasks; gold-as-model invalid: {bad or 'none'}")
