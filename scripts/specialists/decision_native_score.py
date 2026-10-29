"""Score exact native option logits with observed artifact and prompt identities.

Contract: docs/factory/specialist-labs.md. The source revision is declared by
the operator; a binary checksum does not prove which source built that binary.
"""

from __future__ import annotations

import json
import importlib.metadata
import math
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from common import Budget, digest, file_hash, read_json
from decision import identity, option_ids, prompt, validate_item
from decision_native import base_files


class NativeDecisionModel:
    def __init__(
        self, binary, base, source_revision, adapter=None, budget=None, tokenizer=None
    ):
        self.binary, self.base = Path(binary).resolve(), Path(base).resolve()
        self.adapter = Path(adapter).resolve() if adapter else None
        self.budget = budget or Budget()
        if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
            raise ValueError("native source revision must be a declared full commit")
        if not self.binary.is_file() or not os.access(self.binary, os.X_OK):
            raise ValueError("native binary must be an existing executable file")
        self.training_identities = set()
        self.artifacts = self.snapshot()
        self.fingerprints = self.file_fingerprints()
        if (self.base / "specialist.json").exists():
            self.read_training_identities(read_json(self.base / "specialist.json"))
        self.check_adapter()
        if tokenizer is None:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                str(self.base), local_files_only=True, trust_remote_code=False
            )
        self.tokenizer = tokenizer
        tokenizer_versions = {}
        for package in ("transformers", "tokenizers", "jinja2", "markupsafe"):
            try:
                tokenizer_versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                tokenizer_versions[package] = None
        self.runtime_identity = {
            "backend": "native-exact-token-logits-v1",
            "source_revision_declared": source_revision,
            "artifacts_observed": self.artifacts,
            "scorer_sha256": file_hash(__file__),
            "prompt_implementation_sha256": file_hash(
                Path(__file__).with_name("decision.py")
            ),
            "tokenizer_runtime": tokenizer_versions,
            "tokenizer_class": type(tokenizer).__module__
            + "."
            + type(tokenizer).__qualname__,
            "resolved_chat_template_sha256": digest(
                getattr(tokenizer, "chat_template", None)
            ),
        }
        self.model_identity = digest(self.runtime_identity)

    def snapshot(self):
        files = base_files(self.base)
        if "config.json" not in files or not any(
            name.endswith(".safetensors") for name in files
        ):
            raise ValueError("native base requires config and local model weights")
        resources = self.native_resources()
        if not any(path.suffix == ".metallib" for path in resources.values()):
            raise ValueError(
                "native Metal kernel resources unavailable; retain the CLI's Metal library"
            )
        result = {
            "binary_sha256": file_hash(self.binary),
            "base_files": files,
            "tokenizer_files": {
                str(path.relative_to(self.base)): file_hash(path)
                for path in self.tokenizer_files()
            },
            "native_resources": {
                name: file_hash(path) for name, path in resources.items()
            },
        }
        if self.adapter:
            result["adapter_sha256"] = file_hash(self.adapter)
            result["adapter_provenance_sha256"] = file_hash(str(self.adapter) + ".json")
        return result

    def native_resources(self):
        roots = {"binary": self.binary.parent}
        if (
            self.binary.parent.name == "MacOS"
            and self.binary.parent.parent.name == "Contents"
        ):
            roots["app-resources"] = self.binary.parent.parent / "Resources"
            roots["app-frameworks"] = self.binary.parent.parent / "Frameworks"
        resources = {}
        for name, root in roots.items():
            paths = set(root.glob("*.metallib")) | set(root.glob("*.dylib"))
            for bundle in list(root.glob("*.bundle")) + list(root.glob("*.framework")):
                paths.update(path for path in bundle.rglob("*") if path.is_file())
            resources.update(
                {
                    name + "/" + str(path.relative_to(root)): path
                    for path in sorted(paths)
                    if path.is_file()
                }
            )
        return resources

    def tokenizer_files(self):
        return sorted(
            {
                path
                for path in self.base.iterdir()
                if path.is_file()
                and path.suffix in (".jinja", ".txt", ".model", ".tiktoken")
            }
            | set((self.base / "chat_templates").glob("*.jinja"))
        )

    def file_fingerprints(self):
        paths = {"binary": self.binary}
        paths.update(
            {
                "base/" + path.name: path
                for path in self.base.iterdir()
                if path.is_file() and path.suffix in (".json", ".safetensors")
            }
        )
        paths.update(
            {"native/" + name: path for name, path in self.native_resources().items()}
        )
        paths.update(
            {
                "base/" + str(path.relative_to(self.base)): path
                for path in self.tokenizer_files()
            }
        )
        if self.adapter:
            paths.update(
                {
                    "adapter": self.adapter,
                    "adapter_provenance": Path(str(self.adapter) + ".json"),
                }
            )
        result = {}
        for name, path in paths.items():
            status = path.stat()
            result[name] = (
                status.st_dev,
                status.st_ino,
                status.st_size,
                status.st_mtime_ns,
                status.st_ctime_ns,
            )
        return result

    def check_adapter(self):
        if not self.adapter:
            return
        metadata = read_json(str(self.adapter) + ".json")
        if (
            metadata.get("schema") != "decision-native-adapter-v1"
            or metadata.get("base_files") != self.artifacts["base_files"]
            or metadata.get("native_adapter_sha256") != self.artifacts["adapter_sha256"]
        ):
            raise ValueError("native adapter/base provenance mismatch")
        self.read_training_identities(metadata)

    def read_training_identities(self, metadata):
        identities = metadata.get("train_identities")
        if (
            not isinstance(identities, list)
            or not identities
            or any(
                not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                for value in identities
            )
            or len(set(identities)) != len(identities)
        ):
            raise ValueError(
                "native training provenance missing or invalid; source must record original training identities"
            )
        self.training_identities.update(identities)

    def unchanged(self):
        self.budget.check()
        if self.file_fingerprints() != self.fingerprints:
            raise ValueError("native scoring artifacts changed; discard this score run")
        self.budget.check()

    def finish(self):
        self.unchanged()
        if self.snapshot() != self.artifacts:
            raise ValueError("native scoring artifacts changed; discard this score run")
        self.budget.check()

    def prepare(self, item):
        labels = validate_item(item)
        ids = option_ids(labels, self.tokenizer)
        tokens = self.tokenizer.encode(
            prompt(item, self.tokenizer), add_special_tokens=False
        )
        maximum = min(
            256, read_json(self.base / "config.json")["max_position_embeddings"]
        )
        if (
            not tokens
            or len(tokens) > maximum
            or any(type(token) is not int or token < 0 for token in tokens + ids)
        ):
            raise ValueError(
                "native prompt requires bounded exact token ids; no truncation"
            )
        return labels, ids, tokens

    def preflight(self, rows):
        self.unchanged()
        for item in rows:
            self.prepare(item)
            self.budget.check()

    def score(self, item):
        self.unchanged()
        labels, ids, tokens = self.prepare(item)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="posttrain-native-probe-") as directory:
            probe = Path(directory) / "probe.json"
            probe.write_text(json.dumps({"tokens": tokens, "labels": ids}))
            command = [
                str(self.binary),
                "debug-logits",
                "--hf",
                str(self.base),
                "--probe",
                str(probe),
            ]
            if self.adapter:
                command += ["--lora", str(self.adapter)]
            remaining = self.budget.seconds - (time.monotonic() - self.budget.started)
            if remaining <= 0:
                raise TimeoutError("specialist work budget exhausted")
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=remaining,
                    check=True,
                )
            except subprocess.CalledProcessError as error:
                raise ValueError(
                    f"native exact-token probe failed ({error.returncode}): {error.stderr.strip()[-1000:]}"
                ) from None
        self.unchanged()
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise ValueError("native exact-token response does not match the request")
        logits = value.get("logits")
        if (
            value.get("schema") != "native-exact-token-logits-v1"
            or value.get("tokens") != len(tokens)
            or value.get("labels") != ids
            or not isinstance(logits, list)
            or len(logits) != len(labels)
            or any(
                type(number) not in (int, float) or not math.isfinite(number)
                for number in logits
            )
        ):
            raise ValueError("native exact-token response does not match the request")
        return {
            "id": item.get("id", identity(item)),
            "identity": identity(item),
            "labels": labels,
            "logits": logits,
            "model_identity": self.model_identity,
            "runtime_identity": self.runtime_identity,
            "answer": item.get("answer"),
            "prompt_tokens": len(tokens),
            "probe_sha256": digest({"tokens": tokens, "labels": ids}),
            "seen_in_training": identity(item) in self.training_identities,
            "elapsed_seconds": time.monotonic() - started,
        }
