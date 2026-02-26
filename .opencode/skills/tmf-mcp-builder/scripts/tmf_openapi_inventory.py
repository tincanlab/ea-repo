#!/usr/bin/env python3
"""Summarize a TMF OpenAPI spec for MCP/server generation.

Outputs a compact JSON inventory that is useful for:
- Identifying main resources and CRUD coverage
- Choosing MCP tool names
- Deriving ergonomic create/patch input fields

Usage:
  python tmf_openapi_inventory.py --spec TMF629-Customer_Management-v5.0.1.oas.yaml
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def _resolve_ref(spec: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    if not ref.startswith("#/"):
        return None
    node: Any = spec
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


def _merge_allof(spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}

    def merge_into(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
        for key, value in src.items():
            if key == "properties" and isinstance(value, dict):
                dst.setdefault("properties", {})
                dst["properties"].update(value)
            elif key == "required" and isinstance(value, list):
                dst.setdefault("required", [])
                for item in value:
                    if item not in dst["required"]:
                        dst["required"].append(item)
            else:
                dst.setdefault(key, value)

    # Start with direct fields (so allOf can override where appropriate)
    merge_into(merged, schema)

    for sub in schema.get("allOf", []) if isinstance(schema.get("allOf"), list) else []:
        if not isinstance(sub, dict):
            continue
        if "$ref" in sub and isinstance(sub["$ref"], str):
            resolved = _resolve_ref(spec, sub["$ref"])
            if resolved:
                merge_into(merged, _merge_allof(spec, resolved))
                continue
        merge_into(merged, _merge_allof(spec, sub) if "allOf" in sub else sub)

    merged.pop("allOf", None)
    return merged


def _extract_fields(spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    if "$ref" in schema and isinstance(schema["$ref"], str):
        resolved = _resolve_ref(spec, schema["$ref"])
        if resolved:
            return _extract_fields(spec, resolved)

    if "allOf" in schema:
        schema = _merge_allof(spec, schema)

    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = schema.get("required") if isinstance(schema.get("required"), list) else []

    # Only top-level fields; nested objects are represented by name only.
    fields: List[Dict[str, Any]] = []
    for name, prop in properties.items():
        field_type = None
        if isinstance(prop, dict):
            field_type = prop.get("type")
            if not field_type and "$ref" in prop:
                field_type = prop["$ref"].split("/")[-1]
        fields.append({
            "name": name,
            "required": name in required,
            "type": field_type,
        })

    return {
        "type": schema.get("type"),
        "schema": schema.get("title") or schema.get("$id"),
        "required": required,
        "fields": sorted(fields, key=lambda f: (not f["required"], f["name"])),
    }


def _pick_json_schema(request_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    content = request_body.get("content") if isinstance(request_body.get("content"), dict) else None
    if not content:
        return None

    for ctype in ("application/json", "application/*+json", "*/*"):
        if ctype in content and isinstance(content[ctype], dict):
            schema = content[ctype].get("schema")
            return schema if isinstance(schema, dict) else None

    # fallback: first content entry
    for v in content.values():
        if isinstance(v, dict) and isinstance(v.get("schema"), dict):
            return v["schema"]

    return None


def _group_key(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else ""


def inventory(spec: Dict[str, Any]) -> Dict[str, Any]:
    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue

            entry: Dict[str, Any] = {
                "path": path,
                "method": method.upper(),
                "operationId": op.get("operationId"),
                "summary": op.get("summary") or op.get("description"),
            }

            if method in ("post", "put", "patch"):
                rb = op.get("requestBody") if isinstance(op.get("requestBody"), dict) else None
                if rb:
                    schema = _pick_json_schema(rb)
                    if schema:
                        entry["requestFields"] = _extract_fields(spec, schema)

            grouped[_group_key(path)].append(entry)

    # metadata
    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []

    return {
        "title": info.get("title"),
        "version": info.get("version"),
        "servers": [s.get("url") for s in servers if isinstance(s, dict) and s.get("url")],
        "resources": {
            k: sorted(v, key=lambda e: (e["path"], e["method"]))
            for k, v in sorted(grouped.items(), key=lambda kv: kv[0])
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="Path to OpenAPI YAML/JSON")
    parser.add_argument("--out", help="Write JSON to file instead of stdout")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise SystemExit("Spec did not parse to a JSON object")

    result = inventory(spec)
    data = json.dumps(result, indent=2, ensure_ascii=False)

    if args.out:
        Path(args.out).write_text(data + "\n", encoding="utf-8")
    else:
        print(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
