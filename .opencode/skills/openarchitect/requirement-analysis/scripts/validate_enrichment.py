#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _load_yaml(path: Path) -> object:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency: pyyaml. Install with: python -m pip install pyyaml"
        ) from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(instance: object, schema: object) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency: jsonschema. Install with: python -m pip install jsonschema"
        ) from exc
    jsonschema.validate(instance=instance, schema=schema)


def main() -> int:
    parser = argparse.ArgumentParser(prog="validate_enrichment.py")
    parser.add_argument(
        "--enrichment-yml",
        default="architecture/requirements/enrichment.yml",
        help="Path to enrichment.yml (repo-relative by default).",
    )
    parser.add_argument(
        "--schema",
        default="",
        help="Path to enrichment schema JSON. Defaults to references/enrichment.schema.json.",
    )
    args = parser.parse_args()

    repo = _repo_root(Path.cwd())
    enrichment_path = (repo / args.enrichment_yml).resolve()
    if args.schema:
        schema_path = Path(args.schema).expanduser().resolve()
    else:
        schema_path = (
            Path(__file__).resolve().parents[1] / "references" / "enrichment.schema.json"
        ).resolve()

    if not enrichment_path.exists():
        print(f"[ERROR] enrichment file not found: {enrichment_path}")
        return 2
    if not schema_path.exists():
        print(f"[ERROR] schema file not found: {schema_path}")
        return 2

    errors: list[str] = []

    try:
        instance = _load_yaml(enrichment_path)
    except Exception as exc:
        print(f"[ERROR] YAML load failed: {exc}")
        return 2

    try:
        schema = _load_json(schema_path)
    except Exception as exc:
        print(f"[ERROR] schema load failed: {exc}")
        return 2

    try:
        _validate_schema(instance=instance, schema=schema)
    except Exception as exc:
        errors.append(f"schema_validation_failed: {exc}")

    if not isinstance(instance, dict):
        errors.append("enrichment.yml must parse to a mapping/object at top-level")
        instance_dict: dict[str, object] = {}
    else:
        instance_dict = instance

    evidence = instance_dict.get("evidence")
    verification = {}
    if isinstance(evidence, dict):
        verification_obj = evidence.get("verification")
        if isinstance(verification_obj, dict):
            verification = verification_obj

    hierarchy_expected = bool(verification.get("hierarchy_expected"))
    hierarchy_used = bool(verification.get("hierarchy_used"))
    reason_if_skipped = str(verification.get("reason_if_skipped") or "").strip()

    if hierarchy_expected and (not hierarchy_used) and not reason_if_skipped:
        errors.append(
            "hierarchy_verification_failed: hierarchy_expected=true but hierarchy_used=false without reason_if_skipped"
        )

    mappings = instance_dict.get("mappings")
    hierarchy_expansion_seen = False
    if isinstance(mappings, list):
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            etom = mapping.get("etom_processes")
            if not isinstance(etom, list):
                continue
            for process in etom:
                if not isinstance(process, dict):
                    continue
                relation = str(process.get("relation_to_anchor") or "").strip()
                if relation in {"parent", "child", "sibling"}:
                    hierarchy_expansion_seen = True
                    anchor_process_id = str(process.get("anchor_process_id") or "").strip()
                    if not anchor_process_id:
                        errors.append(
                            "hierarchy_relation_missing_anchor: parent/child/sibling relation requires anchor_process_id"
                        )

    if hierarchy_used and not hierarchy_expansion_seen:
        errors.append(
            "hierarchy_used_but_no_expansion: hierarchy_used=true but no parent/child/sibling relations found"
        )

    if errors:
        print(f"[ERROR] validation failed: {enrichment_path}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"[OK] enrichment validated: {enrichment_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
