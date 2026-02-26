#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyYAML is required: {exc}")

try:
    import jsonschema
except Exception:  # pragma: no cover
    jsonschema = None


INITIATIVE_STATUSES = {
    "active",
    "approved",
    "ready",
    "in_progress",
    "planned",
    "paused",
    "completed",
    "cancelled",
    "archived",
}
DOMAIN_STATUSES = {"active", "planned", "paused", "retired", "archived"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"file not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"failed to parse YAML {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"schema not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to parse schema {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"schema root must be an object: {path}")
    return payload


def _find_schemas_root(explicit: str | None) -> Path | None:
    if explicit:
        root = Path(explicit).resolve()
        return root if root.exists() else None
    script = Path(__file__).resolve()
    candidates = [
        script.parents[2] / "adk" / "docs" / "design" / "schemas",
        script.parents[1] / "docs" / "design" / "schemas",
        Path.cwd() / "docs" / "design" / "schemas",
    ]
    for candidate in candidates:
        if (candidate / "initiatives.schema.json").exists():
            return candidate
    return None


def _validate_with_schema(
    *,
    payload: dict[str, Any],
    schema_name: str,
    schemas_root: Path,
    errors: list[str],
) -> None:
    if jsonschema is None:
        return
    schema_path = schemas_root / schema_name
    try:
        schema_payload = _load_json(schema_path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    validator = jsonschema.Draft202012Validator(schema_payload)
    for err in sorted(validator.iter_errors(payload), key=lambda item: str(item.path)):
        path = ".".join(str(p) for p in err.path) or "<root>"
        errors.append(f"{schema_name}: {path}: {err.message}")


def _as_list(value: Any, name: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{name}: expected a list")
        return []
    return value


def _non_empty_str(value: Any) -> str:
    return str(value or "").strip()


def validate_contracts(
    *,
    initiatives_path: Path,
    domain_registry_path: Path,
    engagements_path: Path,
    schemas_root: Path | None,
    skip_schema: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        initiatives_doc = _load_yaml(initiatives_path)
    except ValueError as exc:
        return [str(exc)], warnings
    try:
        registry_doc = _load_yaml(domain_registry_path)
    except ValueError as exc:
        return [str(exc)], warnings
    try:
        engagements_doc = _load_yaml(engagements_path)
    except ValueError as exc:
        return [str(exc)], warnings

    if not skip_schema:
        if schemas_root is None:
            warnings.append("schemas root not found; schema validation skipped")
        else:
            _validate_with_schema(
                payload=initiatives_doc,
                schema_name="initiatives.schema.json",
                schemas_root=schemas_root,
                errors=errors,
            )
            _validate_with_schema(
                payload=registry_doc,
                schema_name="domain-registry.schema.json",
                schemas_root=schemas_root,
                errors=errors,
            )
            _validate_with_schema(
                payload=engagements_doc,
                schema_name="domain-engagements.schema.json",
                schemas_root=schemas_root,
                errors=errors,
            )

    initiatives_rows = _as_list(initiatives_doc.get("initiatives"), "initiatives.yml:initiatives", errors)
    registry_rows = _as_list(registry_doc.get("domains"), "domain-registry.yml:domains", errors)
    engagement_rows = _as_list(engagements_doc.get("engagements"), "domain-engagements.yml:engagements", errors)

    initiative_ids: set[str] = set()
    for idx, row in enumerate(initiatives_rows):
        if not isinstance(row, dict):
            errors.append(f"initiatives.yml: initiatives[{idx}] must be an object")
            continue
        initiative_id = _non_empty_str(row.get("initiative_id"))
        solution_repo_url = _non_empty_str(row.get("solution_repo_url"))
        status = _non_empty_str(row.get("status")).lower()
        if not initiative_id:
            errors.append(f"initiatives.yml: initiatives[{idx}].initiative_id is required")
        elif initiative_id in initiative_ids:
            errors.append(f"initiatives.yml: duplicate initiative_id '{initiative_id}'")
        else:
            initiative_ids.add(initiative_id)
        if not solution_repo_url:
            errors.append(f"initiatives.yml: initiatives[{idx}].solution_repo_url is required")
        if status and status not in INITIATIVE_STATUSES:
            errors.append(f"initiatives.yml: initiatives[{idx}].status '{status}' is invalid")

    domain_ids: set[str] = set()
    domain_id_pattern = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
    for idx, row in enumerate(registry_rows):
        if not isinstance(row, dict):
            errors.append(f"domain-registry.yml: domains[{idx}] must be an object")
            continue
        domain_id = _non_empty_str(row.get("domain_id"))
        name = _non_empty_str(row.get("name"))
        owner = _non_empty_str(row.get("owner"))
        status = _non_empty_str(row.get("status")).lower()
        if not domain_id:
            errors.append(f"domain-registry.yml: domains[{idx}].domain_id is required")
        elif not domain_id_pattern.match(domain_id):
            errors.append(f"domain-registry.yml: domains[{idx}].domain_id '{domain_id}' is invalid")
        elif domain_id in domain_ids:
            errors.append(f"domain-registry.yml: duplicate domain_id '{domain_id}'")
        else:
            domain_ids.add(domain_id)
        if not name:
            errors.append(f"domain-registry.yml: domains[{idx}].name is required")
        if not owner:
            errors.append(f"domain-registry.yml: domains[{idx}].owner is required")
        if status and status not in DOMAIN_STATUSES:
            errors.append(f"domain-registry.yml: domains[{idx}].status '{status}' is invalid")

    engagement_ids: set[str] = set()
    for idx, row in enumerate(engagement_rows):
        if not isinstance(row, dict):
            errors.append(f"domain-engagements.yml: engagements[{idx}] must be an object")
            continue
        engagement_id = _non_empty_str(row.get("engagement_id"))
        initiative_id = _non_empty_str(row.get("initiative_id"))
        domain_id = _non_empty_str(row.get("domain_id"))
        domain_repo_url = _non_empty_str(row.get("domain_repo_url"))
        status = _non_empty_str(row.get("status")).lower()

        if not engagement_id:
            errors.append(f"domain-engagements.yml: engagements[{idx}].engagement_id is required")
        elif engagement_id in engagement_ids:
            errors.append(f"domain-engagements.yml: duplicate engagement_id '{engagement_id}'")
        else:
            engagement_ids.add(engagement_id)

        if not initiative_id:
            errors.append(f"domain-engagements.yml: engagements[{idx}].initiative_id is required")
        elif initiative_id not in initiative_ids:
            errors.append(
                f"domain-engagements.yml: engagements[{idx}].initiative_id '{initiative_id}' "
                "is not present in initiatives.yml"
            )

        if not domain_id:
            errors.append(f"domain-engagements.yml: engagements[{idx}].domain_id is required")
        elif domain_id not in domain_ids:
            errors.append(
                f"domain-engagements.yml: engagements[{idx}].domain_id '{domain_id}' "
                "is not present in domain-registry.yml"
            )

        if not domain_repo_url:
            errors.append(f"domain-engagements.yml: engagements[{idx}].domain_repo_url is required")
        if status and status not in INITIATIVE_STATUSES:
            errors.append(f"domain-engagements.yml: engagements[{idx}].status '{status}' is invalid")

    if not initiatives_rows:
        warnings.append("initiatives.yml has no initiatives entries")
    if not registry_rows:
        warnings.append("domain-registry.yml has no domains entries")
    if not engagement_rows:
        warnings.append("domain-engagements.yml has no engagements entries")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate initiatives.yml, domain-registry.yml, and domain-engagements.yml "
            "together in one pass (schema + cross-file lineage checks)."
        )
    )
    parser.add_argument("--ea-root", default=".", help="EA repo root (contains initiatives + domain registry).")
    parser.add_argument("--sa-root", default=".", help="SA repo root (contains domain engagements).")
    parser.add_argument(
        "--initiatives",
        default="architecture/portfolio/initiatives.yml",
        help="EA initiatives catalog path (relative to --ea-root unless absolute).",
    )
    parser.add_argument(
        "--domain-registry",
        default="architecture/enterprise/domain-registry.yml",
        help="EA domain registry path (relative to --ea-root unless absolute).",
    )
    parser.add_argument(
        "--engagements",
        default="architecture/solution/domain-engagements.yml",
        help="SA engagements catalog path (relative to --sa-root unless absolute).",
    )
    parser.add_argument(
        "--schemas-root",
        default=None,
        help="Optional schemas directory (defaults to auto-detect docs/design/schemas).",
    )
    parser.add_argument("--skip-schema", action="store_true", help="Skip JSON-schema validation and run lineage checks only.")
    args = parser.parse_args()

    ea_root = Path(args.ea_root).resolve()
    sa_root = Path(args.sa_root).resolve()

    initiatives_path = Path(args.initiatives)
    if not initiatives_path.is_absolute():
        initiatives_path = ea_root / initiatives_path
    domain_registry_path = Path(args.domain_registry)
    if not domain_registry_path.is_absolute():
        domain_registry_path = ea_root / domain_registry_path
    engagements_path = Path(args.engagements)
    if not engagements_path.is_absolute():
        engagements_path = sa_root / engagements_path

    schemas_root = _find_schemas_root(args.schemas_root)
    errors, warnings = validate_contracts(
        initiatives_path=initiatives_path,
        domain_registry_path=domain_registry_path,
        engagements_path=engagements_path,
        schemas_root=schemas_root,
        skip_schema=bool(args.skip_schema),
    )

    print("Selector contract validation inputs:")
    print(f"- initiatives: {initiatives_path}")
    print(f"- domain-registry: {domain_registry_path}")
    print(f"- domain-engagements: {engagements_path}")
    if args.skip_schema:
        print("- schema validation: skipped")
    elif schemas_root:
        print(f"- schemas root: {schemas_root}")
    else:
        print("- schemas root: not found (schema validation skipped)")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"Selector contract validation failed with {len(errors)} error(s).")
        return 2
    print("Selector contract validation passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
