# Design Package Schema

`implementation-catalog.json` is the contract between `tmf-domain-architect` and `tmf-developer`.

Top-level fields:
1. `component_name`: logical component/system name.
2. `database`: shared database policy.
   - `url`: default DB URL for generated services.
   - `shared`: whether APIs are intended to share a DB.
   - `engine`: database engine (`sqlite` by default).
   - `strategy`: textual strategy description.
   - `entity_tables`: logical entity tables (canonical entity -> table).
   - `support_tables`: link/outbox and other support tables.
   - `api_resource_bindings`: API resource to table bindings.
   - `ddl_sqlite`: generated SQLite DDL script string.
3. `apis`: per-API design entries.
4. `shared_entities`: canonical entities used by multiple APIs.
5. `implementation_work_items`: ready-to-run generation handoff entries.
6. `governance_signal` (optional): cascade/governance recommendation emitted by the skill.
   - `cascade_layer`: usually `domain_architecture` or `implementation`.
   - `cascade_recommendation`: `ready_for_review`, `remediation_required`, or `block_advancement`.
   - `remediation_status`: `none`, `pending`, or `complete`.
   - `note`: short governance summary.
7. `shared_entity_review_required` (optional boolean): true when heuristic shared-entity grouping requires explicit architect sign-off.

Per-API entry (`apis[]`):
1. `api_id`: stable ID used by `--design-api`.
2. `tmf_number`: TMF API number if discovered.
3. `title`, `version`, `spec_path`.
4. `source_type`: `openapi` or `oda-component`.
5. `openapi_url`: populated when the source is ODA Component YAML and URL is provided.
6. `resources`: resource inventory with:
   - `name`
   - `canonical_entity`
   - `collection_methods`
   - `item_methods`
   - `supports` (`list/create/get/patch/put/delete`)
7. `has_hub`: whether `/hub` endpoints exist.
8. `service_name`: recommended service name.
9. `schema_enrichment`: enrichment status + source OpenAPI file + resource match coverage.
   - `status`: `not_found`, `partial`, or `enriched`.
   - `resource_matches`, `resource_total`.
   - `mcp_resource_matches`: count enriched from MCP-derived catalogs.
   - `source_mode`: `none`, `openapi_only`, `mcp_only`, or `mixed`.
   - `source`: primary enrichment source.
   - `sources`: ordered unique source list.
   - `openapi_file`: first non-MCP source (backward-compatible field).
10. Resource-level enrichment fields (when available):
   - `schema_name`
   - `schema_source`
   - `schema_properties`
   - `schema_properties_count`

MCP schema catalog input (`--mcp-schema-catalog`):
1. Accepts JSON/YAML dictionaries containing one of:
   - `apis: [ ... ]` entries
   - `catalog: [ ... ]` entries
   - top-level map keyed by TMF identifier (`637`, `tmf637`, etc.)
2. Each entry should include:
   - TMF identity (`tmf_number` or equivalent text containing `TMF###`)
   - schema definitions (`schemas`, `components.schemas`, or schema-name keyed map)
   - optional provenance (`source`, `source_tool`)
3. Recommended builder:
   - `scripts/build_mcp_schema_catalog.py` using exported `trace_api_schema_chain` payloads.

Downstream use in `tmf-developer`:
1. `--implementation-catalog <path>`: load package metadata.
2. `--design-api <api_id>`: pick the API entry when multiple APIs exist.
3. If present, service generator can inherit:
   - shared `database.url`
   - API-specific `service_name`
   - API resource canonical entity annotations
