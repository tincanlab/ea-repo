---
name: tmf-mcp-builder
description: Build TM Forum (TMF) MCP servers from TMF OpenAPI specs (TMF6xx/7xx YAML). Use when you are given a TMF OpenAPI file and asked to (1) implement an MCP server exposing TMF operations as tools, (2) generate a mock TMF API server + client + MCP layer, or (3) standardize tool naming, create/update inputs, $ref/allOf handling, and /hub event-subscription patterns for TMF APIs.
---

## Description

Build TM Forum MCP servers from TMF OpenAPI specs (`TMF6xx`/`TMF7xx`).
Use this skill when you need one of two outcomes:

1. **Wrap a real TMF API**: implement an MCP server and HTTP client only.
2. **Generate a full dev sandbox**: implement a mock server, HTTP client, and MCP server.

This skill standardizes TMF tool naming, create/update input ergonomics, and OpenAPI schema handling (`$ref`, `allOf`, and optional `/hub` subscription endpoints).

## Inputs

Required inputs:
1. `tmf_spec_path`: path to TMF OpenAPI YAML/JSON file.
2. `tmf_number`: TMF API number used in naming and docs (example: `620`).
3. `output_dir`: target folder for generated/updated server code.
4. `product_shape`: one of `wrap-real-api` or `full-dev-sandbox`.

Optional inputs:
1. `transport`: `stdio` or `http` for MCP server exposure.
2. `include_hub`: boolean; implement `/hub` tools only when needed.
3. `implementation_mode`: `hand-build` or `llm-assisted`.
4. `include_eval_set`: boolean; generate read-only multi-tool evaluation prompts.

Supporting local assets and scripts:
1. `scripts/tmf_openapi_inventory.py`
2. `scripts/copy_tmf_commons.py`
3. `assets/tmf_commons/`
4. `references/resource-creation-guidelines.md`
5. `references/TMF_MCP_SERVER_CREATION_PROMPT_all-in-one.md`
6. `references/TMF_MCP_SERVER_CREATION_PROMPT_libraries.md`

## Actions

1. Inventory the TMF spec.
   - Parse base paths, resources, operations, and request schemas.
   - Run: `python scripts/tmf_openapi_inventory.py --spec <spec-file>`.
2. Select implementation shape and framework.
   - Use Python with official `mcp` SDK and `FastMCP`.
   - Decide `wrap-real-api` vs `full-dev-sandbox`.
3. Implement HTTP client.
   - Use `httpx.AsyncClient` with consistent timeouts and error handling.
   - Keep request/response handling predictable.
4. Implement mock server when `product_shape=full-dev-sandbox`.
   - Use in-memory storage with sample data.
   - Support list/get/create/patch/delete behavior.
   - If needed, copy shared utilities:
     `python scripts/copy_tmf_commons.py --dest <project-root>`.
5. Implement MCP server tools.
   - Tool naming format: `tmf{tmf_number}_{action}_{resource}`.
   - Standard actions: `list`, `get`, `create`, `patch` (or `update`), `delete`, `health_check`.
   - Ensure list pagination (`limit`, `offset` or cursor).
6. Apply TMF input ergonomics.
   - For `create_*` and `patch_*`, prefer field-level tool parameters.
   - Rebuild TMF JSON payload internally.
   - Follow `references/resource-creation-guidelines.md`.
7. Handle OpenAPI schema semantics.
   - Treat `$ref` resolution as mandatory.
   - Treat `allOf` merge as mandatory, including mixed `type: object` + `allOf`.
   - Prioritize full CRUD for main resources first (example: `/customer`, `/product`, `/service`).
8. Add optional `/hub` tools when required.
   - Keep create/get/delete subscription behavior consistent.
   - For mocks, keep subscription state in memory.
9. Produce delivery artifacts.
   - Create `README-TMF####.md` with overview, tools/endpoints, run instructions, and env vars.
   - Create `requirements.txt` in output folder:
     - `wrap-real-api`: at least `httpx`, `mcp`, `pyyaml`
     - `full-dev-sandbox`: at least `fastapi`, `uvicorn`, `httpx`, `mcp`, `pyyaml`
   - Optional: create 10 read-only, multi-tool evaluation prompts.

## Orchestration Logic

1. Validate required inputs and load the OpenAPI spec.
2. Run spec inventory to identify main resources and operation coverage.
3. Branch by `product_shape`:
   - If `wrap-real-api`:
     1. Build HTTP client.
     2. Build MCP server that proxies to real TMF API.
     3. Skip mock server and `tmf_commons` copy unless explicitly requested.
   - If `full-dev-sandbox`:
     1. Optionally copy `assets/tmf_commons`.
     2. Build mock TMF API server.
     3. Build HTTP client to target the mock.
     4. Build MCP server that proxies to mock API.
4. For each main resource, implement tools in CRUD order:
   - `list` -> `get` -> `create` -> `patch/update` -> `delete`.
5. For create/update operations:
   - expose field-level arguments
   - rebuild payload internally
   - validate required fields before making API calls
6. If `include_hub=true` or spec requires subscriptions, add `/hub` tools.
7. Finalize deliverables:
   - `README-TMF####.md`
   - `requirements.txt`
   - optional evaluation set

## Error Handling

1. Invalid or unreadable spec path:
   - Stop early with actionable message including expected file path format.
2. Spec parse failures (YAML/JSON):
   - Report parser error and offending location when available.
3. Missing required OpenAPI elements (`paths`, schemas, request bodies):
   - Continue with partial generation where possible.
   - Record gaps in `Notes & Assumptions`.
4. `$ref`/`allOf` resolution problems:
   - Return explicit unresolved references.
   - Do not silently generate incomplete request models.
5. Unsupported endpoint patterns:
   - Preserve intent with nearest supported behavior and document deviations.
6. Missing local assets/scripts:
   - Report missing path and fallback strategy.
   - Continue without optional components when feasible.
7. Runtime API errors (client/server):
   - Surface status code, endpoint, and concise reason.
   - Keep MCP tool errors actionable for users.

## Notes & Assumptions

1. Python is the implementation target; `FastMCP` is the default MCP framework.
2. `tmf_commons` is primarily for mock/sandbox implementations and is not mandatory for real API wrapping.
3. LLM-assisted generation is supported through prompt references in `references/`; this skill does not require a bundled `tmf_llm_agent.py`.
4. `/hub` endpoints are optional and should be implemented only when required by spec or use case.
5. Keep tool contracts stable; if a breaking tool input/output change is needed, document migration guidance in a `## Breaking Changes` section.




