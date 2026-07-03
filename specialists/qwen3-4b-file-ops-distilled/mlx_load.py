#!/usr/bin/env python3
"""Load or validate the qwen3-4b-file-ops-distilled specialist package.

Default mode is metadata-only so package checks stay cheap. Pass --load to
materialize the multi-GB safetensor shards with MLX.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def expand(path: str) -> Path:
    return Path(path).expanduser().resolve()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(lock: dict, root: Path, verify_hashes: bool) -> list[str]:
    errors: list[str] = []
    for entry in lock["files"]:
        path = root / entry["path"]
        if not path.exists():
            errors.append(f"missing: {entry['path']}")
            continue
        if path.stat().st_size != entry["bytes"]:
            errors.append(
                f"size mismatch: {entry['path']} expected {entry['bytes']} got {path.stat().st_size}"
            )
        if verify_hashes and "sha256" in entry:
            got = sha256(path)
            if got != entry["sha256"]:
                errors.append(f"sha256 mismatch: {entry['path']} expected {entry['sha256']} got {got}")
    return errors


def load_arrays(root: Path) -> dict:
    import mlx.core as mx

    arrays = {}
    for shard in sorted(root.glob("*.safetensors")):
        arrays.update(mx.load(str(shard)))
    return arrays


def main() -> None:
    package_dir = Path(__file__).resolve().parent
    lock = json.loads((package_dir / "tinygpt.lock.json").read_text())

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact",
        default=lock.get("local_path"),
        help="Local HF/MLX artifact directory to validate or load.",
    )
    parser.add_argument("--verify-hashes", action="store_true", help="hash-check large weight shards")
    parser.add_argument("--load", action="store_true", help="load all safetensor arrays with MLX")
    args = parser.parse_args()

    if not args.artifact:
        repo_id = lock["storage"]["repo_id"]
        raise SystemExit(
            "no local artifact path recorded; download or cache the model first, "
            f"for example: hf download {repo_id} --local-dir <artifact-dir>"
        )

    root = expand(args.artifact)
    errors = validate(lock, root, verify_hashes=args.verify_hashes)
    if errors:
        raise SystemExit("\n".join(errors))

    result = {
        "id": lock["id"],
        "artifact": str(root),
        "files": len(lock["files"]),
        "loadable": True,
    }
    if args.load:
        arrays = load_arrays(root)
        result["tensor_count"] = len(arrays)
        result["sample_keys"] = list(arrays.keys())[:8]

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
