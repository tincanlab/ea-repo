---
name: release-delta-generator
description: Generate a canonical enterprise current-state delta for a production release from approved workspace artifacts.
---

# Release Delta Generator (Planned)

Status: PLANNED (not runnable end-to-end yet)

This skill is a placeholder for the post-MVP flow described in:

- `docs/design/current_state_release_integration.md`
- `docs/design/enterprise_graph_mcp_tool_catalog.md`
- `docs/design/enterprise_current_state_schema.md`

## Purpose

Given a workspace's approved design artifacts (and optionally current-state context), produce `canonical_delta_text` suitable for:

- `enterprise_graph.apply_release(...)`

## Preconditions (Before This Skill Is Implemented)

- Context Registry has workspace TMF assertion read tools (planned):
  - `openarchitect.list_tmf_links(...)`
  - `openarchitect.get_tmf_coverage(...)`
- Enterprise graph MCP exists with:
  - `enterprise_graph.find_canonical_by_tmf_ref(...)`
  - `enterprise_graph.get_impact(...)`
  - `enterprise_graph.apply_release(...)` (arch profile)

## Intended Inputs

- Workspace approved artifacts (examples):
  - `architecture/domains/*/component-specs.yml`
  - `.openarchitect/traceability-map.yml`
  - interface catalogs (OpenAPI/AsyncAPI YAML)
- Optional: current-state lookups by TMF ref (read-only) to reduce noise in the delta.

## Intended Outputs

- `architecture/releases/release-delta.yml`
  - Canonical overlay delta (YAML) matching the `canonical_delta_text` shape in `docs/design/enterprise_graph_mcp_tool_catalog.md`
- Optional: `architecture/releases/release-delta.md`
  - Human-readable summary of what the delta will change and why.

## Safety / Non-Goals

- This skill must not mutate enterprise current state directly.
- The write step happens in CI/automation by calling `enterprise_graph.apply_release(...)` with a release contract + this delta.

