#!/usr/bin/env python3
"""Fail closed when the closed learning lab has an unresolved coverage gap."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINAL_STATUSES = {
    "worked",
    "worked-with-caveat",
    "failed",
    "regressed",
    "inconclusive",
    "superseded",
    "rejected",
    "blocked",
}
RECIPE_STATUSES = {
    "validated-with-caveat",
    "reference-only",
    "closed-lineage",
    "closed-experiment",
    "rejected",
}
CLI_CATALOG = ROOT / "native-mac/Sources/TinyGPT/CLICommandCatalog.swift"
ARTIFACT_ACTIONS = ("build", "modify", "tune", "evaluate", "package")
PUBLIC_CONTRACTS = {
    "browser/src/pages/experiments.astro": [
        "../../../docs/attempts.json",
        'href="/recipes"',
        'href="/learn"',
        'aria-pressed="false"',
        "experimentRecipeHref(attempt)",
        "experimentLearningHref(attempt)",
    ],
    "browser/src/pages/recipes.astro": [
        "../../../docs/recipes/registry.json",
        "completeRecipes",
        "Mastery",
    ],
    "browser/src/pages/learn.astro": [
        "../../../docs/learn/path-registry.json",
        "../../../docs/learn/artifact-journey.json",
        "learningPaths",
        "artifactStages",
        "artifact-actions",
        "Build",
        "Modify",
        "Tune",
        "Prove",
        "Package",
        "Mastery gate",
        "path.cli_commands",
        "path.recipes.map",
        "path.anchors.map",
        "path-${path.id}",
    ],
    "browser/src/components/SiteHeader.astro": [
        '{ href: "/playground", label: "Web Lab"',
        '{ href: "/experiments", label: "Experiments"',
        '{ href: "/recipes", label: "Reproducible recipes"',
        '{ href: "/learn", label: "Learn"',
        '{ href: "/docs/cli-reference", label: "CLI reference"',
        "const isCurrent =",
        '<details class="sh-menu">',
        "@media (max-width: 620px)",
    ],
    "docs/cli-reference.md": [
        "posttrainllm commands --json",
        "evals/cli-surface-smoke.sh",
        "## Exit-code contract",
    ],
    ".github/workflows/ci.yml": [
        "Verify CLI discovery contract",
        "Run project completion smoke test",
        "Unit tests with coverage ratchet (vitest)",
        "Production build (copy_docs + tsc + astro build)",
    ],
    "browser/package.json": ["node scripts/check-built-links.mjs"],
    "browser/scripts/check-built-links.mjs": [
        "BROKEN LINK:",
        "has no matching fragment target",
    ],
    "docs/techniques/needle2-baseline-review.md": [
        "## Task-specific catalog ablation",
        "36/94",
    ],
    "docs/techniques/parakeet-wgsl-browser-smoke.md": [
        "## Result",
        "## Decision",
    ],
}


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def local_path_exists(value: str) -> bool:
    path = value.split("#", 1)[0]
    if path.startswith(("http://", "https://", "/")):
        return True
    return (ROOT / path).exists()


def validate_attempts(payload: dict, errors: list[str]) -> list[dict]:
    attempts = payload.get("attempts") or []
    if payload.get("schema_version") != 3:
        errors.append("docs/attempts.json must use closure schema v3")
    if not attempts:
        errors.append("experiment ledger is empty")
    seen_attempts: set[str] = set()
    for attempt in attempts:
        attempt_id = attempt.get("id")
        if not attempt_id or attempt_id in seen_attempts:
            errors.append(f"missing or duplicate attempt id: {attempt_id!r}")
        seen_attempts.add(attempt_id)
        status = attempt.get("status")
        if status not in FINAL_STATUSES:
            errors.append(f"{attempt_id}: unresolved or invalid status {status!r}")
        for field in (
            "name",
            "family",
            "evidence",
            "failure_reason_confidence",
            "lesson",
            "next_action",
            "source",
        ):
            if not attempt.get(field):
                errors.append(f"{attempt_id}: missing {field}")
        sources = attempt.get("evidence_sources") or []
        if not sources:
            errors.append(f"{attempt_id}: missing evidence_sources")
        for source in sources:
            if not local_path_exists(source):
                errors.append(f"{attempt_id}: missing evidence source {source}")
    return attempts


def validate_recipes(payload: dict, errors: list[str]) -> list[dict]:
    required_recipe_fields = set(payload.get("required_fields") or [])
    recipes = payload.get("recipes") or []
    recipe_ids: set[str] = set()
    technique_coverage = set(payload.get("governance_docs") or [])
    for recipe in recipes:
        validate_recipe(
            recipe, required_recipe_fields, recipe_ids, technique_coverage, errors
        )

    technique_files = {
        str(path.relative_to(ROOT)) for path in (ROOT / "docs/techniques").glob("*.md")
    }
    missing_techniques = sorted(technique_files - technique_coverage)
    extra_techniques = sorted(technique_coverage - technique_files)
    if missing_techniques:
        errors.append(
            f"technique files without recipe/disposition: {missing_techniques}"
        )
    if extra_techniques:
        errors.append(
            f"recipe registry references missing techniques: {extra_techniques}"
        )
    return recipes


def validate_recipe(
    recipe: dict,
    required_fields: set[str],
    recipe_ids: set[str],
    technique_coverage: set[str],
    errors: list[str],
) -> None:
    recipe_id = recipe.get("id")
    if not recipe_id or recipe_id in recipe_ids:
        errors.append(f"missing or duplicate recipe id: {recipe_id!r}")
    recipe_ids.add(recipe_id)
    missing = sorted(field for field in required_fields if not recipe.get(field))
    if missing:
        errors.append(f"{recipe_id}: missing recipe fields {missing}")
    if recipe.get("status") not in RECIPE_STATUSES:
        errors.append(f"{recipe_id}: invalid recipe status {recipe.get('status')!r}")
    technique_path = recipe.get("technique_path")
    if technique_path:
        technique_coverage.add(technique_path)
        if not (ROOT / technique_path).is_file():
            errors.append(f"{recipe_id}: missing technique path {technique_path}")
    for evidence in recipe.get("evidence") or []:
        if not local_path_exists(evidence):
            errors.append(f"{recipe_id}: missing recipe evidence {evidence}")


def cli_catalog_names() -> set[str]:
    source = CLI_CATALOG.read_text(encoding="utf-8").split(
        "static func runDiscoveryIfRequested", 1
    )[0]
    return set(re.findall(r'Command\("([^\"]+)"', source))


def validate_learning(
    payload: dict,
    recipes: list[dict],
    command_names: set[str],
    errors: list[str],
) -> list[dict]:
    paths = payload.get("paths") or []
    path_ids = {path.get("id") for path in paths if path.get("id")}
    if payload.get("start_here") not in path_ids:
        errors.append("learning start_here does not resolve")
    for path in paths:
        validate_learning_path(path, path_ids, command_names, errors)
    for recipe in recipes:
        if recipe.get("learning_path") not in path_ids:
            errors.append(
                f"{recipe.get('id')}: unresolved learning path {recipe.get('learning_path')!r}"
            )
    validate_learning_cycles(paths, errors)
    return paths


def validate_learning_path(
    path: dict, path_ids: set[str], command_names: set[str], errors: list[str]
) -> None:
    path_id = path.get("id")
    for field in (
        "title",
        "sequence",
        "anchors",
        "lab",
        "mastery_gate",
        "cli_commands",
    ):
        if not path.get(field):
            errors.append(f"{path_id}: missing learning-path field {field}")
    for prerequisite in path.get("prerequisites") or []:
        if prerequisite not in path_ids:
            errors.append(f"{path_id}: unresolved prerequisite {prerequisite}")
    for anchor in path.get("anchors") or []:
        if not local_path_exists(anchor):
            errors.append(f"{path_id}: missing learning anchor {anchor}")
    for invocation in path.get("cli_commands") or []:
        prefix = "posttrainllm "
        if not invocation.startswith(prefix):
            errors.append(f"{path_id}: invalid CLI invocation {invocation!r}")
            continue
        command_name = invocation.removeprefix(prefix)
        if command_name not in command_names:
            errors.append(f"{path_id}: unknown CLI command {command_name!r}")


def validate_learning_cycles(paths: list[dict], errors: list[str]) -> None:
    by_path = {path.get("id"): path for path in paths}
    path_ids = set(by_path)
    visited_paths: set[str] = set()

    def visit(path_id: str, active: set[str]) -> None:
        if path_id in active:
            errors.append(f"learning prerequisite cycle reaches {path_id}")
            return
        if path_id in visited_paths:
            return
        active.add(path_id)
        for prerequisite in (by_path.get(path_id) or {}).get("prerequisites") or []:
            visit(prerequisite, active)
        active.remove(path_id)
        visited_paths.add(path_id)

    for path_id in path_ids:
        visit(path_id, set())


def validate_journey_artifact_links(
    artifact: dict, artifact_id: str | None, state: dict, errors: list[str]
) -> None:
    for action_name in ARTIFACT_ACTIONS:
        action = artifact.get(action_name) or {}
        if not action.get("label") or not action.get("href"):
            errors.append(f"{artifact_id}: {action_name} must have label and href")
        elif not local_path_exists(action["href"]):
            errors.append(f"{artifact_id}: missing {action_name} href {action['href']}")
    anchors = artifact.get("anchors") or []
    if not anchors:
        errors.append(f"{artifact_id}: missing artifact anchors")
    for anchor in anchors:
        if not local_path_exists(anchor):
            errors.append(f"{artifact_id}: missing artifact anchor {anchor}")
    for invocation in artifact.get("cli_commands") or []:
        prefix = "posttrainllm "
        if not invocation.startswith(prefix):
            errors.append(f"{artifact_id}: invalid CLI invocation {invocation!r}")
        elif invocation.removeprefix(prefix) not in state["command_names"]:
            errors.append(f"{artifact_id}: unknown CLI command {invocation!r}")


def validate_journey_artifact(artifact: dict, state: dict, errors: list[str]) -> None:
    artifact_id = artifact.get("id")
    if not artifact_id or artifact_id in state["seen_artifacts"]:
        errors.append(f"missing or duplicate journey artifact id: {artifact_id!r}")
    state["seen_artifacts"].add(artifact_id)
    for field in ("title", "kind", "workload", "summary"):
        if not artifact.get(field):
            errors.append(f"{artifact_id}: missing artifact field {field}")
    if artifact.get("readiness") not in state["readiness_values"]:
        errors.append(f"{artifact_id}: invalid readiness {artifact.get('readiness')!r}")
    validate_journey_artifact_links(artifact, artifact_id, state, errors)


def validate_artifact_stage(stage: dict, state: dict, errors: list[str]) -> None:
    stage_id = stage.get("id")
    if not stage_id or stage_id in state["seen_stages"]:
        errors.append(f"missing or duplicate artifact stage id: {stage_id!r}")
    state["seen_stages"].add(stage_id)
    for field in ("title", "question", "outcome"):
        if not stage.get(field):
            errors.append(f"{stage_id}: missing artifact-stage field {field}")
    order = stage.get("order")
    if not isinstance(order, int):
        errors.append(f"{stage_id}: artifact-stage order must be an integer")
    else:
        state["orders"].append(order)
    path_id = stage.get("path_id")
    if path_id not in state["learning_path_ids"]:
        errors.append(f"{stage_id}: unresolved learning path {path_id!r}")
    else:
        state["covered_paths"].add(path_id)
    for prerequisite in stage.get("prerequisites") or []:
        if prerequisite not in state["stage_ids"]:
            errors.append(
                f"{stage_id}: unresolved artifact-stage prerequisite {prerequisite}"
            )
    artifacts = stage.get("artifacts") or []
    if not artifacts:
        errors.append(f"{stage_id}: artifact stage has no artifacts")
    for artifact in artifacts:
        validate_journey_artifact(artifact, state, errors)


def validate_artifact_journey(
    payload: dict,
    learning_paths: list[dict],
    command_names: set[str],
    errors: list[str],
) -> tuple[list[dict], int]:
    stages = payload.get("stages") or []
    state = {
        "stage_ids": {stage.get("id") for stage in stages if stage.get("id")},
        "learning_path_ids": {
            path.get("id") for path in learning_paths if path.get("id")
        },
        "readiness_values": set((payload.get("readiness") or {}).keys()),
        "command_names": command_names,
        "seen_stages": set(),
        "seen_artifacts": set(),
        "covered_paths": set(),
        "orders": [],
    }
    if payload.get("schema_version") != 1:
        errors.append("artifact journey must use schema v1")
    if payload.get("start_here") not in state["stage_ids"]:
        errors.append("artifact journey start_here does not resolve")
    if not state["readiness_values"]:
        errors.append("artifact journey readiness legend is empty")
    for stage in stages:
        validate_artifact_stage(stage, state, errors)
    if sorted(state["orders"]) != list(range(1, len(stages) + 1)):
        errors.append("artifact journey stage order must be contiguous from 1")
    if state["covered_paths"] != state["learning_path_ids"]:
        errors.append("artifact journey learning-path coverage drift")
    validate_learning_cycles(stages, errors)

    narrative = (ROOT / "docs/learn/artifact-journey.md").read_text(encoding="utf-8")
    for artifact_id in state["seen_artifacts"]:
        if f"`{artifact_id}`" not in narrative:
            errors.append(
                f"artifact journey narrative is missing artifact {artifact_id}"
            )
    return stages, len(state["seen_artifacts"])


def validate_public_surfaces(errors: list[str]) -> set[str]:
    for relative, needles in PUBLIC_CONTRACTS.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing public contract source {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{relative}: missing public contract marker {needle!r}")

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    browser_job = workflow.split("  browser:", 1)[1].split("\n  mac:", 1)[0]
    if re.search(r"^\s+if:\s+false\s*$", browser_job, re.MULTILINE):
        errors.append("browser CI job is disabled")

    artifact_source = (ROOT / "browser/src/artifacts.ts").read_text(encoding="utf-8")
    artifact_ids = set(
        re.findall(r'^\s+slug: "([^"]+)",$', artifact_source, re.MULTILINE)
    )
    artifact_doc = (ROOT / "docs/factory/public-artifacts.md").read_text(
        encoding="utf-8"
    )
    artifact_table = artifact_doc.split("## Current Public Artifact List", 1)[-1].split(
        "## Artifact Details", 1
    )[0]
    documented_artifacts = set(
        re.findall(r"^\| `([^`]+)` \|", artifact_table, re.MULTILINE)
    )
    if artifact_ids != documented_artifacts:
        errors.append(
            "public artifact registries drift: "
            f"missing in docs={sorted(artifact_ids - documented_artifacts)}, "
            f"missing in browser={sorted(documented_artifacts - artifact_ids)}"
        )
    for required_artifact in ("needle2-tool-selection", "parakeet-wgsl-browser-asr"):
        if required_artifact not in artifact_ids:
            errors.append(f"missing required experiment artifact {required_artifact}")
    return artifact_ids


def validate_browser_landmarks(errors: list[str]) -> None:
    header_path = ROOT / "browser/src/components/SiteHeader.astro"
    header = header_path.read_text(encoding="utf-8")
    if 'class="sh-skip" href="#main"' not in header:
        errors.append("SiteHeader must provide the shared skip-to-content link")
    # A status page renders the header but belongs to no nav section, so it
    # declares active="none": the sentinel resolves to no key, which is also
    # what switches off SiteHeader's pathname fallback. Every page still has to
    # state its section explicitly; "none" is a statement, not an exemption.
    header_keys = set(re.findall(r'key: "([^"]+)"', header)) | {"none"}

    for page in sorted((ROOT / "browser/src/pages").rglob("*.astro")):
        text = page.read_text(encoding="utf-8")
        if "SiteHeader" not in text:
            continue
        relative = str(page.relative_to(ROOT))
        if text.count("<main") != 1:
            errors.append(f"{relative}: expected exactly one main landmark")
        if text.count("<h1") != 1:
            errors.append(f"{relative}: expected exactly one h1")
        main_ids = re.findall(r'<main[^>]*\bid="([^"]+)"', text)
        if main_ids != ["main"]:
            errors.append(f"{relative}: main landmark must have id=main")
        active_values = re.findall(r'<SiteHeader[^>]*\bactive="([^"]+)"', text)
        root_home = page == ROOT / "browser/src/pages/index.astro"
        if not root_home and len(active_values) != 1:
            errors.append(f"{relative}: expected one SiteHeader active section")
        for active in active_values:
            if active not in header_keys:
                errors.append(f"{relative}: unresolved SiteHeader active key {active}")


def main() -> int:
    errors: list[str] = []
    attempts = validate_attempts(load_json("docs/attempts.json"), errors)
    recipes = validate_recipes(load_json("docs/recipes/registry.json"), errors)
    paths = validate_learning(
        load_json("docs/learn/path-registry.json"),
        recipes,
        cli_catalog_names(),
        errors,
    )
    artifact_stages, journey_artifact_count = validate_artifact_journey(
        load_json("docs/learn/artifact-journey.json"),
        paths,
        cli_catalog_names(),
        errors,
    )
    artifact_ids = validate_public_surfaces(errors)
    validate_browser_landmarks(errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(
        "project completion check ok: "
        f"{len(attempts)} experiments, {len(recipes)} recipes, "
        f"{len(paths)} learning paths, {len(artifact_stages)} artifact stages, "
        f"{journey_artifact_count} buildable artifacts, "
        f"{len(artifact_ids)} public artifacts, "
        "0 unresolved statuses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
