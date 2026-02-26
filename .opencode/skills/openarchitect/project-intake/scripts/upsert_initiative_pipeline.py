#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def _as_bool(value: str) -> bool:
    text = (value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    payload = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected YAML object")
    return payload


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    text = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
        width=88,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _non_empty(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _ensure_list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    if rows is None:
        rows = []
        payload[key] = rows
    if not isinstance(rows, list):
        raise ValueError(f"expected top-level '{key}' list")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(row)
    payload[key] = normalized
    return normalized


def _find_or_create_item(rows: list[dict[str, Any]], initiative_id: str) -> tuple[dict[str, Any], bool]:
    for row in rows:
        if str(row.get("initiative_id") or "").strip() == initiative_id:
            return row, False
    item: dict[str, Any] = {"initiative_id": initiative_id}
    rows.append(item)
    return item, True


def _set_if_present(target: dict[str, Any], key: str, value: str | None) -> None:
    normalized = _non_empty(value)
    if normalized is not None:
        target[key] = normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upsert one initiative row in architecture/portfolio/initiative-pipeline.yml"
    )
    parser.add_argument(
        "--pipeline",
        default="architecture/portfolio/initiative-pipeline.yml",
        help="Path to initiative pipeline YAML.",
    )
    parser.add_argument("--initiative-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument(
        "--objective",
        action="append",
        default=[],
        help="Repeatable objective line; provide at least one.",
    )
    parser.add_argument(
        "--objectives-json",
        default="[]",
        help='Optional JSON array of objective strings merged with --objective.',
    )
    parser.add_argument("--business-case-id")
    parser.add_argument("--business-sponsor")
    parser.add_argument("--pm-owner")
    parser.add_argument("--it-owner")
    parser.add_argument("--t-shirt-size")
    parser.add_argument("--roi-band")
    parser.add_argument("--solution-repo-url")
    parser.add_argument(
        "--publish-to-selector",
        default="false",
        help="true/false; default false",
    )
    parser.add_argument(
        "--selector-status",
        default="planned",
        help="status emitted into initiatives.yml when published",
    )
    parser.add_argument(
        "--metadata-json",
        default="{}",
        help='JSON object merged into initiative.metadata, e.g. {"target_release":"2026-Q4"}',
    )
    args = parser.parse_args(argv)

    try:
        pipeline_path = Path(args.pipeline).resolve()
        payload = _load_yaml(pipeline_path)
        initiatives = _ensure_list(payload, "initiatives")

        initiative_id = str(args.initiative_id).strip()
        if not initiative_id:
            raise ValueError("initiative_id is required")

        item, created = _find_or_create_item(initiatives, initiative_id)
        item["initiative_id"] = initiative_id
        item["name"] = str(args.name).strip()
        item["stage"] = str(args.stage).strip()
        item["description"] = str(args.description).strip()

        objectives_json_in = json.loads(args.objectives_json)
        if not isinstance(objectives_json_in, list):
            raise ValueError("--objectives-json must be a JSON array")
        objectives: list[str] = []
        for value in list(args.objective) + objectives_json_in:
            text = str(value or "").strip()
            if text:
                objectives.append(text)
        if not objectives:
            raise ValueError("at least one objective is required (--objective or --objectives-json)")
        item["objectives"] = objectives

        _set_if_present(item, "business_case_id", args.business_case_id)
        _set_if_present(item, "business_sponsor", args.business_sponsor)
        _set_if_present(item, "pm_owner", args.pm_owner)
        _set_if_present(item, "it_owner", args.it_owner)
        _set_if_present(item, "t_shirt_size", args.t_shirt_size)
        _set_if_present(item, "roi_band", args.roi_band)
        _set_if_present(item, "solution_repo_url", args.solution_repo_url)

        metadata_in = json.loads(args.metadata_json)
        if not isinstance(metadata_in, dict):
            raise ValueError("--metadata-json must be a JSON object")
        existing_metadata = item.get("metadata")
        metadata = existing_metadata if isinstance(existing_metadata, dict) else {}
        metadata.update(metadata_in)
        if metadata:
            item["metadata"] = metadata

        publish = _as_bool(args.publish_to_selector)
        routing = item.get("routing")
        routing_obj = routing if isinstance(routing, dict) else {}
        routing_obj["publish_to_selector"] = publish
        routing_obj["selector_status"] = str(args.selector_status).strip() or "planned"
        item["routing"] = routing_obj

        if "version" not in payload:
            payload["version"] = "1.0"

        _write_yaml(pipeline_path, payload)
        print(
            json.dumps(
                {
                    "ok": True,
                    "pipeline": str(pipeline_path),
                    "initiative_id": initiative_id,
                    "created": created,
                    "publish_to_selector": publish,
                },
                ensure_ascii=True,
            )
        )
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
