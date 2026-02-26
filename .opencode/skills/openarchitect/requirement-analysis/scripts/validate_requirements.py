#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _normalize_question(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"[^\w\s]", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _load_yaml(path: Path) -> object:
    try:
        import yaml  # type: ignore
    except Exception:
        raise RuntimeError(
            "Missing dependency: pyyaml. Install with: python -m pip install pyyaml"
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> object:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(instance: object, schema: object, schema_path: Path) -> None:
    try:
        import jsonschema  # type: ignore
    except Exception:
        raise RuntimeError(
            "Missing dependency: jsonschema. Install with: python -m pip install jsonschema"
        )
    resolver = jsonschema.RefResolver(base_uri=schema_path.resolve().as_uri(), referrer=schema)
    jsonschema.validate(instance=instance, schema=schema, resolver=resolver)


def main() -> int:
    parser = argparse.ArgumentParser(prog="validate_requirements.py")
    parser.add_argument(
        "--mode",
        choices=["solution", "domain"],
        default="solution",
        help="Validation mode. solution validates architecture/requirements/requirements.yml; domain validates a domain requirements file.",
    )
    parser.add_argument(
        "--requirements-yml",
        default="architecture/requirements/requirements.yml",
        help="Path to requirements.yml (repo-relative by default).",
    )
    parser.add_argument(
        "--schema",
        default="",
        help="Path to requirements schema JSON. If omitted, selects a schema based on --mode.",
    )
    parser.add_argument(
        "--allow-approved",
        action="store_true",
        help="Allow requirements with status=approved (default: flag as error).",
    )
    args = parser.parse_args()

    repo = _repo_root(Path.cwd())
    req_path = (repo / args.requirements_yml).resolve()
    if args.schema:
        schema_path = Path(args.schema).expanduser().resolve()
    else:
        references = Path(__file__).resolve().parents[1] / "references"
        if args.mode == "domain":
            schema_path = (references / "domain-requirements.schema.json").resolve()
        else:
            schema_path = (references / "requirements.schema.json").resolve()

    if not req_path.exists():
        print(f"[ERROR] requirements file not found: {req_path}")
        return 2
    if not schema_path.exists():
        print(f"[ERROR] schema file not found: {schema_path}")
        return 2

    try:
        instance = _load_yaml(req_path)
    except Exception as exc:
        print(f"[ERROR] YAML load failed: {exc}")
        return 2

    try:
        schema = _load_json(schema_path)
    except Exception as exc:
        print(f"[ERROR] schema load failed: {exc}")
        return 2

    errors: list[str] = []

    try:
        _validate_schema(instance=instance, schema=schema, schema_path=schema_path)
    except Exception as exc:
        errors.append(f"schema_validation_failed: {exc}")

    if not isinstance(instance, dict):
        errors.append("requirements.yml must parse to a mapping/object at top-level")
        instance_dict: dict[str, object] = {}
    else:
        instance_dict = instance

    requirements = instance_dict.get("requirements")
    if isinstance(requirements, list):
        ids: list[str] = []
        approved: list[str] = []
        for entry in requirements:
            if not isinstance(entry, dict):
                continue
            rid = str(entry.get("id") or "").strip()
            if rid:
                ids.append(rid)
            status = str(entry.get("status") or "").strip().lower()
            if status == "approved" and rid:
                approved.append(rid)
        duplicates = sorted({rid for rid in ids if ids.count(rid) > 1})
        if duplicates:
            errors.append(f"duplicate_requirement_ids: {', '.join(duplicates)}")
        if approved and not args.allow_approved:
            errors.append(
                "approved_requirements_not_allowed: "
                + ", ".join(approved)
                + " (use --allow-approved to bypass)"
            )

    open_questions = instance_dict.get("open_questions")
    if isinstance(open_questions, list):
        policy_obj = instance_dict.get("clarification_policy")
        default_total_cap = 10
        max_allowed_total_cap = 20
        total_cap = default_total_cap
        if isinstance(policy_obj, dict):
            configured_cap = policy_obj.get("max_questions_total")
            if isinstance(configured_cap, int):
                total_cap = configured_cap
        if total_cap > max_allowed_total_cap:
            errors.append(
                f"max_questions_total_exceeds_allowed: {total_cap} > {max_allowed_total_cap}"
            )
        if len(open_questions) > total_cap:
            errors.append(
                f"open_questions_exceed_cap: {len(open_questions)} > {total_cap}"
            )

        norms: dict[str, list[str]] = {}
        for entry in open_questions:
            if not isinstance(entry, dict):
                continue
            qid = str(entry.get("id") or "").strip()
            qtext = str(entry.get("question") or "").strip()
            if not qtext:
                continue
            norm = _normalize_question(qtext)
            if not norm:
                continue
            norms.setdefault(norm, []).append(qid or qtext)
        dups = {k: v for k, v in norms.items() if len(v) > 1}
        if dups:
            examples = []
            for items in list(dups.values())[:5]:
                examples.append("/".join(items[:3]))
            errors.append(f"duplicate_open_questions: examples={', '.join(examples)}")

    if errors:
        print(f"[ERROR] validation failed: {req_path}")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"[OK] requirements validated: {req_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
