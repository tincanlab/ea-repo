---
name: stakeholder-mapping
description: Identify stakeholders for a change/initiative, capture their concerns, decision rights, and engagement plan. Use during requirements analysis and architecture work to de-risk approvals, governance, and cross-domain alignment.
---

# Stakeholder Mapping

## Overview

Create a concrete, decision-ready stakeholder map (who matters, what they care about, and how decisions happen) that can be versioned alongside requirements.

## Repository Convention

- Default folder: `architecture/requirements/`
- Canonical file names:
  - `stakeholders.md` for narrative stakeholder map
  - `stakeholders.yml` for structured canonical map
- If project uses a different path, state it explicitly before running.

## Outputs (write as separate files)

- `architecture/requirements/stakeholders.md`
- `architecture/requirements/stakeholders.yml`

Use:
- `references/stakeholders.md.template`
- `references/stakeholders.yml.template`

## Context Platform Integration

MCP server (recommended):
- `openarchitect`

MCP runtime (HTTP, configured in `.cursor/mcp.json`):
- `openarchitect` -> `http://localhost:8101/mcp`

Degraded mode (when `openarchitect` MCP is unavailable):
- The skill can still read/write the repo artifacts locally.
- The skill must clearly state that workspace context and artifact registration were skipped.

Current limitations in active skills:
- Local workspace-state persistence is not automated.
- Workspace artifact registration is optional and may be unavailable in some environments.

MCP tools to use when available:
- `openarchitect.workspaces_list(limit)`
- `openarchitect.workspaces_search(query, tenant_id, limit)`
- `openarchitect.workspaces_select(workspace_id|query, tenant_id, candidate_index)`
- `openarchitect.workspaces_create(name, tenant_id, persist)` (arch profile when create is needed; persist is client-managed)
- `openarchitect.get_design_context(workspace_id, "requirements", "stakeholders")`
- `openarchitect.get_cascade_state(workspace_id)`
- `openarchitect.list_artifacts(workspace_id, kind, limit)`

## Workflow (deterministic)

1. Resolve workspace deterministically:
   - Use explicit `workspace_id` when provided.
   - If no explicit `workspace_id`, use `workspaces_search/list`.
   - Auto-select only when one clear best candidate exists.
   - If multiple plausible candidates exist, show top 2-3 and ask user to choose.
   - Create workspace only when none is suitable.

2. Gather context and current state:
   - Call `get_design_context(workspace_id, "requirements", "stakeholders")`.
   - Call `get_cascade_state(workspace_id)`.
   - Inspect `list_artifacts(...)` for prior stakeholder baselines and decision records.
   - Interpret cascade readiness from stakeholder evidence:
     - This skill does not advance cascade state directly.
     - If approval gates, approvers, or required evidence are unresolved, mark output as `not_ready_for_advancement` for affected upstream/downstream layers.
     - If gates and ownership are clear, mark output as `ready_for_advancement_review` (advisory signal only; final advancement remains in architecture skills).

3. Handle migration-first registration:
   - If repo files exist but workspace lacks them, register first:
      - `stakeholder_map` -> `architecture/requirements/stakeholders.md`
      - `stakeholder_map_structured` -> `architecture/requirements/stakeholders.yml`
   - Provide `text` explicitly (do not rely on server-side file reads).
   - If registration tooling is unavailable, continue and record that registration was skipped.

4. Produce stakeholder map in phases:
   - discovery phase: identify concrete stakeholder roles/names and affected teams.
   - influence phase: capture concerns, decision rights, approval/block authority, evidence required.
   - engagement phase: define cadence, channels, sign-off gates, escalation path.

5. Clarification behavior:
   - Ask exactly one targeted question per turn unless user invites more.
   - Prioritize unresolved approval gates and decision authority conflicts.

6. Register outputs after writing:
   - Register artifacts when tooling is available; otherwise explicitly record the skip.

7. Emit governance/cascade signal (report-level; no auto-mutation):
   - In `stakeholders.yml`, set `governance_signal.cascade_layer` (usually `requirements`).
   - Set `governance_signal.cascade_recommendation`:
     - `ready_for_review` when decision gates, ownership, and evidence requirements are clear.
     - `remediation_required` when unresolved authority conflicts or missing gate evidence remain.
     - `block_advancement` when required approvers or mandatory gates are missing.
   - Set `governance_signal.remediation_status` to `pending` when recommendation is not `ready_for_review`.
   - Do not auto-advance or auto-update cascade state from this skill.

## Cross-Skill Guidance (Cascade Context)

- This skill is a governance input to cascade decisions, not a cascade-state mutator.
- `requirement-analysis`, `solution-architecture`, and `domain-architecture` should consume stakeholder gates/evidence before advancing their own cascade layers.
- If stakeholder gates are unresolved, recommend pausing cascade advancement until the mapped approvers and evidence are complete.
- Use `governance_signal` as the machine-readable handoff signal for downstream skills.

## Output quality bar

- Stakeholders are concrete (names/roles), not generic (\"the business\").
- At least one explicit architecture decision gate is identified (who approves what).
- Decision ownership quality is explicit:
  - RACI-style ownership is defined for major gates (at least Responsible and Approver roles).
  - Escalation path is defined for blocked/late decisions.
  - Engagement cadence and channel are specified for high-influence stakeholders.

## Output Format Rules

- `stakeholders.yml` is canonical and must validate against `references/stakeholders.schema.json`.
- Keep `stakeholders.md` concise and decision-oriented.
- Include context evidence in markdown: resolved `workspace_id`, tools used, key artifact refs.
- In `stakeholders.yml`, include governance metadata for quality/completeness:
  - `cascade_readiness` (`ready_for_advancement_review|not_ready_for_advancement`)
  - `raci` mappings for major decision gates (at minimum `responsible` and `approver`)
  - `escalation_path` for unresolved/blocked gates
  - `governance_signal`:
    - `workspace_id` (optional)
    - `cascade_layer` (`requirements|enterprise_architecture|solution_architecture|domain_architecture|implementation|unknown`)
    - `cascade_recommendation` (`ready_for_review|remediation_required|block_advancement`)
    - `remediation_status` (`none|pending|complete`)
    - `note` (short governance summary)

## Notes

- Enforce truthfulness: do not mark approvals as confirmed without explicit evidence.
- Keep role labels stable to preserve traceability across versions.
## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
