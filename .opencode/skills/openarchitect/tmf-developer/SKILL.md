---
name: tmf-developer
description: Build real TM Forum REST services from TMF OpenAPI YAML/JSON specs with FastAPI and SQLite persistence. Use when you need to implement a runnable backend service (not only an MCP wrapper) for TMF APIs such as TMF620/TMF637, including CRUD endpoints, local storage, and service scaffolding from a spec file.
---

# TMF Developer

## Overview

Implement a runnable TM Forum service from an OpenAPI document with SQLite-backed persistence.

This skill is optimized for:
1. Bootstrapping new TMF services from files like `TMF620-Product_Catalog_Management-v5.0.0.oas.yaml`.
2. Creating a local, testable backend for development and integration testing.
3. Preserving TMF payloads while exposing standard collection/item operations.

## Repository Convention

- Primary scripts:
  - `scripts/tmf_openapi_inventory.py`
  - `scripts/scaffold_tmf_service.py`
- Hardening reference:
  - `references/sqlite-service-hardening.md`
- Recommended generated structure under `<output_dir>`:
  - `app/main.py`
  - `app/database.py`
  - `app/models.py`
  - `app/crud.py`
  - `app/schemas.py`
  - `requirements.txt`
  - `README-TMF####.md`

## Inputs

Required:
1. `spec_path`: path to TMF OpenAPI YAML/JSON file.
2. `output_dir`: directory where the service project will be generated.

Optional:
1. `service_name`: application name (if omitted, derive from TMF spec title/filename).
2. `database_url`: SQLite URL override (default `sqlite:///./tmf_service.db`).
3. `include_hub`: force-enable or force-disable `/hub` subscription endpoints.
4. `strict_methods`: generate only methods present in spec (default true).
5. `design_package`: optional path to `tmf-domain-architect` output `implementation-catalog.json`.
6. `design_api`: optional API selector (`api_id`, TMF number, or title) when design package contains multiple APIs.
7. `workspace_id` and target `cascade_layer` (optional; governance signaling context only).

## Outputs (write to repo as separate files)

Core outputs in `<output_dir>`:
- `inventory.json`
- Generated FastAPI service package (`app/`)
- `requirements.txt`
- `README-TMF####.md`

Optional outputs:
- `/hub` subscription endpoints (when enabled and present in spec)
- Design-package-aligned configuration and defaults (when `design_package` is provided)

## Context Platform Integration

Default mode is local-script execution from OpenAPI files.

Optional MCP servers:
- `tmf-mcp` (to discover/select spec candidates before generation when needed)
- `openarchitect` (optional governance context: workspace/cascade reads)

MCP is not required for scaffold generation. Do not claim MCP-backed evidence unless tools were actually used.
If `openarchitect` is available, use it only for governance context (`get_cascade_state`, `get_design_context`).

## Design Principles

- Spec-first generation: generated behavior must follow the provided OpenAPI contract.
- Deterministic scaffold: always run inventory before scaffold generation.
- Contract honesty: if methods/resources are unsupported, skip and report explicitly.
- Fast local feedback: verify health + one CRUD flow after generation.
- Production hardening required: generated defaults are for local development unless hardening is applied.

## Workflow (deterministic)

1. Validate inputs:
   - Ensure `spec_path` exists and is parseable.
   - Ensure `output_dir` is writable.
   - If `design_package` is provided and has multiple APIs, require explicit `design_api`.
   - If `design_package` is not provided, ask user to confirm standalone mode; recommended default is to consume `tmf-domain-architect` output.

2. Resolve governance context (optional but recommended):
   - If `workspace_id` is provided and `openarchitect` is available, read cascade/design context.
   - If upstream architecture context is draft/unresolved, continue only in advisory mode and mark output `governance_signal.cascade_recommendation = remediation_required`.
   - This skill does not mutate cascade state.

3. Inventory the TMF spec:
   - Run:
      `python scripts/tmf_openapi_inventory.py --spec <spec_path> --out <output_dir>/inventory.json`
   - Confirm main resources and method coverage.
   - Stop if no usable top-level TMF resources are found.

4. Generate FastAPI + SQLite scaffold:
   - Standard:
      `python scripts/scaffold_tmf_service.py --spec <spec_path> --out <output_dir> --service-name <service_name> --strict-methods --include-hub`
   - Design-package-driven:
      `python scripts/scaffold_tmf_service.py --spec <spec_path> --out <output_dir> --implementation-catalog <implementation-catalog.json> --design-api <api_id>`

5. Install dependencies and run:
   - `pip install -r <output_dir>/requirements.txt`
   - `uvicorn app.main:app --reload --app-dir <output_dir>`

6. Validate generated behavior:
   - Verify `GET /health`.
   - Verify CRUD on one core resource (for TMF620, commonly `/productOffering`).
   - Verify payload `id` handling and patch behavior.
   - If a method is not in the source spec, keep route absent (prefer `405` over emulating unsupported methods).

7. Harden before production-like use:
   - Apply checklist in `references/sqlite-service-hardening.md`.
   - Add authn/authz, stricter request validation, and migration strategy.

8. Emit governance/cascade signal (report-level; no auto-mutation):
   - In generated README (or companion implementation note), include `governance_signal`:
     - `cascade_layer` (usually `implementation`).
     - `cascade_recommendation`: `ready_for_review|remediation_required|block_advancement`.
     - `remediation_status`: `none|pending|complete`.
     - `note`: short summary (for example design-package missing, unresolved contract gaps).

## Cross-Skill Guidance (Cascade Position)

1. Upstream: `domain-architecture` and `tmf-domain-architect` should define/approve component boundaries before service scaffold generation.
2. Upstream default: `tmf-domain-architect` should provide `implementation-catalog.json` to align multi-API ownership and shared entities.
3. Standalone mode: allowed only by explicit user choice when no design package exists.
4. Parallel: `constraint-validation` can validate service design/implementation against enterprise controls.
5. Downstream: service repo CI/CD, security hardening, and operationalization.
6. Governance: this skill emits cascade-readiness signal only; advancement/mutation remains in architecture skills.

## Output Format Rules

- Keep generated service names stable across iterations once published.
- Preserve TMF payload shape unless a documented mapping layer is intentionally introduced.
- Include skipped/unsupported paths in generated README for traceability.
- Treat `inventory.json` as the machine-readable evidence of what was discovered from the input spec.
- Include `governance_signal` in generated README or companion implementation note.

## Notes

- Invalid or unreadable OpenAPI input must fail fast with explicit parser context.
- If required OpenAPI sections (`info`, `paths`) are missing, stop with explicit missing-key errors.
- For unsupported path shapes, skip with evidence instead of silently fabricating handlers.
- SQLite is intended for local development/test and light workloads.
- Generated services omit auth by default and should not be exposed publicly without hardening.

## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
