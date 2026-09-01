#!/usr/bin/env python3
"""Fail when CLI dispatch, discovery metadata, or parked commands drift."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "native-mac/Sources/TinyGPT/TinyGPT.swift"
CATALOG = ROOT / "native-mac/Sources/TinyGPT/CLICommandCatalog.swift"
EXPERIMENTAL = ROOT / "native-mac/Sources/TinyGPT/ExperimentalCommands.swift"
MAC_RELEASE = ROOT / "browser/src/data/mac-release.ts"


def fail(message: str) -> None:
    print(f"CLI SURFACE FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def parse_dispatch_names(entrypoint: str, catalog: str) -> list[str]:
    switch_names: list[str] = []
    dispatch_source = entrypoint + catalog.split("static func runCommands", 1)[0]
    for match in re.finditer(r"case ((?:\"[^\"]+\"(?:,\s*)?)+):", dispatch_source):
        switch_names.extend(re.findall(r'"([^"]+)"', match.group(1)))
    return [name for name in switch_names if name not in {"-h", "--help", "--version"}]


def parse_catalog_names(catalog: str) -> list[str]:
    catalog_block = catalog.split("static func runDiscoveryIfRequested", 1)[0]
    catalog_names = re.findall(r'Command\("([^\"]+)"', catalog_block)
    return catalog_names


def parse_experimental_names(experimental: str) -> list[str]:
    runner_block = experimental.split("private static let runners", 1)[1].split(
        "\n    ]", 1
    )[0]
    return re.findall(r'^\s*"([^"]+)":', runner_block, re.MULTILINE)


def validate_names(
    switch_names: list[str], catalog_names: list[str], experimental_names: list[str]
) -> None:
    top_level_catalog = [name for name in catalog_names if " " not in name]
    namespaced_experimental = [f"experimental {name}" for name in experimental_names]

    if dupes := duplicates(catalog_names):
        fail(f"duplicate catalog entries: {', '.join(dupes)}")
    if dupes := duplicates(switch_names):
        fail(f"duplicate dispatch cases: {', '.join(dupes)}")
    if set(switch_names) != set(top_level_catalog):
        missing = sorted(set(switch_names) - set(top_level_catalog))
        stale = sorted(set(top_level_catalog) - set(switch_names))
        fail(f"dispatch/catalog drift; missing={missing}, stale={stale}")
    if set(namespaced_experimental) != {
        name for name in catalog_names if name.startswith("experimental ")
    }:
        missing = sorted(set(namespaced_experimental) - set(catalog_names))
        stale = sorted(
            {name for name in catalog_names if name.startswith("experimental ")}
            - set(namespaced_experimental)
        )
        fail(f"experimental catalog drift; missing={missing}, stale={stale}")


def validate_default_help(catalog: str, experimental_names: list[str]) -> None:
    default_help = catalog.split("static func printOverview() {", 1)[1].split(
        "\n    }", 1
    )[0]
    leaked = [
        name for name in experimental_names if f"posttrainllm {name}" in default_help
    ]
    if leaked:
        fail(f"parked aliases leaked into default help: {', '.join(leaked)}")
    if "commands --json" not in default_help or "Retained lab loop" not in default_help:
        fail("default help does not advertise discovery and retained-lab state")


def validate_version(catalog: str) -> str:
    release = MAC_RELEASE.read_text()
    cli_match = re.search(r'static let version = "([^"]+)"', catalog)
    release_match = re.search(r'^\s*version: "([^"]+)",$', release, re.MULTILINE)
    if not cli_match or not release_match:
        fail("could not resolve CLI and Mac release versions")
    cli_version = cli_match.group(1)
    release_version = release_match.group(1)
    if cli_version != release_version:
        fail(f"CLI version {cli_version} != Mac release version {release_version}")
    return cli_version


def main() -> None:
    entrypoint = ENTRYPOINT.read_text()
    catalog = CATALOG.read_text()
    experimental = EXPERIMENTAL.read_text()
    switch_names = parse_dispatch_names(entrypoint, catalog)
    catalog_names = parse_catalog_names(catalog)
    experimental_names = parse_experimental_names(experimental)
    validate_names(switch_names, catalog_names, experimental_names)
    validate_default_help(catalog, experimental_names)
    cli_version = validate_version(catalog)

    entry_count = len(catalog_names)
    active_count = len([name for name in catalog_names if " " not in name])
    experimental_count = len(experimental_names)
    print(
        "CLI SURFACE OK: "
        f"{active_count} top-level commands, {experimental_count} parked commands, "
        f"{entry_count} catalog entries, version {cli_version}"
    )


if __name__ == "__main__":
    main()
