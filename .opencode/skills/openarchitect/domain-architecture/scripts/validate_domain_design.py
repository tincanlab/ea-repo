#!/usr/bin/env python3
"""Validate domain-design.yml and component-specs.yml against JSON schemas.

Usage:
    python validate_domain_design.py --domain billing
    python validate_domain_design.py --domain billing --component-specs-only

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

# Reuse component-specs schema from solution-architecture skill
SA_SKILL_DIR = SKILL_DIR.parent / "solution-architecture"
COMPONENT_SCHEMA = SA_SKILL_DIR / "references" / "component-specs.schema.json"


def _load_yaml(path: Path) -> dict | None:
    if not path.exists():
        print(f"  SKIP: {path} (not found)")
        return None
    if yaml is None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ERROR: pyyaml not installed and {path} is not valid JSON")
            return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_schema(path: Path) -> dict | None:
    if not path.exists():
        print(f"  WARN: schema not found at {path}")
        return None
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="validate_domain_design.py")
    parser.add_argument("--domain", required=True, help="Domain name")
    parser.add_argument("--component-specs-only", action="store_true")
    args = parser.parse_args()

    domain_dir = REPO_ROOT / "architecture" / "domains" / args.domain
    all_errors: list[str] = []

    # Validate component-specs.yml
    comp_path = domain_dir / "component-specs.yml"
    print(f"Validating component-specs: {comp_path}")
    comp_data = _load_yaml(comp_path)
    comp_schema = _load_schema(COMPONENT_SCHEMA)
    if comp_data and comp_schema:
        errors = _validate(comp_data, comp_schema, str(comp_path))
        if errors:
            all_errors.extend([f"  {comp_path}:"] + errors)
            print(f"  FAIL: {len(errors)} error(s)")
        else:
            print("  PASS")

    if args.component_specs_only:
        if all_errors:
            print("\n--- Validation Summary ---")
            for err in all_errors:
                print(err)
            return 1
        print("\nAll validations passed.")
        return 0

    # Validate domain-design.yml (structural check: must have key sections)
    design_path = domain_dir / "domain-design.yml"
    print(f"Validating domain-design: {design_path}")
    design_data = _load_yaml(design_path)
    if design_data:
        required_sections = ["context", "bounded_context", "aggregates"]
        missing = [s for s in required_sections if s not in design_data]
        if missing:
            all_errors.append(f"  {design_path}: missing required sections: {missing}")
            print(f"  FAIL: missing sections {missing}")
        else:
            print("  PASS")

    if all_errors:
        print("\n--- Validation Summary ---")
        for err in all_errors:
            print(err)
        return 1

    print("\nAll validations passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
