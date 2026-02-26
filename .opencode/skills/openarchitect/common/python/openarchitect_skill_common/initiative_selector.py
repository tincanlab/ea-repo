from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SELECTOR_STATUSES = {
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


@dataclass
class InitiativeSelectorBuildResult:
    payload: dict[str, Any]
    selected_ids: list[str]
    skipped_ids: list[str]
    errors: list[str]


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _as_str(value).lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_status(value: Any) -> str:
    status = _as_str(value).lower() or "planned"
    return status


def load_yaml_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected YAML object")
    return payload


def write_yaml_payload(path: Path, payload: dict[str, Any]) -> None:
    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
        width=88,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _selector_metadata_row(item: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        "stage",
        "t_shirt_size",
        "roi_band",
        "business_sponsor",
        "pm_owner",
        "it_owner",
        "business_case_id",
    ):
        value = _as_str(item.get(key))
        if value:
            metadata[key] = value
    description = _as_str(item.get("description"))
    if description:
        metadata["description"] = description
    objectives = item.get("objectives")
    if isinstance(objectives, list):
        cleaned: list[str] = []
        for raw in objectives:
            text = _as_str(raw)
            if text:
                cleaned.append(text)
        if cleaned:
            metadata["objectives"] = cleaned
    item_metadata = item.get("metadata")
    if isinstance(item_metadata, dict):
        for key, value in item_metadata.items():
            if key not in metadata:
                metadata[key] = value
    return metadata


def build_selector_from_pipeline_payload(
    pipeline_payload: dict[str, Any],
) -> InitiativeSelectorBuildResult:
    items = pipeline_payload.get("initiatives")
    if not isinstance(items, list):
        raise ValueError("initiative pipeline must define top-level initiatives[]")

    errors: list[str] = []
    selected: list[dict[str, Any]] = []
    selected_ids: list[str] = []
    skipped_ids: list[str] = []

    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            errors.append(f"initiatives[{index}]: expected mapping")
            continue

        initiative_id = _as_str(raw.get("initiative_id"))
        if not initiative_id:
            errors.append(f"initiatives[{index}]: missing initiative_id")
            continue

        routing = raw.get("routing")
        routing_obj = routing if isinstance(routing, dict) else {}
        publish_to_selector = _as_bool(
            routing_obj.get("publish_to_selector"), default=False
        )
        if not publish_to_selector:
            skipped_ids.append(initiative_id)
            continue

        solution_repo_url = _as_str(raw.get("solution_repo_url"))
        if not solution_repo_url:
            errors.append(
                f"initiatives[{index}] ({initiative_id}): publish_to_selector=true "
                "requires solution_repo_url"
            )
            continue

        selector_status = _normalize_status(
            routing_obj.get("selector_status") or raw.get("status")
        )
        if selector_status not in SELECTOR_STATUSES:
            allowed = ", ".join(sorted(SELECTOR_STATUSES))
            errors.append(
                f"initiatives[{index}] ({initiative_id}): invalid selector_status "
                f"'{selector_status}' (allowed: {allowed})"
            )
            continue

        selector_row: dict[str, Any] = {
            "initiative_id": initiative_id,
            "solution_repo_url": solution_repo_url,
            "status": selector_status,
        }
        name = _as_str(raw.get("name"))
        if name:
            selector_row["name"] = name
        owner = _as_str(raw.get("it_owner")) or _as_str(raw.get("pm_owner"))
        if owner:
            selector_row["owner"] = owner
        metadata = _selector_metadata_row(raw)
        if metadata:
            selector_row["metadata"] = metadata

        selected.append(selector_row)
        selected_ids.append(initiative_id)

    selected.sort(key=lambda row: _as_str(row.get("initiative_id")))
    payload: dict[str, Any] = {
        "version": _as_str(pipeline_payload.get("version")) or "1.0",
        "initiatives": selected,
    }
    return InitiativeSelectorBuildResult(
        payload=payload,
        selected_ids=selected_ids,
        skipped_ids=skipped_ids,
        errors=errors,
    )


def build_selector_from_pipeline_path(pipeline_path: Path) -> InitiativeSelectorBuildResult:
    payload = load_yaml_payload(pipeline_path)
    return build_selector_from_pipeline_payload(payload)


def _normalized_selector_for_compare(payload: dict[str, Any]) -> dict[str, Any]:
    version = _as_str(payload.get("version"))
    initiatives = payload.get("initiatives")
    if not isinstance(initiatives, list):
        initiatives = []

    normalized_items: list[dict[str, Any]] = []
    for row in initiatives:
        if not isinstance(row, dict):
            continue
        normalized_items.append(row)

    normalized_items.sort(key=lambda row: _as_str(row.get("initiative_id")))
    return {"version": version, "initiatives": normalized_items}


def selector_payloads_equal(
    *,
    expected_payload: dict[str, Any],
    actual_payload: dict[str, Any],
) -> bool:
    return _normalized_selector_for_compare(expected_payload) == _normalized_selector_for_compare(
        actual_payload
    )
