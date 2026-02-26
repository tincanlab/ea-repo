#!/usr/bin/env python3
"""Build an MCP schema catalog JSON for tmf-domain-architect enrichment.

This script normalizes exported TMF MCP trace payloads into the
`--mcp-schema-catalog` format accepted by `build_tmf_design_package.py`.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml


def _normalize_tmf_api_id(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return text
    match = re.search(r"TMF(\d{3,4})", text, flags=re.IGNORECASE)
    if match:
        return f"TMF{match.group(1)}"
    if re.fullmatch(r"\d{3,4}", text):
        return f"TMF{text}"
    if re.fullmatch(r"tmf[_-]?\d{3,4}", text, flags=re.IGNORECASE):
        digits = re.sub(r"[^0-9]", "", text)
        return f"TMF{digits}"
    return text.upper()


def _tmf_number(api_id: str) -> Optional[str]:
    match = re.search(r"TMF(\d{3,4})", api_id or "", flags=re.IGNORECASE)
    return match.group(1) if match else None


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    trimmed = text.strip()
    if not trimmed.startswith("```"):
        return text
    lines = trimmed.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text


def _load_json_or_yaml(path: Path) -> Any:
    text = _strip_fences(_load_text(path))
    try:
        return json.loads(text)
    except Exception:
        return yaml.safe_load(text)


def _coerce_result_payload(obj: Any) -> Any:
    if isinstance(obj, dict) and "result" in obj:
        result = obj.get("result")
        if isinstance(result, str):
            text = _strip_fences(result)
            try:
                return json.loads(text)
            except Exception:
                try:
                    return yaml.safe_load(text)
                except Exception:
                    return {"raw_result": result}
        return result
    return obj


def _extract_api_id(payload: Dict[str, Any]) -> Optional[str]:
    api = payload.get("api")
    if isinstance(api, dict) and isinstance(api.get("api_id"), str):
        return _normalize_tmf_api_id(str(api["api_id"]))
    for key in ("api_id", "apiId"):
        value = payload.get(key)
        if isinstance(value, str):
            return _normalize_tmf_api_id(value)
    return None


def _iter_schema_links(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for key in ("schema_links", "links", "records"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item


def _extract_link_field(link: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        if key in link and link.get(key) is not None:
            return link.get(key)
    return None


def _normalize_schema_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _build_schema_file_index(schema_root: Path) -> Dict[Tuple[str, str], Path]:
    index: Dict[Tuple[str, str], Path] = {}
    if not schema_root.exists() or not schema_root.is_dir():
        return index
    for path in schema_root.rglob("*.schema.json"):
        if not path.is_file():
            continue
        domain = path.parent.name
        base = path.name[: -len(".schema.json")]
        key = (_normalize_schema_name(domain), _normalize_schema_name(base))
        index.setdefault(key, path)
    return index


def _resolve_schema_path(
    schema_root: Path,
    schema_index: Dict[Tuple[str, str], Path],
    domain: Optional[str],
    schema_name: str,
    source_path: Optional[str],
) -> Optional[Path]:
    if source_path:
        source = Path(source_path)
        if source.exists() and source.is_file():
            return source

    if domain:
        direct = schema_root / domain / f"{schema_name}.schema.json"
        if direct.exists() and direct.is_file():
            return direct

    key = (_normalize_schema_name(domain or ""), _normalize_schema_name(schema_name))
    if key in schema_index:
        return schema_index[key]

    # Domain is sometimes absent or inconsistent; try by schema name only.
    for (dom_key, name_key), path in schema_index.items():
        if name_key == _normalize_schema_name(schema_name):
            return path
    return None


def _load_component_apis(component_spec_path: Path) -> Dict[str, Dict[str, Any]]:
    payload = _load_json_or_yaml(component_spec_path)
    if not isinstance(payload, dict):
        raise ValueError(f"Component spec is not an object: {component_spec_path}")

    spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else {}
    core = spec.get("coreFunction") if isinstance(spec.get("coreFunction"), dict) else {}
    apis: Dict[str, Dict[str, Any]] = {}
    for field in ("dependentAPIs", "exposedAPIs"):
        api_list = core.get(field)
        if not isinstance(api_list, list):
            continue
        for item in api_list:
            if not isinstance(item, dict):
                continue
            api_id_raw = item.get("id")
            if not isinstance(api_id_raw, str):
                continue
            api_id = _normalize_tmf_api_id(api_id_raw)
            if not api_id:
                continue
            apis.setdefault(
                api_id,
                {
                    "api_id": api_id,
                    "name": item.get("name"),
                    "required": bool(item.get("required")),
                },
            )
    return apis


def _load_trace_payload(path: Path) -> Dict[str, Any]:
    raw = _load_json_or_yaml(path)
    payload = _coerce_result_payload(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"Trace payload must be an object: {path}")
    api_id = _extract_api_id(payload)
    if not api_id:
        raise ValueError(f"Trace payload missing api_id: {path}")
    return {"api_id": api_id, "payload": payload, "source_file": str(path)}


def _build_catalog_entry(
    api_id: str,
    trace_payloads: List[Dict[str, Any]],
    schema_root: Path,
    schema_index: Dict[Tuple[str, str], Path],
    source_tool: str,
    component_meta: Optional[Dict[str, Any]] = None,
    min_confidence: float = 0.0,
) -> Dict[str, Any]:
    schema_candidates: Dict[Tuple[str, str], Dict[str, Any]] = {}
    unresolved: List[Dict[str, Any]] = []
    trace_files: List[str] = []

    for trace in trace_payloads:
        payload = trace["payload"]
        trace_files.append(str(trace["source_file"]))
        for link in _iter_schema_links(payload):
            confidence_raw = _extract_link_field(link, "link_confidence", "confidence_score")
            confidence = 1.0
            if isinstance(confidence_raw, (float, int)):
                confidence = float(confidence_raw)
            if confidence < min_confidence:
                continue

            schema_name_raw = _extract_link_field(
                link,
                "canonical_schema_name",
                "to_schema_name",
                "schema_name",
                "operation_model_name",
                "api_schema_name",
            )
            if not isinstance(schema_name_raw, str) or not schema_name_raw.strip():
                continue
            schema_name = schema_name_raw.strip()

            domain_raw = _extract_link_field(link, "canonical_domain", "to_domain", "domain")
            domain = str(domain_raw).strip() if isinstance(domain_raw, str) and domain_raw.strip() else None

            source_path_raw = _extract_link_field(link, "to_source_path", "source_path")
            source_path = str(source_path_raw).strip() if isinstance(source_path_raw, str) and source_path_raw.strip() else None

            schema_lib_id = _extract_link_field(link, "schema_lib_id", "to_schema_lib_id", "schema_id")

            key = (_normalize_schema_name(domain or ""), schema_name)
            bucket = schema_candidates.setdefault(
                key,
                {
                    "schema_name": schema_name,
                    "domain": domain,
                    "schema_lib_ids": set(),
                    "source_paths": set(),
                },
            )
            if isinstance(schema_lib_id, (int, float)):
                bucket["schema_lib_ids"].add(int(schema_lib_id))
            if source_path:
                bucket["source_paths"].add(source_path)

    schemas: Dict[str, Any] = {}
    schema_index_rows: List[Dict[str, Any]] = []

    for (_, schema_name), meta in sorted(schema_candidates.items(), key=lambda item: item[1]["schema_name"].lower()):
        domain = meta.get("domain")
        source_path = next(iter(meta.get("source_paths") or []), None)
        resolved = _resolve_schema_path(
            schema_root=schema_root,
            schema_index=schema_index,
            domain=domain,
            schema_name=schema_name,
            source_path=source_path,
        )
        if not resolved:
            unresolved.append(
                {
                    "schema_name": schema_name,
                    "domain": domain,
                    "schema_lib_ids": sorted(meta["schema_lib_ids"]),
                    "source_paths": sorted(meta["source_paths"]),
                }
            )
            continue
        try:
            schema_payload = _load_json_or_yaml(resolved)
        except Exception as exc:
            unresolved.append(
                {
                    "schema_name": schema_name,
                    "domain": domain,
                    "schema_lib_ids": sorted(meta["schema_lib_ids"]),
                    "source_paths": sorted(meta["source_paths"]),
                    "error": f"failed_to_load_schema_file: {exc}",
                    "resolved_path": str(resolved),
                }
            )
            continue
        if not isinstance(schema_payload, dict):
            unresolved.append(
                {
                    "schema_name": schema_name,
                    "domain": domain,
                    "schema_lib_ids": sorted(meta["schema_lib_ids"]),
                    "source_paths": sorted(meta["source_paths"]),
                    "error": "schema_file_not_object",
                    "resolved_path": str(resolved),
                }
            )
            continue
        schemas[schema_name] = schema_payload
        schema_index_rows.append(
            {
                "schema_name": schema_name,
                "domain": domain,
                "schema_lib_ids": sorted(meta["schema_lib_ids"]),
                "source_path": str(resolved),
            }
        )

    entry: Dict[str, Any] = {
        "api_id": api_id,
        "tmf_number": _tmf_number(api_id),
        "source_tool": source_tool,
        "source": f"{source_tool}:{api_id}",
        "schemas": schemas,
        "schema_count": len(schemas),
        "schema_index": schema_index_rows,
        "trace_files": sorted(set(trace_files)),
        "unresolved_links": unresolved,
    }
    if component_meta:
        entry["title"] = component_meta.get("name")
        entry["required"] = bool(component_meta.get("required"))
    return entry


def build_catalog(
    trace_files: List[Path],
    out_path: Path,
    schema_root: Path,
    source_tool: str,
    component_spec: Optional[Path],
    explicit_api_ids: List[str],
    min_confidence: float,
) -> Dict[str, Any]:
    trace_by_api: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for path in trace_files:
        trace = _load_trace_payload(path)
        trace_by_api[trace["api_id"]].append(trace)

    component_apis: Dict[str, Dict[str, Any]] = {}
    if component_spec:
        component_apis = _load_component_apis(component_spec)

    api_filter = {_normalize_tmf_api_id(v) for v in explicit_api_ids if v}
    if component_apis:
        api_filter.update(component_apis.keys())
    if not api_filter:
        api_filter = set(trace_by_api.keys())

    schema_index = _build_schema_file_index(schema_root)
    catalog_rows: List[Dict[str, Any]] = []
    missing_trace_apis: List[str] = []

    for api_id in sorted(api_filter):
        traces = trace_by_api.get(api_id, [])
        if not traces:
            missing_trace_apis.append(api_id)
            continue
        row = _build_catalog_entry(
            api_id=api_id,
            trace_payloads=traces,
            schema_root=schema_root,
            schema_index=schema_index,
            source_tool=source_tool,
            component_meta=component_apis.get(api_id),
            min_confidence=min_confidence,
        )
        catalog_rows.append(row)

    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_tool": source_tool,
        "schema_root": str(schema_root),
        "trace_file_count": len(trace_files),
        "api_count": len(catalog_rows),
        "missing_trace_apis": missing_trace_apis,
        "catalog": catalog_rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace-json",
        action="append",
        default=[],
        help="Path to exported JSON/YAML from tmf-mcp trace tool calls (repeatable).",
    )
    parser.add_argument(
        "--trace-json-dir",
        help="Directory containing exported trace JSON/YAML files.",
    )
    parser.add_argument(
        "--component-spec",
        help="Optional ODA component YAML to derive API IDs (dependent/exposed APIs).",
    )
    parser.add_argument(
        "--api-id",
        action="append",
        default=[],
        help="Optional API ID filter (TMF###). Repeatable.",
    )
    parser.add_argument(
        "--schema-root",
        default="C:/Projects/vector_service/data/schemas-candidates",
        help="Root directory containing canonical schema files (default: C:/Projects/vector_service/data/schemas-candidates).",
    )
    parser.add_argument(
        "--source-tool",
        default="mcp__tmf-mcp__trace_api_schema_chain",
        help="Tool provenance label stored in output.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Minimum link confidence to include (default 0.0).",
    )
    parser.add_argument("--out", required=True, help="Output catalog JSON path.")
    args = parser.parse_args()

    trace_files: List[Path] = [Path(item).resolve() for item in args.trace_json]
    if args.trace_json_dir:
        trace_dir = Path(args.trace_json_dir).resolve()
        if not trace_dir.exists() or not trace_dir.is_dir():
            raise SystemExit(f"--trace-json-dir is not a directory: {trace_dir}")
        for path in sorted(trace_dir.rglob("*")):
            if path.suffix.lower() in (".json", ".yaml", ".yml"):
                trace_files.append(path.resolve())

    trace_files = sorted(set(trace_files))
    if not trace_files:
        raise SystemExit("Provide at least one trace payload using --trace-json or --trace-json-dir")

    missing_trace_files = [str(path) for path in trace_files if not path.exists()]
    if missing_trace_files:
        raise SystemExit(f"Trace files not found: {', '.join(missing_trace_files)}")

    component_spec = Path(args.component_spec).resolve() if args.component_spec else None
    if component_spec and not component_spec.exists():
        raise SystemExit(f"Component spec not found: {component_spec}")

    schema_root = Path(args.schema_root).resolve()
    if not schema_root.exists() or not schema_root.is_dir():
        raise SystemExit(f"Schema root not found or not directory: {schema_root}")

    output = build_catalog(
        trace_files=trace_files,
        out_path=Path(args.out).resolve(),
        schema_root=schema_root,
        source_tool=str(args.source_tool),
        component_spec=component_spec,
        explicit_api_ids=list(args.api_id),
        min_confidence=float(args.min_confidence),
    )

    print(f"Wrote MCP schema catalog: {Path(args.out).resolve()}")
    print(f"APIs in catalog: {output['api_count']}")
    missing = output.get("missing_trace_apis", [])
    if missing:
        print(f"Missing trace payloads for APIs: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
