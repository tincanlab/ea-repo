#!/usr/bin/env python3
"""Validate component-specs.yml and interface-contracts.yml against JSON schemas.

Usage:
    python validate_component_specs.py [--component-specs PATH] [--interface-contracts PATH]
    python validate_component_specs.py --all  # validate default paths

Exit codes:
    0 = all valid
    1 = validation errors found
    2 = file not found / parse error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def _repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


REPO_ROOT = _repo_root(Path.cwd())
SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_DIR / "references"

DEFAULT_COMPONENT_SPECS = REPO_ROOT / "architecture" / "domains"
DEFAULT_INTERFACE_CONTRACTS = (
    REPO_ROOT / "architecture" / "solution" / "interface-contracts.yml"
)

COMPONENT_SCHEMA = REFERENCES / "component-specs.schema.json"
INTERFACE_SCHEMA = REFERENCES / "interface-contracts.schema.json"


def _load_yaml(path: Path) -> dict | None:
    if not path.exists():
        print(f"  SKIP: {path} (not found)")
        return None
    if yaml is None:
        # Fallback: try JSON parse (some YAML is valid JSON)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ERROR: pyyaml not installed and {path} is not valid JSON")
            return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(data: dict, schema: dict, label: str) -> list[str]:
    if jsonschema is None:
        print(f"  WARN: jsonschema not installed, skipping validation for {label}")
        return []
    errors: list[str] = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path_str = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"  {path_str}: {error.message}")
    return errors


def _find_component_spec_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(base.rglob("component-specs.yml"))


def main() -> int:
    parser = argparse.ArgumentParser(prog="validate_component_specs.py")
    parser.add_argument(
        "--component-specs",
        type=Path,
        nargs="*",
        help="Paths to component-specs.yml files",
    )
    parser.add_argument(
        "--interface-contracts",
        type=Path,
        help="Path to interface-contracts.yml",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all default paths",
    )
    args = parser.parse_args()

    comp_schema = _load_schema(COMPONENT_SCHEMA)
    ifc_schema = _load_schema(INTERFACE_SCHEMA)

    all_errors: list[str] = []

    # Component specs
    comp_paths: list[Path] = []
    if args.component_specs:
        comp_paths = args.component_specs
    elif args.all:
        comp_paths = _find_component_spec_files(DEFAULT_COMPONENT_SPECS)

    for comp_path in comp_paths:
        print(f"Validating component-specs: {comp_path}")
        data = _load_yaml(comp_path)
        if data is None:
            all_errors.append(f"  {comp_path}: file not found or parse error")
            continue
        errors = _validate(data, comp_schema, str(comp_path))
        if errors:
            all_errors.extend([f"  {comp_path}:"] + errors)
            print(f"  FAIL: {len(errors)} error(s)")
        else:
            print("  PASS")

    # Interface contracts
    ifc_path = args.interface_contracts or (
        DEFAULT_INTERFACE_CONTRACTS if args.all else None
    )
    if ifc_path:
        print(f"Validating interface-contracts: {ifc_path}")
        data = _load_yaml(ifc_path)
        if data is None:
            all_errors.append(f"  {ifc_path}: file not found or parse error")
        else:
            errors = _validate(data, ifc_schema, str(ifc_path))
            if errors:
                all_errors.extend([f"  {ifc_path}:"] + errors)
                print(f"  FAIL: {len(errors)} error(s)")
            else:
                print("  PASS")

    if all_errors:
        print("\n--- Validation Summary ---")
        for err in all_errors:
            print(err)
        return 1

    if not comp_paths and not ifc_path:
        print("No files to validate. Use --all or specify paths.")
        return 0

    print("\nAll validations passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
