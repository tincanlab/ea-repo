#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"PyYAML is required for selector resolution: {exc}")


ACTIVE_STATUSES = {"active", "approved", "ready", "in_progress"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"selector catalog not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"failed to parse YAML {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"selector catalog must be a YAML object: {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"implementation catalog not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"failed to parse JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"implementation catalog must be a JSON object: {path}")
    return payload


def _normalize_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "active"


def _as_items(payload: dict[str, Any], key: str, path: Path) -> list[dict[str, Any]]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected top-level '{key}' list")
    items: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            items.append(row)
    if not items:
        raise ValueError(f"{path}: '{key}' list is empty")
    return items


def _match_selector(*, items: list[dict[str, Any]], selector_id: str, keys: list[str]) -> list[dict[str, Any]]:
    normalized = str(selector_id or "").strip()
    if not normalized:
        return []
    matches: list[dict[str, Any]] = []
    for item in items:
        for key in keys:
            value = str(item.get(key) or "").strip()
            if value and value == normalized:
                matches.append(item)
                break
    return matches


def _resolve_sa_or_da(
    *,
    role: str,
    selector_id: str,
    catalog_path: Path,
    list_key: str,
    selector_key: str,
    repo_url_key: str,
    allow_inactive: bool,
) -> dict[str, str]:
    payload = _load_yaml(catalog_path)
    items = _as_items(payload, list_key, catalog_path)
    matches = _match_selector(items=items, selector_id=selector_id, keys=[selector_key])
    if not matches:
        raise ValueError(f"{role}: selector_id '{selector_id}' not found in {catalog_path}")
    if len(matches) > 1:
        raise ValueError(f"{role}: selector_id '{selector_id}' is ambiguous in {catalog_path}")
    selected = matches[0]
    status = _normalize_status(selected.get("status"))
    if not allow_inactive and status not in ACTIVE_STATUSES:
        raise ValueError(f"{role}: selector_id '{selector_id}' is not active (status={status})")
    repo_url = str(selected.get(repo_url_key) or "").strip()
    if not repo_url:
        raise ValueError(f"{role}: selector_id '{selector_id}' missing {repo_url_key}")
    return {
        "OPENARCHITECT_GIT_REPO_URL": repo_url,
        "OPENARCHITECT_SELECTOR_ID": selector_id,
        "OPENARCHITECT_SELECTOR_STATUS": status,
    }


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _as_list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _as_str(item)
        if text:
            result.append(text)
    return result


def _resolve_da(
    *,
    selector_id: str,
    allow_inactive: bool,
    catalog: str | None,
    engagement_catalog: str | None,
) -> dict[str, str]:
    engagement_catalog_path = Path(
        engagement_catalog or catalog or "architecture/solution/domain-engagements.yml"
    )
    engagement_resolved = _resolve_sa_or_da(
        role="da",
        selector_id=selector_id,
        catalog_path=engagement_catalog_path,
        list_key="engagements",
        selector_key="engagement_id",
        repo_url_key="domain_repo_url",
        allow_inactive=allow_inactive,
    )
    payload = _load_yaml(engagement_catalog_path)
    items = _as_items(payload, "engagements", engagement_catalog_path)
    matches = _match_selector(
        items=items,
        selector_id=selector_id,
        keys=["engagement_id"],
    )
    selected = matches[0]
    engagement_resolved["OPENARCHITECT_SELECTOR_KIND"] = "engagement"
    engagement_resolved["OPENARCHITECT_ACTIVE_ENGAGEMENT_ID"] = str(
        selected.get("engagement_id") or selector_id
    ).strip()
    domain_id = str(selected.get("domain_id") or "").strip()
    initiative_id = str(selected.get("initiative_id") or "").strip()
    handoff_ref = str(selected.get("handoff_ref") or "").strip()
    if domain_id:
        engagement_resolved["OPENARCHITECT_ACTIVE_DOMAIN_ID"] = domain_id
    if initiative_id:
        engagement_resolved["OPENARCHITECT_ACTIVE_INITIATIVE_ID"] = initiative_id
    if handoff_ref:
        engagement_resolved["OPENARCHITECT_ACTIVE_HANDOFF_REF"] = handoff_ref
    return engagement_resolved


def _resolve_sa(
    *,
    selector_id: str,
    allow_inactive: bool,
    catalog: str | None,
) -> dict[str, str]:
    catalog_path = Path(catalog or "architecture/portfolio/initiatives.yml")
    resolved = _resolve_sa_or_da(
        role="sa",
        selector_id=selector_id,
        catalog_path=catalog_path,
        list_key="initiatives",
        selector_key="initiative_id",
        repo_url_key="solution_repo_url",
        allow_inactive=allow_inactive,
    )

    payload = _load_yaml(catalog_path)
    items = _as_items(payload, "initiatives", catalog_path)
    matches = _match_selector(
        items=items,
        selector_id=selector_id,
        keys=["initiative_id"],
    )
    selected = matches[0]

    resolved["OPENARCHITECT_SELECTOR_KIND"] = "initiative"
    resolved["OPENARCHITECT_ACTIVE_INITIATIVE_ID"] = _as_str(selected.get("initiative_id") or selector_id)
    resolved["OPENARCHITECT_ACTIVE_INITIATIVE_NAME"] = _as_str(selected.get("name"))

    meta = selected.get("metadata")
    meta_obj = meta if isinstance(meta, dict) else {}
    resolved["OPENARCHITECT_ACTIVE_INITIATIVE_DESCRIPTION"] = _as_str(meta_obj.get("description"))
    objectives = _as_list_of_str(meta_obj.get("objectives"))
    if objectives:
        resolved["OPENARCHITECT_ACTIVE_INITIATIVE_OBJECTIVES_JSON"] = json.dumps(
            objectives, ensure_ascii=True, sort_keys=False
        )
    resolved["OPENARCHITECT_ACTIVE_INITIATIVE_CONTEXT_JSON"] = json.dumps(
        {
            "initiative_id": _as_str(selected.get("initiative_id") or selector_id),
            "name": _as_str(selected.get("name")),
            "description": _as_str(meta_obj.get("description")),
            "objectives": objectives,
            "status": _as_str(selected.get("status")),
        },
        ensure_ascii=True,
        sort_keys=False,
    )
    return resolved


def _resolve_dev(
    *,
    selector_id: str,
    implementation_catalog_path: Path,
    allow_inactive: bool,
) -> dict[str, str]:
    payload = _load_json(implementation_catalog_path)
    items = _as_items(payload, "implementation_work_items", implementation_catalog_path)
    matches = _match_selector(items=items, selector_id=selector_id, keys=["work_item_id", "api_id"])
    if not matches:
        raise ValueError(f"dev: selector_id '{selector_id}' not found in {implementation_catalog_path}")
    if len(matches) > 1:
        raise ValueError(f"dev: selector_id '{selector_id}' is ambiguous in {implementation_catalog_path}")
    selected = matches[0]
    status = _normalize_status(selected.get("status"))
    if not allow_inactive and status not in ACTIVE_STATUSES:
        raise ValueError(f"dev: selector_id '{selector_id}' is not active (status={status})")

    result = {
        "OPENARCHITECT_SELECTOR_ID": selector_id,
        "OPENARCHITECT_SELECTOR_STATUS": status,
        "OPENARCHITECT_ACTIVE_WORK_ITEM_ID": str(selected.get("work_item_id") or "").strip(),
        "OPENARCHITECT_ACTIVE_API_ID": str(selected.get("api_id") or "").strip(),
    }
    repo_url = str(selected.get("repo_url") or "").strip()
    repo_path = str(selected.get("repo_path") or "").strip()
    if repo_url:
        result["OPENARCHITECT_GIT_REPO_URL"] = repo_url
    if repo_path:
        result["OPENARCHITECT_ACTIVE_REPO_PATH"] = repo_path
    return result


def _emit(values: dict[str, str], output_format: str) -> None:
    filtered = {k: str(v) for k, v in values.items() if str(v).strip()}
    if output_format == "json":
        print(json.dumps(filtered, ensure_ascii=True, indent=2))
        return
    if output_format == "env":
        for key, value in filtered.items():
            print(f"{key}={value}")
        return
    for key, value in filtered.items():
        print(f"export {key}={shlex.quote(value)}")


def _default_selector_id(role: str) -> str:
    if role == "sa":
        return str(os.getenv("INITIATIVE_ID") or "").strip()
    if role == "da":
        return str(os.getenv("ENGAGEMENT_ID") or "").strip()
    return str(os.getenv("WORK_ITEM_ID") or os.getenv("API_ID") or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve OPENARCHITECT_GIT_REPO_URL and related env vars from selector manifests."
    )
    parser.add_argument("--role", choices=["sa", "da", "dev"], required=True)
    parser.add_argument(
        "--selector-id",
        default=None,
        help="Initiative/engagement/work-item/API selector.",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help=(
            "Primary selector catalog path. Defaults: SA=architecture/portfolio/initiatives.yml, "
            "DA=architecture/solution/domain-engagements.yml."
        ),
    )
    parser.add_argument(
        "--da-engagement-catalog",
        default=None,
        help="DA engagement catalog path (default: architecture/solution/domain-engagements.yml).",
    )
    parser.add_argument(
        "--implementation-catalog",
        default="implementation-catalog.json",
        help="Implementation catalog path for dev role.",
    )
    parser.add_argument("--git-workdir", default=None, help="In-container git workdir.")
    parser.add_argument("--allow-inactive", action="store_true", help="Allow non-active selector entries.")
    parser.add_argument("--output", choices=["export", "env", "json"], default="export")
    args = parser.parse_args()

    selector_id = str(args.selector_id or _default_selector_id(args.role)).strip()
    if not selector_id:
        env_hint = {
            "sa": "INITIATIVE_ID",
            "da": "ENGAGEMENT_ID",
            "dev": "WORK_ITEM_ID or API_ID",
        }[args.role]
        print(f"error: missing selector id for role={args.role}; provide --selector-id or set {env_hint}", file=sys.stderr)
        return 2

    git_workdir = str(args.git_workdir or os.getenv("OPENARCHITECT_GIT_WORKDIR") or "/home/op/project").strip()

    try:
        if args.role == "sa":
            resolved = _resolve_sa(
                selector_id=selector_id,
                allow_inactive=bool(args.allow_inactive),
                catalog=args.catalog,
            )
        elif args.role == "da":
            resolved = _resolve_da(
                selector_id=selector_id,
                allow_inactive=bool(args.allow_inactive),
                catalog=args.catalog,
                engagement_catalog=args.da_engagement_catalog,
            )
        else:
            resolved = _resolve_dev(
                selector_id=selector_id,
                implementation_catalog_path=Path(args.implementation_catalog),
                allow_inactive=bool(args.allow_inactive),
            )
        resolved["OPENARCHITECT_GIT_WORKDIR"] = git_workdir
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    _emit(resolved, args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
