# MCP Schema Catalog Workflow

Purpose: generate `mcp-catalog.json` for `tmf-domain-architect` when local OpenAPI schema coverage is incomplete.

## Inputs

1. ODA component YAML (for example `TMFC005-ProductInventory.yaml`)
2. Trace exports from registered TMF MCP tools, typically:
   - `mcp__tmf-mcp__trace_api_schema_chain` per API (`TMF620`, `TMF637`, etc.)
3. Canonical schema root:
   - default `C:/Projects/vector_service/data/schemas-candidates`

## Step 1: Export MCP traces

Export one trace JSON per API. Recommended file naming:
1. `trace-TMF620.json`
2. `trace-TMF637.json`
3. etc.

Accepted payload shapes in each file:
1. Raw object with `api` + `schema_links`
2. Wrapper object with `result` containing JSON string/object

## Step 2: Build catalog

Run:

```bash
python scripts/build_mcp_schema_catalog.py \
  --component-spec <tmfc-component.yaml> \
  --trace-json-dir <trace-export-dir> \
  --out <mcp-catalog.json>
```

Optional flags:
1. `--api-id TMF637` (repeatable) to restrict APIs
2. `--min-confidence 0.85` to ignore weak links
3. `--schema-root <path>` when canonical schema root differs

## Step 3: Use catalog in design generation

Run:

```bash
python scripts/build_tmf_design_package.py \
  --component-name <component_name> \
  --spec <tmfc-component.yaml> \
  --out <implementation-catalog.json> \
  --summary-md <design-summary.md> \
  --ddl-sql <database.sql> \
  --use-mcp \
  --mcp-schema-catalog <mcp-catalog.json>
```

## Output contract

`mcp-catalog.json` contains:
1. `catalog[]` entries keyed by API (`api_id`, `tmf_number`)
2. `schemas` map (schema name -> full JSON schema payload)
3. provenance fields (`source_tool`, `trace_files`)
4. unresolved schema links for audit (`unresolved_links`)

## Notes

1. `build_mcp_schema_catalog.py` does not call MCP tools directly; it normalizes exported MCP results.
2. This keeps CI runs deterministic while still leveraging registered MCP tools for schema discovery.
