---
name: tmf-domain-architect
description: Design multi-API TM Forum components from TMF OpenAPI specs or ODA Component YAML files, including shared canonical entities, ownership boundaries, and shared database strategy. Use when one component exposes multiple TMF APIs (for example TMF620 + TMF637) and you need a design package before generating runnable services.
---

# TMF Domain Architect

## Overview

Create a component-level design package across multiple TMF APIs before implementation.

Critical caveat:
- Canonical shared-entity detection is heuristic and must be explicitly reviewed by architects before downstream service generation.

Primary outcomes:
1. `implementation-catalog.json` consumable by `tmf-developer`.
2. `design-summary.md` for architecture review and handoff.
3. Database design section (`database.entity_tables`, `database.support_tables`, `database.ddl_sqlite`) and optional `.sql` DDL.

## Repository Convention

- Primary scripts:
  - `scripts/build_tmf_design_package.py`
  - `scripts/build_mcp_schema_catalog.py`
- Core references:
  - `references/design-package-schema.md`
  - `references/mcp-schema-catalog-workflow.md`
- Keep outputs in a dedicated design output folder (for example `<project-root>/design-output/<component>/`) and not beside source specs.

## Inputs

Required:
1. `spec_paths`: TMF spec files (`--spec` repeated), each OpenAPI YAML/JSON or ODA Component YAML.
2. `component_name`: logical component/system name.
3. `output_path`: path to write `implementation-catalog.json`.

Optional:
1. `database_url`: shared DB URL for downstream scaffolds (default `sqlite:///./tmf_component.db`).
2. `service_prefix`: prefix for generated service names.
3. `summary_path`: optional markdown summary output path.
4. `ddl_sql_path`: optional path to write generated SQLite DDL SQL file.
5. `openapi_spec_dir`: optional directory (repeatable) to locate TMF OpenAPI files for schema enrichment.
6. `use_mcp`: enable MCP schema fallback (`--use-mcp`) when local OpenAPI specs are incomplete.
7. `mcp_schema_catalog_path`: catalog file(s) (`--mcp-schema-catalog`) from TMF MCP tool traces.
8. `mcp_required`: enforce MCP enrichment coverage (`--mcp-required`) for CI/quality gates.
9. `workspace_id` and target `cascade_layer` (optional; for governance signaling context only).

## Outputs (write to repo as separate files)

Core outputs:
- `implementation-catalog.json`
- `design-summary.md` (if requested)

Optional outputs:
- `<component>-ddl.sql` (or configured `ddl_sql_path`)
- MCP catalog JSON (`mcp-catalog.json`) when MCP enrichment workflow is used

## Context Platform Integration

Default mode is local multi-spec analysis with optional local OpenAPI enrichment.

Optional MCP servers:
- `tmf-mcp` (used to produce trace exports/catalog inputs for schema enrichment fallback)
- `openarchitect` (optional governance context: workspace/cascade reads)

MCP is optional. The bundled scripts consume catalog files and do not call MCP directly.
If `openarchitect` is available, use it only for governance context:
- `get_cascade_state(workspace_id)`
- `get_design_context(workspace_id, domain, level)` (or equivalent)

## Design Principles

- Component-first decomposition: model one logical component that may expose multiple APIs.
- Shared-entity discipline: identify canonical entities reused across APIs and define ownership boundaries.
- Deterministic enrichment order: local OpenAPI evidence first, MCP catalog fallback second.
- Handoff readiness: outputs must be directly consumable by `tmf-developer`.
- Explicit gap reporting: if enrichment is partial, record coverage and unresolved gaps.

## Workflow (deterministic)

1. Resolve governance context (optional but recommended):
   - If `workspace_id` is provided and `openarchitect` is available, read cascade/design context.
   - If upstream architecture context is draft/unresolved, continue only in advisory mode and mark output `governance_signal.cascade_recommendation = remediation_required`.
   - This skill does not mutate cascade state.

2. Prepare schema enrichment inputs:
   - If MCP enrichment is used, first build a catalog:
      `python scripts/build_mcp_schema_catalog.py --component-spec <tmfc-component.yaml> --trace-json-dir <trace-export-dir> --out <mcp-catalog.json>`
   - Expected source: exported JSON from TMF MCP traces (for example `trace_api_schema_chain` outputs).

3. Build component design package from multiple specs:
   - Run:
      `python scripts/build_tmf_design_package.py --component-name <component_name> --spec <spec1> --spec <spec2> --out <implementation-catalog.json> --summary-md <design-summary.md> --ddl-sql <component-ddl.sql> --openapi-spec-dir <dir-with-tmf-openapi> --use-mcp --mcp-schema-catalog <mcp-catalog.json>`
   - Keep outputs in a dedicated output directory.

4. Validate generated design artifacts:
   - Shared entities used by multiple APIs.
   - Per-API resource ownership.
   - Recommended `implementation_work_items`.
   - Shared database strategy and DDL output quality.
   - Architect review checklist for heuristic shared entities:
     - Confirm each `shared_entities[]` entry has business-meaningful canonical naming.
     - Confirm no false merges across unrelated API resources.
     - Confirm ownership boundaries for each shared entity before handoff.

5. Handoff to implementation with `tmf-developer`:
   - For each job in `implementation_work_items`, run:
      `python .codex/skills/openarchitect/tmf-developer/scripts/scaffold_tmf_service.py --spec <spec_path> --out <service_out_dir> --service-name <service_name> --database-url <database_url> --implementation-catalog <implementation-catalog.json> --design-api <api_id>`

6. Validate cross-service consistency:
   - Shared `database_url` when shared DB is intended.
   - Consistent naming for shared canonical entities.
   - Acceptable schema enrichment coverage (`schema_enrichment.resource_matches/resource_total` per API).

7. Emit governance/cascade signal (report-level; no auto-mutation):
   - Include `governance_signal` in design outputs:
     - `cascade_layer` (usually `domain_architecture` or `implementation`).
     - `cascade_recommendation`: `ready_for_review|remediation_required|block_advancement`.
     - `remediation_status`: `none|pending|complete`.
     - `note`: short summary of gating issues (for example unresolved shared-entity ownership).

## Cross-Skill Guidance (Cascade Position)

1. Upstream: `domain-architecture` (and/or SA component decomposition) should define component boundaries and API scope before this skill runs.
2. Downstream: `tmf-developer` consumes `implementation-catalog.json` to scaffold runnable API services.
3. Parallel: `constraint-validation` can be used to check compliance and architecture constraints.
4. Governance: this skill emits cascade-readiness signal only; advancement/mutation remains in architecture skills.

## Output Format Rules

- `implementation-catalog.json` must remain the canonical machine-readable contract for downstream scaffold generation.
- Keep shared entity naming stable across iterations once consumed by implementation.
- Include per-API ownership and schema enrichment coverage in outputs.
- If MCP enrichment is used, retain catalog provenance (source trace set, generation time, coverage).
- Include `governance_signal` in outputs for downstream gating context.
- Include an explicit `shared_entity_review_required` indicator when heuristic grouping was applied.

## Notes

- Missing spec files or unparseable YAML/JSON must fail fast with explicit path/context.
- Specs without `paths` may be skipped only when other valid specs remain; otherwise fail.
- If no usable TMF resources are found across inputs, stop and request corrected specs.
- When `--use-mcp` is set without catalog input, fail with explicit remediation.
- When `--mcp-required` is enabled with zero MCP matches, fail to prevent silent under-enrichment.
- Canonical entity detection is heuristic: architect review is mandatory before using outputs as implementation contracts.

## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
