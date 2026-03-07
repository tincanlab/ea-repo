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
DEFAULT_DA_WORKSTREAM_CATALOG = Path("architecture/solution/domain-workstreams.yml")


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


def _load_catalog(path: Path) -> tuple[dict[str, Any], Path]:
    """Load implementation catalog from YAML (canonical) or JSON (compatibility projection).

    YAML (.yml/.yaml) is authoritative per the enterprise.md convention.
    JSON (.json) is a compatibility projection for tmf-developer scaffold generation.

    Resolution order:
    1. If the requested path exists, load it directly.
    2. If a YAML path (.yml/.yaml) is requested but absent, fall back to the
       sibling .json file when it exists.
    3. If a JSON path is requested but absent, try .yml then .yaml siblings.

    Drift guard (enterprise.md convention rule 4):
    When the canonical YAML is loaded and a sibling .json also exists, compare
    the routable work-item IDs in both files.  If they disagree the resolver
    fails closed instead of silently ignoring the stale projection.

    Returns (payload, resolved_path).
    """
    resolved = path
    suffix = resolved.suffix.lower()

    if not resolved.exists():
        if suffix in (".yml", ".yaml"):
            json_fb = resolved.with_suffix(".json")
            if json_fb.exists():
                resolved = json_fb
        elif suffix == ".json":
            for yaml_ext in (".yml", ".yaml"):
                yaml_fb = resolved.with_suffix(yaml_ext)
                if yaml_fb.exists():
                    resolved = yaml_fb
                    break

    if not resolved.exists():
        raise ValueError(f"implementation catalog not found: {path}")

    resolved_suffix = resolved.suffix.lower()
    if resolved_suffix in (".yml", ".yaml"):
        try:
            payload = yaml.safe_load(resolved.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise ValueError(f"failed to parse YAML {resolved}: {exc}") from exc
    else:
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise ValueError(f"failed to parse JSON {resolved}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"implementation catalog must be an object: {resolved}")

    if resolved_suffix in (".yml", ".yaml"):
        json_sibling = resolved.with_suffix(".json")
        if json_sibling.exists():
            _check_catalog_drift(resolved, payload, json_sibling)

    return payload, resolved


def _check_catalog_drift(
    yaml_path: Path,
    yaml_payload: dict[str, Any],
    json_path: Path,
) -> None:
    """Fail closed when YAML and JSON catalogs disagree on any routable field."""
    try:
        json_payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return
    if not isinstance(json_payload, dict):
        return

    yaml_key = "work_items" if "work_items" in yaml_payload else "implementation_work_items"
    json_key = "work_items" if "work_items" in json_payload else "implementation_work_items"

    yaml_items = yaml_payload.get(yaml_key)
    json_items = json_payload.get(json_key)
    if not isinstance(yaml_items, list) or not isinstance(json_items, list):
        return

    _ROUTABLE_FIELDS = ("work_item_id", "api_id", "repo_path", "repo_url", "status")

    def _signature(item: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(item.get(f) or "").strip() for f in _ROUTABLE_FIELDS)

    def _keyed(items: list[Any]) -> dict[str, tuple[str, ...]]:
        out: dict[str, tuple[str, ...]] = {}
        for item in items:
            if isinstance(item, dict):
                wid = str(item.get("work_item_id") or "").strip()
                if wid:
                    out[wid] = _signature(item)
        return out

    yaml_keyed = _keyed(yaml_items)
    json_keyed = _keyed(json_items)

    diffs: list[str] = []
    only_yaml = set(yaml_keyed) - set(json_keyed)
    only_json = set(json_keyed) - set(yaml_keyed)
    if only_yaml:
        diffs.append(f"  work items in YAML only: {sorted(only_yaml)}")
    if only_json:
        diffs.append(f"  work items in JSON only: {sorted(only_json)}")

    for wid in sorted(set(yaml_keyed) & set(json_keyed)):
        if yaml_keyed[wid] != json_keyed[wid]:
            changed = [
                f for f, y, j in zip(_ROUTABLE_FIELDS, yaml_keyed[wid], json_keyed[wid]) if y != j
            ]
            diffs.append(f"  {wid}: fields differ: {changed}")

    if diffs:
        parts = [
            f"implementation catalog drift detected between {yaml_path} (canonical) and {json_path} (compat projection)",
            *diffs,
            "Regenerate the JSON projection from the YAML source to resolve.",
        ]
        raise ValueError("\n".join(parts))


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
    workstream_catalog: str | None,
) -> dict[str, str]:
    explicit_catalog = str(workstream_catalog or catalog or "").strip()
    if explicit_catalog:
        workstream_catalog_path = Path(explicit_catalog)
    else:
        workstream_catalog_path = DEFAULT_DA_WORKSTREAM_CATALOG
    workstream_resolved = _resolve_sa_or_da(
        role="da",
        selector_id=selector_id,
        catalog_path=workstream_catalog_path,
        list_key="workstreams",
        selector_key="workstream_id",
        repo_url_key="workstream_repo_url",
        allow_inactive=allow_inactive,
    )
    payload = _load_yaml(workstream_catalog_path)
    items = _as_items(payload, "workstreams", workstream_catalog_path)
    matches = _match_selector(
        items=items,
        selector_id=selector_id,
        keys=["workstream_id"],
    )
    selected = matches[0]
    workstream_resolved["OPENARCHITECT_SELECTOR_KIND"] = "workstream"
    workstream_resolved["OPENARCHITECT_ACTIVE_WORKSTREAM_ID"] = str(
        selected.get("workstream_id") or selector_id
    ).strip()
    domain_id = str(selected.get("domain_id") or "").strip()
    initiative_id = str(selected.get("initiative_id") or "").strip()
    handoff_ref = str(selected.get("handoff_ref") or "").strip()
    if domain_id:
        workstream_resolved["OPENARCHITECT_ACTIVE_DOMAIN_ID"] = domain_id
    if initiative_id:
        workstream_resolved["OPENARCHITECT_ACTIVE_INITIATIVE_ID"] = initiative_id
    if handoff_ref:
        workstream_resolved["OPENARCHITECT_ACTIVE_HANDOFF_REF"] = handoff_ref
    return workstream_resolved


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
    description = _as_str(meta_obj.get("description") or selected.get("description"))
    resolved["OPENARCHITECT_ACTIVE_INITIATIVE_DESCRIPTION"] = description
    objectives = _as_list_of_str(meta_obj.get("objectives") or selected.get("objectives"))
    if objectives:
        resolved["OPENARCHITECT_ACTIVE_INITIATIVE_OBJECTIVES_JSON"] = json.dumps(
            objectives, ensure_ascii=True, sort_keys=False
        )
    metadata_clean = {
        str(key): value
        for key, value in meta_obj.items()
        if isinstance(key, str) and key.strip()
    }
    resolved["OPENARCHITECT_ACTIVE_INITIATIVE_CONTEXT_JSON"] = json.dumps(
        {
            "initiative_id": _as_str(selected.get("initiative_id") or selector_id),
            "name": _as_str(selected.get("name")),
            "description": description,
            "objectives": objectives,
            "owner": _as_str(selected.get("owner")),
            "solution_repo_url": _as_str(selected.get("solution_repo_url")),
            "status": _as_str(selected.get("status")),
            "metadata": metadata_clean,
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
    payload, resolved_path = _load_catalog(implementation_catalog_path)
    # work_items is the canonical YAML key; implementation_work_items is the JSON compatibility key.
    items_key = "work_items" if "work_items" in payload else "implementation_work_items"
    items = _as_items(payload, items_key, resolved_path)
    matches = _match_selector(items=items, selector_id=selector_id, keys=["work_item_id", "api_id"])
    if not matches:
        raise ValueError(f"dev: selector_id '{selector_id}' not found in {resolved_path}")
    if len(matches) > 1:
        raise ValueError(f"dev: selector_id '{selector_id}' is ambiguous in {resolved_path}")
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
        return str(os.getenv("WORKSTREAM_ID") or "").strip()
    return str(os.getenv("WORK_ITEM_ID") or os.getenv("API_ID") or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve OPENARCHITECT_GIT_REPO_URL and related env vars from selector manifests."
    )
    parser.add_argument("--role", choices=["sa", "da", "dev"], required=True)
    parser.add_argument(
        "--selector-id",
        default=None,
        help="Initiative/workstream/work-item/API selector.",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help=(
            "Primary selector catalog path. Defaults: SA=architecture/portfolio/initiatives.yml, "
            "DA=architecture/solution/domain-workstreams.yml."
        ),
    )
    parser.add_argument(
        "--da-workstream-catalog",
        default=None,
        help=(
            "DA workstream catalog path "
            "(default: architecture/solution/domain-workstreams.yml)."
        ),
    )
    parser.add_argument(
        "--implementation-catalog",
        default="implementation-catalog.yml",
        help=(
            "Implementation catalog path for dev role "
            "(default: implementation-catalog.yml; auto-falls back to .json if .yml is absent, or to .yml/.yaml if .json is absent)."
        ),
    )
    parser.add_argument("--git-workdir", default=None, help="In-container git workdir.")
    parser.add_argument("--allow-inactive", action="store_true", help="Allow non-active selector entries.")
    parser.add_argument("--output", choices=["export", "env", "json"], default="export")
    args = parser.parse_args()

    selector_id = str(args.selector_id or _default_selector_id(args.role)).strip()
    if not selector_id:
        env_hint = {
            "sa": "INITIATIVE_ID",
            "da": "WORKSTREAM_ID",
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
                workstream_catalog=args.da_workstream_catalog,
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




