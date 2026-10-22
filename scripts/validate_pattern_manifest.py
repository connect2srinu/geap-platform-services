#!/usr/bin/env python3
"""Validate pattern manifests against schemas/pattern.schema.json, plus cross-checks that a
JSON Schema cannot express (referenced paths exist, name matches directory, version matches
the changelog, required pattern directories are present).

Usage:
    python3 scripts/validate_pattern_manifest.py [patterns/<name> ...]

With no arguments, validates every pattern.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, Report, require_deps  # noqa: E402

yaml, jsonschema = require_deps()

SCHEMA_PATH = REPO_ROOT / "schemas" / "pattern.schema.json"
REQUIRED_DIRS = [
    "contracts",
    "src",
    "config",
    "extensions",
    "tests",
    "conformance",
    "examples",
]
REQUIRED_FILES = ["README.md", "pattern.yaml", "CHANGELOG.md"]


def validate_pattern(folder: Path, schema: dict, report: Report) -> None:
    rel = folder.relative_to(REPO_ROOT)
    manifest_path = folder / "pattern.yaml"

    if not manifest_path.is_file():
        report.error(str(rel), "pattern.yaml not found")
        return
    report.ok()

    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report.error(f"{rel}/pattern.yaml", f"not valid YAML: {exc}")
        return
    report.ok()

    try:
        jsonschema.validate(manifest, schema)
        report.ok()
    except jsonschema.ValidationError as exc:
        loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        report.error(f"{rel}/pattern.yaml", f"schema violation at {loc}: {exc.message}")
        return

    meta = manifest["metadata"]
    spec = manifest["spec"]

    if meta["name"] != folder.name:
        report.error(
            f"{rel}/pattern.yaml",
            f"metadata.name '{meta['name']}' does not match directory '{folder.name}'",
        )
    else:
        report.ok()

    for required in REQUIRED_FILES:
        if not (folder / required).is_file():
            report.error(str(rel), f"required file missing: {required}")
        else:
            report.ok()

    for required in REQUIRED_DIRS:
        if not (folder / required).is_dir():
            report.error(str(rel), f"required directory missing: {required}/")
        else:
            report.ok()

    # Every path the manifest references must exist.
    referenced: list[tuple[str, str]] = []
    for iface in spec["interfaces"]:
        if iface.get("spec"):
            referenced.append((f"interfaces[{iface['kind']}].spec", iface["spec"]))
    referenced.append(("configuration.schema", spec["configuration"]["schema"]))
    for i, ex in enumerate(spec["configuration"]["examples"]):
        referenced.append((f"configuration.examples[{i}]", ex))
    for key in ("platformOwned", "domainOwned"):
        referenced.append((f"infrastructure.{key}", spec["infrastructure"][key]))
    referenced.append(("build.dockerfile", spec["build"]["dockerfile"]))
    referenced.append(("tests.unit", spec["tests"]["unit"]))
    referenced.append(("tests.conformance", spec["tests"]["conformance"]))

    for label, relpath in referenced:
        target = REPO_ROOT / relpath
        if not target.exists():
            report.error(
                f"{rel}/pattern.yaml", f"{label} points to missing path: {relpath}"
            )
        else:
            report.ok()

    # Every example configuration must validate against the pattern's own config schema.
    # Caught a real bug during foundation validation: a YAML key with only comments beneath it
    # parses as None, not as an empty mapping, and silently violates the schema.
    schema_path = REPO_ROOT / spec["configuration"]["schema"]
    if schema_path.is_file():
        try:
            config_schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:
            report.error(
                str(schema_path.relative_to(REPO_ROOT)), f"not valid JSON: {exc}"
            )
            config_schema = None
        if config_schema is not None:
            report.ok()
            for relpath in spec["configuration"]["examples"]:
                example_path = REPO_ROOT / relpath
                if not example_path.is_file():
                    continue
                try:
                    example = yaml.safe_load(example_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    report.error(relpath, f"not valid YAML: {exc}")
                    continue
                try:
                    jsonschema.validate(example, config_schema)
                    report.ok()
                except jsonschema.ValidationError as exc:
                    loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
                    report.error(
                        relpath,
                        f"example does not validate against the pattern config schema "
                        f"at {loc}: {exc.message}",
                    )

    # Security-relevant extension points must fail closed.
    for ep in spec.get("extensionPoints", []):
        if "classif" in ep["id"] or "polic" in ep["id"] or "auth" in ep["id"]:
            if ep["failureMode"] != "deny":
                report.error(
                    f"{rel}/pattern.yaml",
                    f"extension point '{ep['id']}' is security-relevant and must have "
                    f"failureMode 'deny', not '{ep['failureMode']}'",
                )
            else:
                report.ok()

    # Version must appear in the changelog, except while still proposed.
    changelog = folder / "CHANGELOG.md"
    if changelog.is_file() and meta["status"] != "proposed":
        if meta["version"] not in changelog.read_text(encoding="utf-8"):
            report.error(
                f"{rel}/CHANGELOG.md",
                f"version {meta['version']} has no changelog entry",
            )
        else:
            report.ok()

    # A pattern cannot claim certification without a conformance suite that has content.
    if meta["status"] in ("certified", "beta"):
        conformance = folder / "conformance"
        if conformance.is_dir() and not any(conformance.glob("test_*.py")):
            report.error(
                str(rel),
                f"status '{meta['status']}' requires a populated conformance suite",
            )
        else:
            report.ok()


def main(argv: list[str]) -> int:
    if not SCHEMA_PATH.is_file():
        sys.exit(f"error: schema not found at {SCHEMA_PATH}")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    if argv:
        folders = [Path(a).resolve() for a in argv]
    else:
        patterns = REPO_ROOT / "patterns"
        folders = (
            sorted(p for p in patterns.iterdir() if p.is_dir())
            if patterns.is_dir()
            else []
        )

    report = Report("Pattern manifest validation")
    if not folders:
        print("No patterns found; nothing to validate.")
        return 0
    for folder in folders:
        if not folder.is_dir():
            report.error(str(folder), "not a directory")
            continue
        validate_pattern(folder, schema, report)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
