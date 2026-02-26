#!/usr/bin/env python3
"""Summarize TMF OpenAPI specs for service implementation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _tmf_number_from_text(*parts: str) -> str | None:
    for part in parts:
        match = re.search(r"TMF(\d+)", part or "", flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _collect_resources(paths: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str], bool]:
    resource_map: Dict[str, Dict[str, Any]] = {}
    skipped_paths: List[str] = []
    has_hub = False

    for raw_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        if raw_path.startswith("/hub"):
            has_hub = True
            continue
        if not raw_path.startswith("/"):
            skipped_paths.append(raw_path)
            continue

        parts = [p for p in raw_path.split("/") if p]
        if not parts:
            skipped_paths.append(raw_path)
            continue
        if parts[0].startswith("{"):
            skipped_paths.append(raw_path)
            continue

        methods = [m for m in HTTP_METHODS if isinstance(path_item.get(m), dict)]
        if not methods:
            continue

        resource_name = parts[0]
        entry = resource_map.setdefault(
            resource_name,
            {
                "name": resource_name,
                "collection_path": f"/{resource_name}",
                "item_path": f"/{resource_name}/{{id}}",
                "collection_methods": set(),
                "item_methods": set(),
            },
        )

        if len(parts) == 1:
            entry["collection_methods"].update(methods)
        elif len(parts) >= 2 and parts[1].startswith("{"):
            entry["item_methods"].update(methods)
        else:
            skipped_paths.append(raw_path)

    resources: List[Dict[str, Any]] = []
    for _, value in sorted(resource_map.items(), key=lambda kv: kv[0]):
        collection_methods = sorted(value["collection_methods"])
        item_methods = sorted(value["item_methods"])
        supports = {
            "list": "get" in collection_methods,
            "create": "post" in collection_methods,
            "get": "get" in item_methods,
            "patch": "patch" in item_methods,
            "put": "put" in item_methods,
            "delete": "delete" in item_methods,
        }
        resources.append(
            {
                "name": value["name"],
                "collection_path": value["collection_path"],
                "item_path": value["item_path"],
                "collection_methods": collection_methods,
                "item_methods": item_methods,
                "supports": supports,
            }
        )

    return resources, sorted(set(skipped_paths)), has_hub


def inventory(spec: Dict[str, Any], spec_path: Path) -> Dict[str, Any]:
    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    resources, skipped_paths, has_hub = _collect_resources(paths)

    tmf_number = _tmf_number_from_text(spec_path.name, str(info.get("title", ""))) or "unknown"

    return {
        "title": info.get("title") or spec_path.stem,
        "version": info.get("version") or "0.0.0",
        "tmf_number": tmf_number,
        "servers": [s.get("url") for s in servers if isinstance(s, dict) and s.get("url")],
        "resource_count": len(resources),
        "has_hub": has_hub,
        "resources": resources,
        "skipped_paths": skipped_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="Path to OpenAPI YAML/JSON file")
    parser.add_argument("--out", help="Write output JSON to this file")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        raise SystemExit(f"Spec file not found: {spec_path}")

    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise SystemExit("Spec did not parse into an object")

    result = inventory(spec, spec_path)
    data = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(data, encoding="utf-8")
        print(f"Wrote inventory: {out_path}")
    else:
        print(data, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

