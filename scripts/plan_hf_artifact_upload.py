#!/usr/bin/env python3
"""Stage a TinyGPT artifact for Hugging Face Hub upload.

This script does not require an HF token and does not upload by itself. It
creates the small public metadata surface that should go to the Hub first, then
prints the exact `hf upload` command to run after login.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE_ROOT = ROOT / "dist" / "hf-artifacts"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_if_present(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    shutil.copy2(src, dst)
    return True


def public_lock(lock: dict[str, Any], repo_id: str) -> dict[str, Any]:
    sanitized = dict(lock)
    if "local_path" in sanitized:
        sanitized["local_path"] = None
    sanitized["public_uri"] = f"hf://models/{repo_id}"
    return sanitized


def package_id(package_dir: Path) -> str:
    lock = package_dir / "tinygpt.lock.json"
    if lock.exists():
        return str(read_json(lock)["id"])
    return package_dir.name


def stage_package(package_dir: Path, repo_id: str, out_dir: Path, include_weights: bool) -> None:
    package_dir = package_dir.resolve()
    if not package_dir.exists():
        raise SystemExit(f"package not found: {package_dir}")

    lock_path = package_dir / "tinygpt.lock.json"
    lock = read_json(lock_path)
    artifact_id = str(lock.get("id") or package_dir.name)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": package_dir / "model_card.md",
        "prompt.md": package_dir / "prompt.md",
        "eval_report.json": package_dir / "eval_report.json",
    }
    copied: list[str] = []
    for dst_name, src in files.items():
        if copy_if_present(src, out_dir / dst_name):
            copied.append(dst_name)
    write_json(out_dir / "tinygpt.lock.json", public_lock(lock, repo_id))
    copied.append("tinygpt.lock.json")

    manifest = {
        "schema": "tinygpt.hf_artifact_manifest.v1",
        "artifact_id": artifact_id,
        "repo_id": repo_id,
        "repo_type": "model",
        "storage_provider": "huggingface_hub",
        "package_dir": str(package_dir.relative_to(ROOT)),
        "metadata_files": copied,
        "large_weights_included": include_weights,
        "large_weight_policy": (
            "included in this staged directory"
            if include_weights
            else "not staged by default; upload only after ship decision and size review"
        ),
        "source_lock": "tinygpt.lock.json",
    }

    if include_weights:
        local_path = Path(str(lock["local_path"])).expanduser()
        if not local_path.exists():
            raise SystemExit(f"local artifact path missing: {local_path}")
        weights_dir = out_dir / "weights"
        weights_dir.mkdir(exist_ok=True)
        for entry in lock.get("files", []):
            src = local_path / entry["path"]
            if not src.exists():
                raise SystemExit(f"missing weight file: {src}")
            dst = weights_dir / entry["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    write_json(out_dir / "artifact_manifest.json", manifest)

    print(f"staged {artifact_id} for HF Hub: {out_dir}")
    print()
    print("Next commands:")
    print("  hf auth login")
    print(f"  hf repos create {repo_id} --repo-type model --public --exist-ok")
    print(f"  hf upload {repo_id} {out_dir} . --repo-type model")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("package", help="Specialist package directory, e.g. specialists/qwen3-4b-file-ops-distilled")
    ap.add_argument("--repo-id", help="HF repo id, e.g. <namespace>/<artifact-id>")
    ap.add_argument("--out", help="Staging output directory")
    ap.add_argument(
        "--include-weights",
        action="store_true",
        help="Also copy large local weight files into the staging directory. Off by default.",
    )
    args = ap.parse_args()

    package_dir = (ROOT / args.package).resolve()
    artifact_id = package_id(package_dir)
    repo_id = args.repo_id or f"<hf-namespace>/{artifact_id}"
    out_dir = Path(args.out) if args.out else DEFAULT_STAGE_ROOT / artifact_id
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    if out_dir.exists():
        shutil.rmtree(out_dir)
    stage_package(package_dir, repo_id, out_dir, args.include_weights)


if __name__ == "__main__":
    main()
