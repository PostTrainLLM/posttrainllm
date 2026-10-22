"""Freeze issue #200's original synthetic-document pilot before model execution.

These invented engineering records test contextual grounding, not world knowledge.
Train/dev/test documents and their opaque factual values are disjoint.
"""

import hashlib
import importlib.metadata
import json
import random
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/2026-10-22-grounding-200-v1"
SYSTEM = (
    "Answer using only the supplied record. If it does not establish the answer, "
    "respond exactly ABSTAIN. Otherwise return only the answer, without explanation."
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def messages(row, answer=None):
    result = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": row["prompt"]},
    ]
    if answer is not None:
        result.append({"role": "assistant", "content": answer})
    return result


def document_rows(rng, fields, split, count):
    rows = []
    for i in range(count):
        doc = f"{split}-record-{i:03d}"
        field = fields[i % len(fields)]
        value = f"{split[0].upper()}{rng.randrange(100000, 999999)}"
        unrelated = f"N{rng.randrange(100000, 999999)}"
        preface = (
            f"Engineering record {doc}. The unit passed its vibration check. "
            f"The batch reference is {unrelated}. The operator logged a routine review."
        )
        sentence = f" Its {field} is {value}."
        question = f"What is the {field} for the unit in {doc}?"
        for present in [True, False]:
            context = preface + (sentence if present else "")
            rows.append(
                {
                    "id": f"{doc}-{'present' if present else 'absent'}",
                    "document": doc,
                    "split": split,
                    "slice": field,
                    "present": present,
                    "answer": value if present else "ABSTAIN",
                    "prompt": f"Record: {context}\nQuestion: {question}",
                }
            )
    return rows


def write_training(rows, split):
    for candidate in ["ordinary", "perturbation"]:
        training = []
        for row in rows:
            prompt_row = row.copy()
            if candidate == "ordinary" and not row["present"]:
                prompt_row["prompt"] = (
                    "Record: [no record supplied]\n" + row["prompt"].split("\n")[-1]
                )
            training.append({"messages": messages(prompt_row, row["answer"])})
        jsonl(
            OUT / candidate / ("valid.jsonl" if split == "dev" else f"{split}.jsonl"),
            training,
        )


def write_regression():
    regression = [
        ("How many sides does a triangle have?", "3"),
        ("What is 8 plus 7?", "15"),
        ("What is the chemical symbol for oxygen?", "O"),
        ("What is 9 multiplied by 6?", "54"),
        ("How many centimeters are in one meter?", "100"),
        ("What is the chemical symbol for gold?", "Au"),
        ("What is 81 divided by 9?", "9"),
        ("What is the binary representation of decimal 5?", "101"),
        ("What is 12 squared?", "144"),
        ("What is the chemical symbol for helium?", "He"),
        ("How many minutes are in two hours?", "120"),
        ("What is 100 minus 37?", "63"),
    ]
    jsonl(
        OUT / "regression.jsonl",
        [
            {"id": f"regression-{i}", "prompt": q, "answer": a}
            for i, (q, a) in enumerate(regression)
        ],
    )


def frozen_contract(hashes):
    return {
        "schema_version": "posttrainllm.grounding-pilot.v1",
        "issue": 200,
        "seed": 20020261022,
        "system": SYSTEM,
        "source": "Original synthetic engineering documents; not real safety instructions or owner data.",
        "limitations": "Small controlled opaque-fact pilot, not a claim about broad factual grounding.",
        "model": "mlx-community/Qwen3-1.7B-4bit",
        "revision": "3b1b1768f8f8cf8351c712464f906e86c2b8269e",
        "runtime": {
            p: importlib.metadata.version(p)
            for p in ["mlx-lm", "mlx", "transformers", "tokenizers"]
        },
        "counts": {
            "train_documents": 48,
            "dev_documents": 12,
            "test_documents": 20,
            "paired_examples": 160,
            "regression": 12,
        },
        "decode": {"temperature": 0, "max_tokens": 24, "enable_thinking": False},
        "adapter": {
            "rank": 4,
            "scale": 8,
            "dropout": 0,
            "layers": 4,
            "batch_size": 1,
            "iterations": 100,
            "learning_rate": 0.0001,
            "max_seq_length": 384,
            "mask_prompt": True,
            "seed": 20020261022,
        },
        "caps": {
            "model_compute_seconds": 3600,
            "peak_process_gib": 16,
            "paid_usd": 0,
            "trained_candidates": 2,
            "preparation_hours": 4,
        },
        "acceptance": {
            "unsupported_rate_improvement_pp": 10,
            "must_beat_ordinary": True,
            "maximum_regression_pp": 2,
            "paired_bootstrap_seed": 200,
            "paired_bootstrap_samples": 10000,
        },
        "stop": "Reject/inconclusive if baseline unsupported rate is below 10%; no training can clear the frozen gain.",
        "bfcl": "Required for retention; use existing calibrated subset. If unavailable, explicitly skip and prohibit retention.",
        "files_sha256": hashes,
    }


def validate_rows(rows):
    groups = {
        split: [row for row in rows if row["split"] == split]
        for split in ["train", "dev", "test"]
    }
    values = {
        split: {row["answer"] for row in group if row["present"]}
        for split, group in groups.items()
    }
    documents = {
        split: {row["document"] for row in group} for split, group in groups.items()
    }
    for left, right in combinations(groups, 2):
        assert values[left].isdisjoint(values[right])
        assert documents[left].isdisjoint(documents[right])
    paired = {row["document"]: row["answer"] for row in rows if row["present"]}
    assert all(
        paired[row["document"]] not in row["prompt"]
        for row in rows
        if not row["present"]
    )
    return {
        "source_documents_disjoint": True,
        "actual_target_values_disjoint": True,
        "decisive_values_absent_from_perturbed_contexts": True,
        "value_prefixes": {
            split: sorted({value[0] for value in targets})
            for split, targets in values.items()
        },
        "limitation": "TRAIN and TEST values share T prefix; this is a source-document/value split, not a prefix split.",
    }


def prepare():
    if (OUT / "contract.json").exists():
        raise SystemExit("Frozen contract already exists; do not overwrite a run.")
    rng = random.Random(20020261022)
    fields = ["release code", "storage bay", "calibration token", "inspection label"]
    all_rows = []
    for split, count in [("train", 48), ("dev", 12), ("test", 20)]:
        rows = document_rows(rng, fields, split, count)
        jsonl(OUT / f"{split}.jsonl", rows)
        all_rows.extend(rows)
        if split != "test":
            write_training(rows, split)
    for split in ["train", "dev", "test"]:
        values = {r["answer"] for r in all_rows if r["split"] == split and r["present"]}
        assert len(values) == {"train": 48, "dev": 12, "test": 20}[split]
    validate_rows(all_rows)
    write_regression()
    hashes = {
        str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(OUT.rglob("*.jsonl"))
    }
    contract = frozen_contract(hashes)
    write(OUT / "contract.json", contract)
    write(
        OUT / "runtime-lock.json",
        {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
    )
    print(
        json.dumps(
            {
                "contract_sha256": hashlib.sha256(
                    (OUT / "contract.json").read_bytes()
                ).hexdigest(),
                "counts": contract["counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    prepare()
