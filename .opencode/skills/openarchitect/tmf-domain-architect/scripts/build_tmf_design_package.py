#!/usr/bin/env python3
"""Build a multi-API TMF design package for downstream service generation."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    value = value.strip("_").lower()
    return value or "entity"


def _singularize(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("ses") and len(value) > 3:
        return value[:-2]
    if value.endswith("s") and not value.endswith("ss") and len(value) > 1:
        return value[:-1]
    return value


def _canonical_entity(resource_name: str) -> str:
    return _singularize(_snake_case(resource_name))


def _tmf_number_from_text(*parts: str) -> str | None:
    for part in parts:
        text = (part or "").strip()
        match = re.search(r"TMF(\d+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        plain_digits = re.fullmatch(r"(\d{3,4})", text)
        if plain_digits:
            return plain_digits.group(1)
        prefixed_digits = re.fullmatch(r"tmf[_-]?(\d{3,4})", text, flags=re.IGNORECASE)
        if prefixed_digits:
            return prefixed_digits.group(1)
    return None


def _supports_from_methods(collection_methods: List[str], item_methods: List[str]) -> Dict[str, bool]:
    return {
        "list": "get" in collection_methods,
        "create": "post" in collection_methods,
        "get": "get" in item_methods,
        "patch": "patch" in item_methods,
        "put": "put" in item_methods,
        "delete": "delete" in item_methods,
    }


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
        if not parts or parts[0].startswith("{"):
            skipped_paths.append(raw_path)
            continue

        methods = [m for m in HTTP_METHODS if isinstance(path_item.get(m), dict)]
        if not methods:
            continue

        resource_name = parts[0]
        entry = resource_map.setdefault(
            resource_name,
            {"name": resource_name, "collection_methods": set(), "item_methods": set()},
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
        supports = _supports_from_methods(collection_methods, item_methods)
        name = value["name"]
        resources.append(
            {
                "name": name,
                "canonical_entity": _canonical_entity(name),
                "collection_methods": collection_methods,
                "item_methods": item_methods,
                "supports": supports,
            }
        )

    return resources, sorted(set(skipped_paths)), has_hub


def _api_id(tmf_number: str | None, title: str, stem: str) -> str:
    if tmf_number and tmf_number != "unknown":
        return f"tmf{tmf_number}"
    base = _snake_case(title or stem)
    return base[:48]


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _load_yaml_or_json(path: Path) -> Dict[str, Any] | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _is_openapi_doc(raw: Dict[str, Any]) -> bool:
    return isinstance(raw.get("paths"), dict) and (
        "openapi" in raw or "swagger" in raw or isinstance(raw.get("components"), dict)
    )


def _discover_openapi_candidates(specs: List[Path], catalog_dirs: List[Path]) -> Dict[str, Path]:
    candidates: Dict[str, Path] = {}

    def add_candidate(path: Path) -> None:
        raw = _load_yaml_or_json(path)
        if not raw or not _is_openapi_doc(raw):
            return
        tmf_number = _tmf_number_from_text(path.name, str(raw.get("info", {}).get("title", "")))
        if tmf_number and tmf_number not in candidates:
            candidates[tmf_number] = path

    for path in specs:
        if path.exists():
            add_candidate(path)
    for directory in catalog_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            add_candidate(path)
    return candidates


def _coerce_schema_map(payload: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(payload, dict):
        components = payload.get("components")
        if isinstance(components, dict):
            schemas = components.get("schemas")
            if isinstance(schemas, dict):
                return {str(k): v for k, v in schemas.items() if isinstance(v, dict)}

        schemas = payload.get("schemas")
        if isinstance(schemas, dict):
            return {str(k): v for k, v in schemas.items() if isinstance(v, dict)}
        if isinstance(schemas, list):
            out: Dict[str, Dict[str, Any]] = {}
            for item in schemas:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("schema_name")
                if isinstance(name, str) and name.strip():
                    out[name.strip()] = item
            return out

        likely_map = {
            str(k): v
            for k, v in payload.items()
            if isinstance(v, dict) and any(key in v for key in ("type", "properties", "allOf", "$ref"))
        }
        if likely_map:
            return likely_map
    return {}


def _load_mcp_schema_catalogs(catalog_paths: List[Path]) -> Tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, str]]:
    catalog: Dict[str, Dict[str, Dict[str, Any]]] = {}
    sources: Dict[str, str] = {}
    for path in catalog_paths:
        raw = _load_yaml_or_json(path)
        if not raw:
            continue

        entries: List[Tuple[str | None, Dict[str, Any]]] = []
        embedded_apis = raw.get("apis")
        if isinstance(embedded_apis, list):
            for item in embedded_apis:
                if isinstance(item, dict):
                    entries.append((None, item))

        embedded_catalog = raw.get("catalog")
        if isinstance(embedded_catalog, list):
            for item in embedded_catalog:
                if isinstance(item, dict):
                    entries.append((None, item))

        if not entries:
            for key, value in raw.items():
                if not isinstance(value, dict):
                    continue
                entries.append((str(key), value))

        for fallback_key, entry in entries:
            tmf_number = _tmf_number_from_text(
                str(entry.get("tmf_number", "")),
                str(entry.get("api_id", "")),
                str(entry.get("title", "")),
                str(fallback_key or ""),
            )
            if not tmf_number:
                continue
            schema_map = _coerce_schema_map(entry)
            if not schema_map:
                continue
            if tmf_number not in catalog:
                catalog[tmf_number] = schema_map
                source = entry.get("source") or entry.get("source_tool") or str(path)
                sources[tmf_number] = str(source)
    return catalog, sources


def _resolve_ref_schema(
    schema_map: Dict[str, Dict[str, Any]], schema: Dict[str, Any] | None
) -> Dict[str, Any] | None:
    if not isinstance(schema, dict):
        return None
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.split("/")[-1]
        return schema_map.get(name)
    return schema


def _collect_schema_properties(
    schema_map: Dict[str, Dict[str, Any]], schema_name: str
) -> List[Dict[str, Any]]:
    visited: set[str] = set()

    def walk(schema: Dict[str, Any] | None) -> Dict[str, Dict[str, Any]]:
        if not isinstance(schema, dict):
            return {}
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            name = ref.split("/")[-1]
            if name in visited:
                return {}
            visited.add(name)
            return walk(schema_map.get(name))

        merged: Dict[str, Dict[str, Any]] = {}
        for sub in schema.get("allOf", []) if isinstance(schema.get("allOf"), list) else []:
            if isinstance(sub, dict):
                for key, value in walk(sub).items():
                    merged[key] = value

        properties = schema.get("properties")
        required = set(schema.get("required", [])) if isinstance(schema.get("required"), list) else set()
        if isinstance(properties, dict):
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    continue
                prop_ref = prop_schema.get("$ref")
                ref_name = None
                if isinstance(prop_ref, str) and prop_ref.startswith("#/components/schemas/"):
                    ref_name = prop_ref.split("/")[-1]
                p_type = prop_schema.get("type")
                merged[prop_name] = {
                    "name": prop_name,
                    "type": str(p_type) if p_type is not None else None,
                    "format": prop_schema.get("format"),
                    "required": prop_name in required,
                    "ref_schema": ref_name,
                }
        return merged

    root = schema_map.get(schema_name)
    props = walk(root)
    return sorted(props.values(), key=lambda p: p["name"])


def _find_resource_schema_name(resource_name: str, schema_map: Dict[str, Dict[str, Any]]) -> str | None:
    if not schema_map:
        return None

    by_norm = {_normalized_name(name): name for name in schema_map.keys()}
    base = resource_name.strip()
    candidates = [
        base,
        base[:1].upper() + base[1:],
        _singularize(base),
        _singularize(base[:1].upper() + base[1:]),
    ]
    normalized_candidates = []
    for candidate in candidates:
        normalized_candidates.append(_normalized_name(candidate))
        normalized_candidates.append(_normalized_name(candidate + "_FVO"))
        normalized_candidates.append(_normalized_name(candidate + "_MVO"))
    for item in normalized_candidates:
        if item in by_norm:
            return by_norm[item]
    return None


def _apply_schema_map_to_api(
    api: Dict[str, Any],
    schema_map: Dict[str, Dict[str, Any]],
    schema_source: str,
) -> int:
    matched = 0
    for resource in api.get("resources", []):
        if not isinstance(resource, dict):
            continue
        if resource.get("schema_name"):
            continue
        schema_name = _find_resource_schema_name(str(resource.get("name", "")), schema_map)
        if not schema_name:
            continue
        props = _collect_schema_properties(schema_map, schema_name)
        resource["schema_name"] = schema_name
        resource["schema_source"] = schema_source
        resource["schema_properties"] = props
        resource["schema_properties_count"] = len(props)
        matched += 1
    return matched


def _refresh_schema_enrichment_status(apis: List[Dict[str, Any]]) -> None:
    for api in apis:
        resources = api.get("resources", []) if isinstance(api.get("resources"), list) else []
        resource_total = len(resources)
        resource_matches = 0
        mcp_matches = 0
        sources: List[str] = []
        seen_sources: set[str] = set()

        for resource in resources:
            if not isinstance(resource, dict):
                continue
            if resource.get("schema_name"):
                resource_matches += 1
                source = str(resource.get("schema_source") or "")
                if source and source not in seen_sources:
                    seen_sources.add(source)
                    sources.append(source)
                if source.startswith("mcp:"):
                    mcp_matches += 1

        if resource_matches == 0:
            status = "not_found"
            source_mode = "none"
        elif resource_matches < resource_total:
            status = "partial"
            source_mode = "mixed" if len(sources) > 1 else ("mcp_only" if mcp_matches else "openapi_only")
        else:
            status = "enriched"
            source_mode = "mixed" if len(sources) > 1 else ("mcp_only" if mcp_matches else "openapi_only")

        openapi_file = None
        for source in sources:
            if not source.startswith("mcp:"):
                openapi_file = source
                break

        api["schema_enrichment"] = {
            "status": status,
            "resource_matches": resource_matches,
            "resource_total": resource_total,
            "mcp_resource_matches": mcp_matches,
            "source_mode": source_mode,
            "source": sources[0] if sources else None,
            "sources": sources,
            "openapi_file": openapi_file,
        }


def _enrich_apis_with_openapi_schemas(apis: List[Dict[str, Any]], openapi_candidates: Dict[str, Path]) -> None:
    schema_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for api in apis:
        tmf_number = str(api.get("tmf_number") or "")
        openapi_path = openapi_candidates.get(tmf_number)
        if not openapi_path:
            continue

        cache_key = str(openapi_path)
        if cache_key not in schema_cache:
            raw = _load_yaml_or_json(openapi_path)
            components = raw.get("components") if isinstance(raw, dict) else {}
            schemas = components.get("schemas") if isinstance(components, dict) else {}
            schema_cache[cache_key] = schemas if isinstance(schemas, dict) else {}
        schema_map = schema_cache[cache_key]
        _apply_schema_map_to_api(api, schema_map, str(openapi_path))


def _enrich_apis_with_mcp_catalog(
    apis: List[Dict[str, Any]],
    mcp_catalog: Dict[str, Dict[str, Dict[str, Any]]],
    mcp_sources: Dict[str, str],
) -> None:
    for api in apis:
        tmf_number = str(api.get("tmf_number") or "")
        schema_map = mcp_catalog.get(tmf_number)
        if not schema_map:
            continue
        source = f"mcp:{mcp_sources.get(tmf_number, 'schema-catalog')}"
        _apply_schema_map_to_api(api, schema_map, source)


def _load_openapi_spec(raw: Dict[str, Any], spec_path: Path) -> List[Dict[str, Any]]:
    paths = raw.get("paths")
    if not isinstance(paths, dict):
        raise ValueError(f"Spec missing top-level 'paths': {spec_path}")

    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    title = str(info.get("title") or spec_path.stem)
    version = str(info.get("version") or "0.0.0")
    tmf_number = _tmf_number_from_text(spec_path.name, title) or "unknown"
    api_id = _api_id(tmf_number, title, spec_path.stem)
    resources, skipped_paths, has_hub = _collect_resources(paths)
    if not resources:
        raise ValueError(f"No top-level TMF resources found: {spec_path}")

    return [
        {
            "api_id": api_id,
            "tmf_number": tmf_number,
            "title": title,
            "version": version,
            "spec_path": str(spec_path),
            "resources": resources,
            "resource_count": len(resources),
            "skipped_paths": skipped_paths,
            "has_hub": has_hub,
            "source_type": "openapi",
        }
    ]


def _parse_component_api_resources(resources_field: Any) -> Tuple[List[Dict[str, Any]], bool]:
    if not isinstance(resources_field, list):
        return [], False

    parsed: List[Dict[str, Any]] = []
    has_hub = False

    for item in resources_field:
        if not isinstance(item, dict):
            continue
        for resource_name, methods_value in item.items():
            if not isinstance(resource_name, str):
                continue
            methods_raw = methods_value if isinstance(methods_value, list) else []
            collection_methods: set[str] = set()
            item_methods: set[str] = set()

            for entry in methods_raw:
                if not isinstance(entry, str):
                    continue
                text = entry.strip().lower()
                if not text:
                    continue
                parts = text.split()
                method = parts[0]
                if method not in HTTP_METHODS:
                    continue
                path_part = parts[1] if len(parts) > 1 else ""
                if "/id" in path_part or "{id}" in path_part:
                    item_methods.add(method)
                else:
                    collection_methods.add(method)

            if resource_name.lower() == "hub":
                has_hub = True

            collection_methods_sorted = sorted(collection_methods)
            item_methods_sorted = sorted(item_methods)
            parsed.append(
                {
                    "name": resource_name,
                    "canonical_entity": _canonical_entity(resource_name),
                    "collection_methods": collection_methods_sorted,
                    "item_methods": item_methods_sorted,
                    "supports": _supports_from_methods(collection_methods_sorted, item_methods_sorted),
                }
            )

    parsed = sorted(parsed, key=lambda r: str(r.get("name", "")).lower())
    return parsed, has_hub


def _load_oda_component_spec(raw: Dict[str, Any], spec_path: Path) -> List[Dict[str, Any]]:
    spec = raw.get("spec") if isinstance(raw.get("spec"), dict) else {}
    core_function = spec.get("coreFunction") if isinstance(spec.get("coreFunction"), dict) else {}
    dependent_apis = core_function.get("dependentAPIs")
    if not isinstance(dependent_apis, list):
        raise ValueError(f"Component YAML missing spec.coreFunction.dependentAPIs: {spec_path}")

    apis: List[Dict[str, Any]] = []
    for dep in dependent_apis:
        if not isinstance(dep, dict):
            continue
        dep_id = str(dep.get("id") or "").strip()
        dep_name = str(dep.get("name") or dep_id or "api").strip()
        tmf_number = _tmf_number_from_text(dep_id, dep_name) or "unknown"
        api_id = _api_id(tmf_number, dep_name, dep_name)
        resources, has_hub = _parse_component_api_resources(dep.get("resources"))
        if not resources:
            continue

        specifications = dep.get("specification") if isinstance(dep.get("specification"), list) else []
        first_spec = specifications[0] if specifications and isinstance(specifications[0], dict) else {}
        openapi_url = str(first_spec.get("url") or "").strip()
        version = str(first_spec.get("version") or "unknown")

        apis.append(
            {
                "api_id": api_id,
                "tmf_number": tmf_number,
                "title": dep_name,
                "version": version,
                "spec_path": str(spec_path),
                "openapi_url": openapi_url or None,
                "resources": resources,
                "resource_count": len(resources),
                "skipped_paths": [],
                "has_hub": has_hub,
                "source_type": "oda-component",
                "required": bool(dep.get("required", False)),
            }
        )

    if not apis:
        raise ValueError(f"No usable dependent APIs with resources in component YAML: {spec_path}")
    return apis


def _load_api_specs(spec_path: Path) -> List[Dict[str, Any]]:
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Spec did not parse into an object: {spec_path}")

    if isinstance(raw.get("paths"), dict):
        return _load_openapi_spec(raw, spec_path)

    kind = str(raw.get("kind") or "").strip().lower()
    api_version = str(raw.get("apiVersion") or "")
    if kind == "component" and api_version.startswith("oda.tmforum.org/"):
        return _load_oda_component_spec(raw, spec_path)

    raise ValueError(
        f"Unsupported spec format for {spec_path}; expected OpenAPI (paths) or ODA Component YAML (kind: Component)."
    )


def _dedupe_api_ids(apis: List[Dict[str, Any]]) -> None:
    seen: Dict[str, int] = {}
    for api in apis:
        base = str(api.get("api_id") or "api")
        count = seen.get(base, 0) + 1
        seen[base] = count
        if count > 1:
            api["api_id"] = f"{base}_{count}"


def _table_name_for_entity(canonical_entity: str) -> str:
    return f"ent_{_snake_case(canonical_entity)}"


def _sqlite_quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _build_database_design(
    apis: List[Dict[str, Any]], shared_entities: List[Dict[str, Any]], database_url: str
) -> Dict[str, Any]:
    entity_usage: Dict[str, Dict[str, set[str]]] = {}
    binding_rows: List[Dict[str, Any]] = []
    entity_schema_fields: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for api in apis:
        api_id = str(api.get("api_id"))
        for resource in api.get("resources", []):
            if not isinstance(resource, dict):
                continue
            resource_name = str(resource.get("name", "resource"))
            canonical_entity = str(resource.get("canonical_entity") or _canonical_entity(resource_name))
            usage = entity_usage.setdefault(canonical_entity, {"apis": set(), "resources": set()})
            usage["apis"].add(api_id)
            usage["resources"].add(resource_name)
            binding_rows.append(
                {
                    "api_id": api_id,
                    "resource_name": resource_name,
                    "canonical_entity": canonical_entity,
                    "table_name": _table_name_for_entity(canonical_entity),
                }
            )
            field_bucket = entity_schema_fields.setdefault(canonical_entity, {})
            for prop in resource.get("schema_properties", []) if isinstance(resource.get("schema_properties"), list) else []:
                if not isinstance(prop, dict):
                    continue
                prop_name = str(prop.get("name") or "").strip()
                if not prop_name:
                    continue
                field_bucket[prop_name] = prop

    shared_set = {str(item.get("canonical_entity")) for item in shared_entities if isinstance(item, dict)}
    entity_tables: List[Dict[str, Any]] = []
    ddl_blocks: List[str] = []

    for canonical_entity, usage in sorted(entity_usage.items(), key=lambda kv: kv[0]):
        table_name = _table_name_for_entity(canonical_entity)
        apis_for_entity = sorted(usage["apis"])
        resources_for_entity = sorted(usage["resources"])
        shared = canonical_entity in shared_set or len(apis_for_entity) > 1
        owner = apis_for_entity[0] if apis_for_entity else None

        columns = [
            {"name": "tmf_id", "type": "TEXT", "nullable": False, "pk": True},
            {"name": "payload", "type": "TEXT", "nullable": False, "notes": "JSON payload as text"},
            {"name": "source_api", "type": "TEXT", "nullable": False},
            {"name": "source_resource", "type": "TEXT", "nullable": False},
            {"name": "lifecycle_status", "type": "TEXT", "nullable": True},
            {"name": "version", "type": "TEXT", "nullable": True},
            {"name": "created_at", "type": "TEXT", "nullable": False, "default": "CURRENT_TIMESTAMP"},
            {"name": "updated_at", "type": "TEXT", "nullable": False, "default": "CURRENT_TIMESTAMP"},
        ]
        scalar_map = {"string": "TEXT", "integer": "INTEGER", "number": "REAL", "boolean": "INTEGER"}
        synthetic_cols: List[Tuple[str, str, bool, str]] = []
        for prop_name, meta in sorted(entity_schema_fields.get(canonical_entity, {}).items(), key=lambda kv: kv[0]):
            p_type = str(meta.get("type") or "").lower()
            if p_type not in scalar_map:
                continue
            if prop_name.lower() in ("id", "href"):
                continue
            col_name = f"attr_{_snake_case(prop_name)}"
            synthetic_cols.append((col_name, scalar_map[p_type], bool(meta.get("required", False)), prop_name))
        for col_name, col_type, required, source_name in synthetic_cols[:20]:
            columns.append(
                {
                    "name": col_name,
                    "type": col_type,
                    "nullable": not required,
                    "source_schema_field": source_name,
                }
            )
        indexes = [
            {"name": f"idx_{table_name}_source_api", "columns": ["source_api"]},
            {"name": f"idx_{table_name}_updated_at", "columns": ["updated_at"]},
            {"name": f"idx_{table_name}_lifecycle_status", "columns": ["lifecycle_status"]},
        ]
        entity_tables.append(
            {
                "table_name": table_name,
                "canonical_entity": canonical_entity,
                "shared_across_apis": shared,
                "owned_by_api": owner,
                "apis": apis_for_entity,
                "resources": resources_for_entity,
                "columns": columns,
                "indexes": indexes,
                "schema_field_count": len(entity_schema_fields.get(canonical_entity, {})),
            }
        )

        column_ddl_lines: List[str] = [
            '  "tmf_id" TEXT PRIMARY KEY,',
            '  "payload" TEXT NOT NULL,',
            '  "source_api" TEXT NOT NULL,',
            '  "source_resource" TEXT NOT NULL,',
            '  "lifecycle_status" TEXT,',
            '  "version" TEXT,',
            '  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,',
            '  "updated_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP',
        ]
        for idx, col in enumerate(synthetic_cols[:20]):
            col_name, col_type, required, _ = col
            suffix = "," if idx < len(synthetic_cols[:20]) - 1 else ""
            null_token = "NOT NULL" if required else ""
            mid = f'  "{col_name}" {col_type}'
            if null_token:
                mid = f"{mid} {null_token}"
            column_ddl_lines.append(mid + suffix)
        # Ensure commas for pre-existing base lines when synthetic columns were added.
        if synthetic_cols:
            for i in range(len(column_ddl_lines)):
                if i < len(column_ddl_lines) - 1 and not column_ddl_lines[i].endswith(","):
                    column_ddl_lines[i] = column_ddl_lines[i] + ","

        ddl_blocks.append(
            "\n".join(
                [
                    f"CREATE TABLE IF NOT EXISTS {_sqlite_quote(table_name)} (",
                    *column_ddl_lines,
                    ");",
                    f'CREATE INDEX IF NOT EXISTS {_sqlite_quote("idx_" + table_name + "_source_api")} ON {_sqlite_quote(table_name)} ("source_api");',
                    f'CREATE INDEX IF NOT EXISTS {_sqlite_quote("idx_" + table_name + "_updated_at")} ON {_sqlite_quote(table_name)} ("updated_at");',
                    f'CREATE INDEX IF NOT EXISTS {_sqlite_quote("idx_" + table_name + "_lifecycle_status")} ON {_sqlite_quote(table_name)} ("lifecycle_status");',
                ]
            )
        )

    support_tables = [
        {
            "table_name": "entity_links",
            "purpose": "Cross-entity references and relationships",
            "columns": [
                {"name": "id", "type": "INTEGER", "pk": True},
                {"name": "from_table", "type": "TEXT"},
                {"name": "from_id", "type": "TEXT"},
                {"name": "to_table", "type": "TEXT"},
                {"name": "to_id", "type": "TEXT"},
                {"name": "relation_type", "type": "TEXT"},
                {"name": "created_at", "type": "TEXT", "default": "CURRENT_TIMESTAMP"},
            ],
        },
        {
            "table_name": "outbox_events",
            "purpose": "Transactional event outbox for hub/event publication",
            "columns": [
                {"name": "id", "type": "INTEGER", "pk": True},
                {"name": "entity_table", "type": "TEXT"},
                {"name": "entity_id", "type": "TEXT"},
                {"name": "event_type", "type": "TEXT"},
                {"name": "event_payload", "type": "TEXT"},
                {"name": "status", "type": "TEXT", "default": "'NEW'"},
                {"name": "created_at", "type": "TEXT", "default": "CURRENT_TIMESTAMP"},
            ],
        },
    ]

    ddl_blocks.append(
        "\n".join(
            [
                'CREATE TABLE IF NOT EXISTS "entity_links" (',
                '  "id" INTEGER PRIMARY KEY AUTOINCREMENT,',
                '  "from_table" TEXT NOT NULL,',
                '  "from_id" TEXT NOT NULL,',
                '  "to_table" TEXT NOT NULL,',
                '  "to_id" TEXT NOT NULL,',
                '  "relation_type" TEXT NOT NULL,',
                '  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP',
                ");",
                'CREATE TABLE IF NOT EXISTS "outbox_events" (',
                '  "id" INTEGER PRIMARY KEY AUTOINCREMENT,',
                '  "entity_table" TEXT NOT NULL,',
                '  "entity_id" TEXT NOT NULL,',
                '  "event_type" TEXT NOT NULL,',
                '  "event_payload" TEXT NOT NULL,',
                '  "status" TEXT NOT NULL DEFAULT \'NEW\',',
                '  "created_at" TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP',
                ");",
                'CREATE INDEX IF NOT EXISTS "idx_outbox_events_status" ON "outbox_events" ("status");',
                'CREATE INDEX IF NOT EXISTS "idx_outbox_events_entity" ON "outbox_events" ("entity_table", "entity_id");',
            ]
        )
    )

    return {
        "url": database_url,
        "shared": True,
        "engine": "sqlite",
        "strategy": "canonical entity tables shared across APIs, plus link and outbox tables",
        "entity_tables": entity_tables,
        "support_tables": support_tables,
        "api_resource_bindings": sorted(
            binding_rows, key=lambda b: (b["api_id"], b["resource_name"], b["canonical_entity"])
        ),
        "ddl_sqlite": "\n\n".join(ddl_blocks) + "\n",
    }


def build_design_package(
    component_name: str,
    specs: List[Path],
    out_path: Path,
    database_url: str,
    service_prefix: str | None,
    openapi_catalog_dirs: List[Path],
    enrich_schemas: bool,
    use_mcp: bool,
    mcp_schema_catalogs: List[Path],
) -> Dict[str, Any]:
    apis: List[Dict[str, Any]] = []
    for path in specs:
        apis.extend(_load_api_specs(path))
    _dedupe_api_ids(apis)
    if not apis:
        raise ValueError("No APIs discovered from input specs")
    if enrich_schemas:
        openapi_candidates = _discover_openapi_candidates(specs, openapi_catalog_dirs)
        _enrich_apis_with_openapi_schemas(apis, openapi_candidates)
    if use_mcp:
        mcp_catalog, mcp_sources = _load_mcp_schema_catalogs(mcp_schema_catalogs)
        _enrich_apis_with_mcp_catalog(apis, mcp_catalog, mcp_sources)
    _refresh_schema_enrichment_status(apis)

    canonical_index: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for api in apis:
        for resource in api["resources"]:
            canonical_index[resource["canonical_entity"]].append((api["api_id"], resource["name"]))

    shared_entities = []
    for canonical_entity, members in sorted(canonical_index.items(), key=lambda kv: kv[0]):
        api_ids = sorted({api_id for api_id, _ in members})
        if len(api_ids) < 2:
            continue
        shared_entities.append(
            {
                "canonical_entity": canonical_entity,
                "apis": api_ids,
                "resources": sorted({resource_name for _, resource_name in members}),
            }
        )

    prefix = _snake_case(service_prefix or component_name)
    for api in apis:
        api["service_name"] = f"{prefix}-{api['api_id']}-service"
        if api.get("source_type") == "openapi":
            api["spec_path_for_builder"] = api.get("spec_path")
        else:
            api["spec_path_for_builder"] = None

    jobs = [
        {
            "api_id": api["api_id"],
            "spec_path": api["spec_path"],
            "openapi_url": api.get("openapi_url"),
            "service_name": api["service_name"],
            "database_url": database_url,
            "design_package": str(out_path),
            "recommended_command": (
                "python .codex/skills/tmf-developer/scripts/scaffold_tmf_service.py "
                f"--spec \"{api.get('spec_path_for_builder') or '<openapi_spec_path_for_' + api['api_id'] + '>'}\" "
                "--out <service_out_dir> "
                f"--service-name \"{api['service_name']}\" "
                f"--database-url \"{database_url}\" "
                f"--implementation-catalog \"{out_path}\" "
                f"--design-api \"{api['api_id']}\""
            ),
        }
        for api in apis
    ]

    database_design = _build_database_design(apis, shared_entities, database_url)

    return {
        "component_name": component_name,
        "database": database_design,
        "apis": apis,
        "shared_entities": shared_entities,
        "implementation_work_items": jobs,
    }


def _build_summary_md(design: Dict[str, Any]) -> str:
    lines: List[str] = []
    db = design.get("database") if isinstance(design.get("database"), dict) else {}
    entity_tables = db.get("entity_tables") if isinstance(db.get("entity_tables"), list) else []
    support_tables = db.get("support_tables") if isinstance(db.get("support_tables"), list) else []
    apis = design.get("apis") if isinstance(design.get("apis"), list) else []
    enriched_api_count = 0
    mcp_enriched_api_count = 0
    for api in apis:
        if isinstance(api, dict):
            enrichment = api.get("schema_enrichment")
            if isinstance(enrichment, dict) and enrichment.get("status") == "enriched":
                enriched_api_count += 1
            if isinstance(enrichment, dict) and int(enrichment.get("mcp_resource_matches") or 0) > 0:
                mcp_enriched_api_count += 1
    lines.append(f"# TMF Design Summary: {design['component_name']}")
    lines.append("")
    lines.append(f"- Shared database: `{db.get('url', 'sqlite:///./tmf_component.db')}`")
    lines.append(f"- Database engine: `{db.get('engine', 'sqlite')}`")
    lines.append(f"- API count: `{len(design['apis'])}`")
    lines.append(f"- Schema-enriched APIs: `{enriched_api_count}`")
    lines.append(f"- MCP-enriched APIs: `{mcp_enriched_api_count}`")
    lines.append(f"- Shared entities: `{len(design['shared_entities'])}`")
    lines.append(f"- Entity tables: `{len(entity_tables)}`")
    lines.append(f"- Support tables: `{len(support_tables)}`")
    lines.append("")
    lines.append("## APIs")
    lines.append("")
    for api in design["apis"]:
        lines.append(f"- `{api['api_id']}` (TMF{api['tmf_number']}): {api['title']}")
        lines.append(f"  - Resources: {api['resource_count']}")
        lines.append(f"  - Service name: `{api['service_name']}`")
        if api.get("openapi_url"):
            lines.append(f"  - OpenAPI URL: `{api['openapi_url']}`")
        enrichment = api.get("schema_enrichment")
        if isinstance(enrichment, dict):
            lines.append(
                f"  - Schema enrichment: {enrichment.get('status')} ({enrichment.get('resource_matches', 0)}/{enrichment.get('resource_total', 0)} resources)"
            )
            lines.append(f"  - Enrichment mode: {enrichment.get('source_mode', 'none')}")
            if enrichment.get("source"):
                lines.append(f"  - Enrichment source: `{enrichment.get('source')}`")
    lines.append("")
    if design["shared_entities"]:
        lines.append("## Shared Entities")
        lines.append("")
        for item in design["shared_entities"]:
            lines.append(
                f"- `{item['canonical_entity']}`: apis={', '.join(item['apis'])}; resources={', '.join(item['resources'])}"
            )
        lines.append("")
    lines.append("## Database Design")
    lines.append("")
    lines.append(f"- Strategy: {db.get('strategy', 'n/a')}")
    lines.append("")
    if entity_tables:
        lines.append("### Entity Tables")
        lines.append("")
        for table in entity_tables:
            lines.append(
                f"- `{table.get('table_name')}` (`{table.get('canonical_entity')}`), shared={table.get('shared_across_apis')}, owner={table.get('owned_by_api')}"
            )
        lines.append("")
    if support_tables:
        lines.append("### Support Tables")
        lines.append("")
        for table in support_tables:
            lines.append(f"- `{table.get('table_name')}`: {table.get('purpose')}")
        lines.append("")
    ddl = db.get("ddl_sqlite")
    if isinstance(ddl, str) and ddl.strip():
        lines.append("### SQLite DDL")
        lines.append("")
        lines.append("```sql")
        lines.append(ddl.strip())
        lines.append("```")
        lines.append("")
    lines.append("## Service Builder Handoff")
    lines.append("")
    for job in design["implementation_work_items"]:
        lines.append(f"- `{job['api_id']}`")
        lines.append(f"  - `{job['recommended_command']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component-name", required=True, help="TMF component name")
    parser.add_argument(
        "--spec",
        action="append",
        required=True,
        help="TMF spec path (OpenAPI YAML/JSON or ODA Component YAML). Repeatable.",
    )
    parser.add_argument("--out", required=True, help="Output JSON design package path")
    parser.add_argument("--database-url", default="sqlite:///./tmf_component.db", help="Shared DB URL")
    parser.add_argument("--service-prefix", help="Service name prefix")
    parser.add_argument("--summary-md", help="Optional markdown summary output path")
    parser.add_argument("--ddl-sql", help="Optional path to write generated SQLite DDL")
    parser.add_argument(
        "--openapi-spec-dir",
        action="append",
        default=[],
        help="Directory to search for TMF OpenAPI files for schema enrichment (repeatable)",
    )
    parser.add_argument(
        "--enrich-schemas",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable OpenAPI schema enrichment for resource and DB design (default true)",
    )
    parser.add_argument(
        "--use-mcp",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable MCP-backed schema enrichment fallback using --mcp-schema-catalog inputs",
    )
    parser.add_argument(
        "--mcp-schema-catalog",
        action="append",
        default=[],
        help="Path to MCP schema catalog JSON/YAML generated from registered TMF MCP tools (repeatable)",
    )
    parser.add_argument(
        "--mcp-required",
        action="store_true",
        help="Fail when --use-mcp is enabled but no resources are enriched from MCP catalogs",
    )
    parser.add_argument(
        "--allow-inplace",
        action="store_true",
        help="Allow writing outputs in the same directory as input spec files (disabled by default)",
    )
    args = parser.parse_args()

    specs = [Path(item).resolve() for item in args.spec]
    missing = [str(path) for path in specs if not path.exists()]
    if missing:
        raise SystemExit(f"Spec files not found: {', '.join(missing)}")

    spec_dirs = {path.parent.resolve() for path in specs}
    output_targets = [Path(args.out).resolve()]
    if args.summary_md:
        output_targets.append(Path(args.summary_md).resolve())
    if args.ddl_sql:
        output_targets.append(Path(args.ddl_sql).resolve())
    if not args.allow_inplace:
        conflicting = sorted(
            {
                str(target)
                for target in output_targets
                if target.parent.resolve() in spec_dirs
            }
        )
        if conflicting:
            raise SystemExit(
                "Output paths must not be in the same directory as input specs. "
                "Choose a separate design output directory or pass --allow-inplace. "
                f"Conflicting targets: {', '.join(conflicting)}"
            )
    if args.use_mcp and not args.mcp_schema_catalog:
        raise SystemExit("--use-mcp requires at least one --mcp-schema-catalog path")
    mcp_catalog_paths = [Path(item).resolve() for item in args.mcp_schema_catalog]
    missing_mcp_catalogs = [str(path) for path in mcp_catalog_paths if not path.exists()]
    if missing_mcp_catalogs:
        raise SystemExit(f"MCP schema catalog files not found: {', '.join(missing_mcp_catalogs)}")

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    design = build_design_package(
        component_name=args.component_name,
        specs=specs,
        out_path=out_path,
        database_url=args.database_url,
        service_prefix=args.service_prefix,
        openapi_catalog_dirs=[Path(item).resolve() for item in args.openapi_spec_dir],
        enrich_schemas=bool(args.enrich_schemas),
        use_mcp=bool(args.use_mcp),
        mcp_schema_catalogs=mcp_catalog_paths,
    )

    if args.use_mcp and args.mcp_required:
        mcp_matches = 0
        for api in design.get("apis", []):
            if not isinstance(api, dict):
                continue
            enrichment = api.get("schema_enrichment")
            if not isinstance(enrichment, dict):
                continue
            mcp_matches += int(enrichment.get("mcp_resource_matches") or 0)
        if mcp_matches <= 0:
            raise SystemExit("--mcp-required was set, but no resources were enriched from MCP schema catalogs")

    out_path.write_text(json.dumps(design, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote design package: {out_path}")

    if args.summary_md:
        summary_path = Path(args.summary_md).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(_build_summary_md(design), encoding="utf-8")
        print(f"Wrote design summary: {summary_path}")

    if args.ddl_sql:
        ddl_path = Path(args.ddl_sql).resolve()
        ddl_path.parent.mkdir(parents=True, exist_ok=True)
        db = design.get("database") if isinstance(design.get("database"), dict) else {}
        ddl_sql = db.get("ddl_sqlite")
        if not isinstance(ddl_sql, str) or not ddl_sql.strip():
            raise SystemExit("No database.ddl_sqlite found in generated design package")
        ddl_path.write_text(ddl_sql, encoding="utf-8")
        print(f"Wrote SQLite DDL: {ddl_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
