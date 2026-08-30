"""Author a DIFFICULTY-GRADED multi-turn agentic gate (single GorillaFileSystem backend,
deterministic state-changing tasks). multi_turn_base is too hard for a 95% gate (frontier
caps ~50-70%); these tiers are right-sized + discriminating. Writes
scripts/fixtures/multi_turn_{easy,moderate,hard}_{data,gold}.jsonl.

Reference (task-completion): 30B-A3B 100/100/83 ; Qwen3-4B-2507 bf16 94/86/58 (easy/mod/hard).
The MODERATE tier is the sound 95% gate (proxy aces, 4B clearly below); HARD maximally
discriminates (true frontier should ~ace it; the 30B-A3B proxy gets 83%).
Run: MT_DATA=scripts/fixtures/multi_turn_moderate_data.jsonl \
     MT_GOLD=scripts/fixtures/multi_turn_moderate_gold.jsonl MODEL=<path> python3 scripts/bfcl/bfcl_multiturn_eval.py 14
"""

import json
import sys
import os

sys.path.insert(
    0,
    os.path.expanduser(
        "~/.cache/posttrainllm/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard"
    ),
)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker


def fs(c):
    return {
        "GorillaFileSystem": {
            "root": {"workspace": {"type": "directory", "contents": c}}
        }
    }


def F(t=""):
    return {"type": "file", "content": t}


def D(c=None):
    return {"type": "directory", "contents": c or {}}


TIERS = {
    "easy": [
        (
            "9001",
            {},
            ["Create a directory named 'reports'."],
            [["mkdir(dir_name='reports')"]],
        ),
        (
            "9002",
            {},
            ["Create an empty file called 'notes.txt'."],
            [["touch(file_name='notes.txt')"]],
        ),
        (
            "9003",
            {"old.txt": F("hi")},
            ["Rename the file 'old.txt' to 'new.txt'."],
            [["mv(source='old.txt', destination='new.txt')"]],
        ),
        (
            "9004",
            {},
            ["Create a directory 'images' and an empty file 'readme.txt'."],
            [["mkdir(dir_name='images')", "touch(file_name='readme.txt')"]],
        ),
        (
            "9005",
            {"temp.txt": F("x")},
            ["Delete the file 'temp.txt'."],
            [["rm(file_name='temp.txt')"]],
        ),
        (
            "9006",
            {"a.txt": F("data")},
            ["Make a copy of 'a.txt' called 'b.txt'."],
            [["cp(source='a.txt', destination='b.txt')"]],
        ),
        (
            "9007",
            {"junk": D()},
            ["Remove the empty directory 'junk'."],
            [["rmdir(dir_name='junk')"]],
        ),
        (
            "9008",
            {},
            ["Create files 'a.txt' and 'b.txt'."],
            [["touch(file_name='a.txt')", "touch(file_name='b.txt')"]],
        ),
        (
            "9009",
            {},
            ["Create a directory 'data', then create an empty file 'x.txt' inside it."],
            [
                [
                    "mkdir(dir_name='data')",
                    "cd(folder='data')",
                    "touch(file_name='x.txt')",
                ]
            ],
        ),
        (
            "9010",
            {},
            [
                "Create a directory called 'logs'.",
                "Now create an empty file 'app.log' inside 'logs'.",
            ],
            [
                ["mkdir(dir_name='logs')"],
                ["cd(folder='logs')", "touch(file_name='app.log')"],
            ],
        ),
        (
            "9011",
            {"draft.txt": F("v1")},
            ["Write 'final version' into 'draft.txt' (overwrite it)."],
            [["echo(content='final version', file_name='draft.txt')"]],
        ),
        (
            "9012",
            {"report.txt": F("q"), "archive": D()},
            ["Move 'report.txt' into the 'archive' directory."],
            [["mv(source='report.txt', destination='archive')"]],
        ),
        (
            "9013",
            {},
            ["Make a directory 'project' and another directory 'docs'."],
            [["mkdir(dir_name='project')", "mkdir(dir_name='docs')"]],
        ),
        (
            "9014",
            {"notes.txt": F("hello")},
            ["Make a copy of 'notes.txt' named 'notes_backup.txt'."],
            [["cp(source='notes.txt', destination='notes_backup.txt')"]],
        ),
        (
            "9015",
            {"a.txt": F("1"), "b.txt": F("2")},
            ["Delete both 'a.txt' and 'b.txt'."],
            [["rm(file_name='a.txt')", "rm(file_name='b.txt')"]],
        ),
        (
            "9016",
            {},
            [
                "Create a directory 'app'.",
                "Inside 'app', create a directory named 'lib'.",
            ],
            [["mkdir(dir_name='app')"], ["cd(folder='app')", "mkdir(dir_name='lib')"]],
        ),
    ],
    "moderate": [
        (
            "7001",
            {},
            [
                "Create a directory 'project', go into it, and create empty files 'main.py' and 'test.py'."
            ],
            [
                [
                    "mkdir(dir_name='project')",
                    "cd(folder='project')",
                    "touch(file_name='main.py')",
                    "touch(file_name='test.py')",
                ]
            ],
        ),
        (
            "7002",
            {},
            [
                "Create directories 'docs' and 'src'.",
                "Go into 'docs' and create an empty file 'readme.md'.",
            ],
            [
                ["mkdir(dir_name='docs')", "mkdir(dir_name='src')"],
                ["cd(folder='docs')", "touch(file_name='readme.md')"],
            ],
        ),
        (
            "7003",
            {"a.txt": F("1")},
            [
                "Create a directory 'backup' and copy 'a.txt' into it, then create an empty file 'b.txt'."
            ],
            [
                [
                    "mkdir(dir_name='backup')",
                    "cp(source='a.txt', destination='backup')",
                    "touch(file_name='b.txt')",
                ]
            ],
        ),
        (
            "7004",
            {},
            [
                "Create a directory 'data', go in, and create files 'jan.csv' and 'feb.csv'."
            ],
            [
                [
                    "mkdir(dir_name='data')",
                    "cd(folder='data')",
                    "touch(file_name='jan.csv')",
                    "touch(file_name='feb.csv')",
                ]
            ],
        ),
        (
            "7005",
            {"report.txt": F("r")},
            [
                "Create a directory 'archive', move 'report.txt' into it, then go into 'archive'."
            ],
            [
                [
                    "mkdir(dir_name='archive')",
                    "mv(source='report.txt', destination='archive')",
                    "cd(folder='archive')",
                ]
            ],
        ),
        (
            "7006",
            {},
            [
                "Create directories 'a' and 'b'.",
                "Go into 'a' and create an empty file 'x.txt'.",
            ],
            [
                ["mkdir(dir_name='a')", "mkdir(dir_name='b')"],
                ["cd(folder='a')", "touch(file_name='x.txt')"],
            ],
        ),
        (
            "7007",
            {"f1.txt": F("a"), "f2.txt": F("b")},
            ["Create a directory 'files' and move both 'f1.txt' and 'f2.txt' into it."],
            [
                [
                    "mkdir(dir_name='files')",
                    "mv(source='f1.txt', destination='files')",
                    "mv(source='f2.txt', destination='files')",
                ]
            ],
        ),
        (
            "7008",
            {},
            [
                "Create a directory 'logs', go in, and create empty files 'app.log' and 'err.log'."
            ],
            [
                [
                    "mkdir(dir_name='logs')",
                    "cd(folder='logs')",
                    "touch(file_name='app.log')",
                    "touch(file_name='err.log')",
                ]
            ],
        ),
        (
            "7009",
            {"notes.txt": F("n")},
            [
                "Create a directory 'saved', copy 'notes.txt' into it, and also make a copy named 'notes2.txt' in the current directory."
            ],
            [
                [
                    "mkdir(dir_name='saved')",
                    "cp(source='notes.txt', destination='saved')",
                    "cp(source='notes.txt', destination='notes2.txt')",
                ]
            ],
        ),
        (
            "7010",
            {},
            [
                "Create a directory 'app'.",
                "Go into 'app' and create directories 'static' and 'templates'.",
            ],
            [
                ["mkdir(dir_name='app')"],
                [
                    "cd(folder='app')",
                    "mkdir(dir_name='static')",
                    "mkdir(dir_name='templates')",
                ],
            ],
        ),
        (
            "7011",
            {"old.txt": F("x"), "keep.txt": F("y")},
            [
                "Delete 'old.txt', then create a directory 'done' and move 'keep.txt' into it."
            ],
            [
                [
                    "rm(file_name='old.txt')",
                    "mkdir(dir_name='done')",
                    "mv(source='keep.txt', destination='done')",
                ]
            ],
        ),
        (
            "7012",
            {},
            [
                "Create files 'a.txt', 'b.txt', and 'c.txt', then create a directory 'all'."
            ],
            [
                [
                    "touch(file_name='a.txt')",
                    "touch(file_name='b.txt')",
                    "touch(file_name='c.txt')",
                    "mkdir(dir_name='all')",
                ]
            ],
        ),
        (
            "7013",
            {"src": D({"app.py": F("c")})},
            ["Go into 'src', make a copy of 'app.py' called 'app_backup.py'."],
            [["cd(folder='src')", "cp(source='app.py', destination='app_backup.py')"]],
        ),
        (
            "7014",
            {},
            [
                "Create a directory 'project'.",
                "Inside 'project' create a directory 'src'.",
                "Inside 'src' create a file 'main.py'.",
            ],
            [
                ["mkdir(dir_name='project')"],
                ["cd(folder='project')", "mkdir(dir_name='src')"],
                ["cd(folder='src')", "touch(file_name='main.py')"],
            ],
        ),
    ],
    "hard": [
        (
            "6001",
            {},
            [
                "Create directory 'l1'; inside it 'l2'; inside that 'l3'; and inside 'l3' an empty file 'deep.txt'."
            ],
            [
                [
                    "mkdir(dir_name='l1')",
                    "cd(folder='l1')",
                    "mkdir(dir_name='l2')",
                    "cd(folder='l2')",
                    "mkdir(dir_name='l3')",
                    "cd(folder='l3')",
                    "touch(file_name='deep.txt')",
                ]
            ],
        ),
        (
            "6002",
            {},
            [
                "Create empty files 'f1.txt','f2.txt','f3.txt','f4.txt','f5.txt','f6.txt'."
            ],
            [
                [
                    "touch(file_name='f1.txt')",
                    "touch(file_name='f2.txt')",
                    "touch(file_name='f3.txt')",
                    "touch(file_name='f4.txt')",
                    "touch(file_name='f5.txt')",
                    "touch(file_name='f6.txt')",
                ]
            ],
        ),
        (
            "6003",
            {},
            [
                "Create directory 'project' and go in.",
                "Create directories 'src' and 'docs'.",
                "Go into 'src' and create files 'a.py' and 'b.py'.",
                "Go up one level, into 'docs', and create 'readme.md'.",
            ],
            [
                ["mkdir(dir_name='project')", "cd(folder='project')"],
                ["mkdir(dir_name='src')", "mkdir(dir_name='docs')"],
                [
                    "cd(folder='src')",
                    "touch(file_name='a.py')",
                    "touch(file_name='b.py')",
                ],
                [
                    "cd(folder='..')",
                    "cd(folder='docs')",
                    "touch(file_name='readme.md')",
                ],
            ],
        ),
        (
            "6004",
            {"d1.txt": F("1"), "d2.txt": F("2"), "d3.txt": F("3")},
            [
                "Create a directory 'archive'.",
                "Move d1.txt, d2.txt and d3.txt into 'archive'.",
            ],
            [
                ["mkdir(dir_name='archive')"],
                [
                    "mv(source='d1.txt', destination='archive')",
                    "mv(source='d2.txt', destination='archive')",
                    "mv(source='d3.txt', destination='archive')",
                ],
            ],
        ),
        (
            "6005",
            {},
            [
                "Create directory 'data'; go in; create 'raw' and 'clean' directories; go into 'raw' and create 'input.csv'."
            ],
            [
                [
                    "mkdir(dir_name='data')",
                    "cd(folder='data')",
                    "mkdir(dir_name='raw')",
                    "mkdir(dir_name='clean')",
                    "cd(folder='raw')",
                    "touch(file_name='input.csv')",
                ]
            ],
        ),
        (
            "6006",
            {},
            [
                "Create directory 'app' and go in.",
                "Create 'static','templates','models' directories.",
                "Go into 'models' and create files 'user.py' and 'post.py'.",
            ],
            [
                ["mkdir(dir_name='app')", "cd(folder='app')"],
                [
                    "mkdir(dir_name='static')",
                    "mkdir(dir_name='templates')",
                    "mkdir(dir_name='models')",
                ],
                [
                    "cd(folder='models')",
                    "touch(file_name='user.py')",
                    "touch(file_name='post.py')",
                ],
            ],
        ),
        (
            "6007",
            {"a.txt": F("a"), "b.txt": F("b")},
            [
                "Create directory 'backup'; copy both a.txt and b.txt into it; then create a directory 'logs' and an empty file 'run.log' inside 'logs'."
            ],
            [
                [
                    "mkdir(dir_name='backup')",
                    "cp(source='a.txt', destination='backup')",
                    "cp(source='b.txt', destination='backup')",
                    "mkdir(dir_name='logs')",
                    "cd(folder='logs')",
                    "touch(file_name='run.log')",
                ]
            ],
        ),
        (
            "6008",
            {},
            [
                "Create directories 'a','b','c'.",
                "Inside 'a' create 'x.txt'.",
                "Inside 'b' create 'y.txt'.",
                "Inside 'c' create 'z.txt'.",
            ],
            [
                ["mkdir(dir_name='a')", "mkdir(dir_name='b')", "mkdir(dir_name='c')"],
                ["cd(folder='a')", "touch(file_name='x.txt')"],
                ["cd(folder='..')", "cd(folder='b')", "touch(file_name='y.txt')"],
                ["cd(folder='..')", "cd(folder='c')", "touch(file_name='z.txt')"],
            ],
        ),
        (
            "6009",
            {},
            [
                "Create a directory 'v1', go in, create files 'm.py' and 'n.py'; go up; create 'v2', go in, create file 'o.py'."
            ],
            [
                [
                    "mkdir(dir_name='v1')",
                    "cd(folder='v1')",
                    "touch(file_name='m.py')",
                    "touch(file_name='n.py')",
                    "cd(folder='..')",
                    "mkdir(dir_name='v2')",
                    "cd(folder='v2')",
                    "touch(file_name='o.py')",
                ]
            ],
        ),
        (
            "6010",
            {"report.txt": F("r"), "data.csv": F("d")},
            [
                "Create directory 'final'; move both report.txt and data.csv into 'final'; then go into 'final' and make a copy of report.txt named 'report_v2.txt'."
            ],
            [
                [
                    "mkdir(dir_name='final')",
                    "mv(source='report.txt', destination='final')",
                    "mv(source='data.csv', destination='final')",
                    "cd(folder='final')",
                    "cp(source='report.txt', destination='report_v2.txt')",
                ]
            ],
        ),
        (
            "6011",
            {},
            [
                "Create directory 'site' and go in.",
                "Create 'css' and 'js' directories.",
                "In 'css' create 'main.css'.",
                "In 'js' create 'app.js' and 'util.js'.",
            ],
            [
                ["mkdir(dir_name='site')", "cd(folder='site')"],
                ["mkdir(dir_name='css')", "mkdir(dir_name='js')"],
                ["cd(folder='css')", "touch(file_name='main.css')"],
                [
                    "cd(folder='..')",
                    "cd(folder='js')",
                    "touch(file_name='app.js')",
                    "touch(file_name='util.js')",
                ],
            ],
        ),
        (
            "6012",
            {"tmp": D({"a.log": F(""), "b.log": F("")})},
            [
                "Go into 'tmp', delete both a.log and b.log, go back up, and remove the now-empty 'tmp' directory."
            ],
            [
                [
                    "cd(folder='tmp')",
                    "rm(file_name='a.log')",
                    "rm(file_name='b.log')",
                    "cd(folder='..')",
                    "rmdir(dir_name='tmp')",
                ]
            ],
        ),
    ],
}
os.makedirs("scripts/fixtures", exist_ok=True)
for tier, T in TIERS.items():
    data = []
    gold = []
    for tid, c, turns, gt in T:
        ex = {
            "id": f"multi_turn_base_{tid}",
            "question": [[{"role": "user", "content": u}] for u in turns],
            "initial_config": fs(c),
            "involved_classes": ["GorillaFileSystem"],
            "path": [],
        }
        data.append(ex)
        gold.append({"id": ex["id"], "ground_truth": gt})
    open(f"scripts/fixtures/multi_turn_{tier}_data.jsonl", "w").write(
        "".join(json.dumps(x) + "\n" for x in data)
    )
    open(f"scripts/fixtures/multi_turn_{tier}_gold.jsonl", "w").write(
        "".join(json.dumps(x) + "\n" for x in gold)
    )
    bad = [
        ex["id"]
        for ex, g in zip(data, gold)
        if not multi_turn_checker(
            [[t] for t in g["ground_truth"]],
            g["ground_truth"],
            ex,
            "multi_turn_base",
            "gt",
        ).get("valid")
    ]
    print(f"{tier}: {len(data)} tasks; gold-as-model invalid: {bad or 'none'}")
