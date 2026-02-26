---
name: workspace-creation
description: Create governed workspace creation requests and optional workspace/relation provisioning for a design initiative. Use when solution architecture outputs identify required workspaces, when checking whether target workspaces already exist, when preparing approval-ready workspace provisioning artifacts, or when executing approved workspace creation and relation updates.
---

# Workspace Creation

## Overview

This skill handles workspace provisioning as a governed flow:
- confirm what workspaces are required (usually from SA outputs)
- check existing workspace matches and workspace kind fit
- produce approval-ready creation requests
- optionally execute approved creation and relation updates

This skill follows the locked workspace selection policy:
- default resolution is fail-closed
- no implicit create in selection flows
- creation only happens from explicit, approved requests

## Repository Convention

- Primary inputs from SA:
  - `architecture/solution/workspace-plan.yml`
  - `architecture/solution/workspace-creation-request.yml`
- Primary outputs:
  - `architecture/solution/workspace-creation-request.yml` (updated state)
  - `architecture/solution/workspace-creation-result.yml` (execution result)
  - Optional: `architecture/solution/workspace-creation-result.md` (human summary)

Use templates:
- `references/workspace-creation-request.yml.template`
- `references/workspace-creation-result.yml.template`

## Required Inputs

- `workspace_id` (current SA workspace)
- requested workspaces (from SA artifact or user)
- target `enterprise_id`

Optional:
- `tenant_id`
- explicit actor id for `created_by`

## Tooling and Access

Required MCP server:
- `openarchitect`

Required MCP tools:
- `openarchitect.get_workspace(workspace_id)`
- `openarchitect.workspaces_search(query, tenant_id, enterprise_id, limit)`
- `openarchitect.create_workspace(name, tenant_id, enterprise_id, workspace_kind)`
- `openarchitect.set_workspace_kind(workspace_id, workspace_kind, reason)` (when reclassification is needed)
- `openarchitect.upsert_workspace_relation(...)`
- `openarchitect.register_artifact(...)`

Optional MCP tools:
- `openarchitect.list_workspace_relations(...)` (pre/post relation verification)

## Workflow

### Phase 0: Load Context

1. Resolve source context:
- call `get_workspace(workspace_id)` for the initiating workspace
- capture `enterprise_id` and `tenant_id` defaults for requests

2. Load requested workspaces:
- prefer `architecture/solution/workspace-creation-request.yml`
- fallback to `architecture/solution/workspace-plan.yml`
- if both are missing, ask user for requested workspaces and create a new request file

### Phase 1: Verify Existing Workspaces

3. Check workspace existence:
- for each requested workspace name, call `workspaces_search(...)`
- record:
  - `none` match -> candidate for create
  - `single` exact match -> candidate for reuse
  - `multiple` matches -> candidate requires explicit selection

4. Check workspace kind fit:
- for matched candidates, call `get_workspace(match.workspace_id)`
- if kind mismatches request:
  - do not auto-change by default
  - set action to `review_kind_mismatch` unless user explicitly approves reclassification

5. Update request artifact with evidence:
- set each request `current_state` with search and kind-check evidence
- set `action`:
  - `reuse_then_relate`
  - `create_then_relate`
  - `manual_select_required`
  - `review_kind_mismatch`

### Phase 2: Approval Package

6. Emit/refresh `workspace-creation-request.yml`:
- include name, kind, enterprise, tenant, reason
- include relation updates required after reuse/create
- include `approval.state` and `requested_by`
- include `source_artifacts` when available

7. Stop for approval when required:
- unless explicitly told to execute, leave `execution.state=not_started`
- never claim a workspace was created or relation updated without tool evidence

### Phase 3: Execute (Only When Explicitly Approved)

8. Create missing workspaces:
- for each approved request with `action=create_then_relate`, call `create_workspace(...)`
- record created workspace IDs by `workspace_key`

9. Apply relation updates:
- resolve relation endpoints from:
  - existing workspace IDs
  - newly created workspace IDs
  - initiating `workspace_id` when requested
- call `upsert_workspace_relation(...)` for each approved relation update

10. Optional reclassification:
- only when explicitly approved, call `set_workspace_kind(...)` for kind corrections
- if no explicit approval, leave mismatch as an open governance item

11. Emit result artifact:
- write `architecture/solution/workspace-creation-result.yml`
- set `execution.state` to `completed`, `partial_failure`, or `failed`
- include created workspaces, relation updates, and failures

### Phase 4: Register Artifacts

12. Register artifacts to workspace:
- register request artifact as `workspace_creation_request`
- register result artifact as `workspace_creation_result` (if execution was attempted)
- include `git_path`, source refs, and pinned commit metadata when available

## Output Contract

Use `references/workspace-creation-request.yml.template` and `references/workspace-creation-result.yml.template`.

Minimum request fields:
- `workspace_id`
- `request_id`
- `workspaces_requested[]` with `name`, `workspace_kind`, `enterprise_id`, `reason`
- `approval.state`
- `execution.state`

Minimum result fields:
- `workspace_id`
- `request_id`
- `execution.state`
- `created_workspaces[]`
- `relation_updates[]`
- `failures[]`

## Truthfulness and Safety

- Do not claim workspace creation success without MCP evidence.
- Do not auto-create workspaces from ambiguous multi-match searches.
- Do not auto-change workspace kind without explicit approval and reason.
- Do not auto-add relations not present in approved request artifacts.
- If permissions are missing, output a complete request artifact and stop cleanly.
