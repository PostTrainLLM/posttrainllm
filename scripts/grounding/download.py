"""Acquire only public pinned weights/tokenizer files, without stored HF credentials."""

import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

from prepare import OUT, write


def download():
    contract = json.loads((OUT / "contract.json").read_text())
    model = Path(
        snapshot_download(
            repo_id=contract["model"],
            revision=contract["revision"],
            token=False,
            allow_patterns=["*.json", "*.safetensors", "*.model", "*.jinja", "*.txt"],
        )
    )
    files = {
        str(p.relative_to(model)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(model.rglob("*"))
        if p.is_file()
    }
    write(
        OUT / "model-source.json",
        {
            "model": contract["model"],
            "revision": contract["revision"],
            "local_path": str(model),
            "files_sha256": files,
        },
    )
    print(json.dumps({"path": str(model), "file_count": len(files)}, indent=2))


if __name__ == "__main__":
    download()
