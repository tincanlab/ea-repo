---
name: use-case-elaboration
description: Expand high-level requirements into concrete use cases (actors, triggers, main/alternate flows, errors) and critical user journeys with acceptance criteria. Use after initial requirement analysis and before/during solution architecture to anchor interfaces and sequences.
---

# Use Case Elaboration

## Overview

Turn requirements into implementation-ready, testable use cases and journeys that drive architecture sequencing and integration behavior.

## Repository Convention

- Default folder: `architecture/requirements/`
- Canonical file names:
  - `use-cases.md` for narrative/use-case specs
  - `use-cases.yml` for structured canonical baseline
- If project uses a different path, state it explicitly before running.

## Outputs (write as separate files)

- `architecture/requirements/use-cases.md`
- `architecture/requirements/use-cases.yml`

Use:
- `references/use-cases.md.template`
- `references/use-cases.yml.template`

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
- `openarchitect.get_design_context(workspace_id, "requirements", "use_cases")`
- `openarchitect.get_cascade_state(workspace_id)`
- `openarchitect.list_artifacts(workspace_id, kind, limit)`

## Workflow (deterministic)

1. Resolve workspace deterministically:
   - Use explicit `workspace_id` when provided.
   - If no explicit `workspace_id`, use `workspaces_search/list` and rank candidates by requirements/use-case relevance.
   - Auto-select only when there is one clear best candidate.
   - If multiple plausible workspaces exist, present top 2-3 choices and ask user to choose before selecting.
   - Create workspace only when none is suitable.

2. Gather context and state:
   - Call `get_design_context(workspace_id, "requirements", "use_cases")`.
   - Call `get_cascade_state(workspace_id)`.
   - Inspect `list_artifacts(...)` for prior use-case outputs to avoid overwriting newer baselines.

3. Handle migration-first registration:
   - If repo files already exist but workspace lacks them, register first:
      - `use_cases_markdown` -> `architecture/requirements/use-cases.md`
      - `use_cases_structured` -> `architecture/requirements/use-cases.yml`
   - Provide `text` explicitly (do not rely on server-side file reads).
   - If registration tooling is unavailable, continue and record that registration was skipped.

4. Produce use cases in phases:
   - selection phase:
     - Default target is 5-12 critical use cases to keep first-pass reviewable and decision-ready while covering core business value and integration risk.
     - For larger programs, make the count configurable with `target_use_case_count` (for example 12-30) based on system scope and stakeholder review capacity.
   - elaboration phase: for each use case define actors, trigger, preconditions, main flow, alternates/errors, inputs/outputs, NFR touchpoints.
   - traceability phase: link each use case to one or more `req-*` IDs and define acceptance checks.
   - lifecycle phase:
     - Apply versioning policy for change-safe evolution:
       - Minor edits: keep `uc-*` ID; increment `revision`.
       - Major semantic change: create a new `uc-*` ID and mark old entry `status: superseded`.
       - Split: keep original `uc-*` as `superseded` and create child `uc-*` entries referencing `supersedes`.
       - Merge: create a new `uc-*` entry and mark source entries `superseded`.
     - Maintain explicit links (`supersedes`, `superseded_by`, `change_reason`) so downstream architecture artifacts can trace transitions.

5. Clarification behavior:
   - Ask exactly one targeted question per turn unless user invites more.
   - If a flow is blocked by an unresolved architectural decision, ask the single highest-impact question and stop.

6. Register outputs after writing:
   - Register artifacts when tooling is available; otherwise explicitly record the skip.

7. Emit governance/cascade signal (report-level; no auto-mutation):
   - In `use-cases.yml`, set `governance_signal.cascade_layer` (usually `requirements`).
   - Set `governance_signal.cascade_recommendation`:
     - `ready_for_review` when selected use cases have clear traceability to requirements and no blocking decision gaps.
     - `remediation_required` when major gaps/ambiguities remain (for example unresolved architecture decisions impacting core flows).
     - `block_advancement` when foundational use-case coverage is missing for critical scope.
   - Set `governance_signal.remediation_status` to `pending` when recommendation is not `ready_for_review`.
   - Do not auto-advance or auto-update cascade state from this skill.

## Cross-Skill Guidance (Cascade Context)

- This skill provides readiness evidence for downstream architecture, but does not mutate cascade state.
- `requirement-analysis`, `solution-architecture`, and `domain-architecture` should consume `governance_signal` and use-case traceability before advancement decisions.

## Output quality bar

- Use cases include failure paths (timeouts, invalid input, upstream/downstream failure).
- At least one cross-domain \"golden path\" is fully specified end-to-end.

## Output Format Rules

- `use-cases.yml` is canonical and must validate against `references/use-cases.schema.json`.
- Keep `use-cases.md` concise and decision-oriented.
- Include context evidence in markdown: resolved `workspace_id`, key tools used, and key artifact refs.
- Use lifecycle metadata in `use-cases.yml` for change management:
  - `status` (`active|deprecated|superseded`)
  - `revision` (monotonic integer per `uc-*`)
  - `supersedes` / `superseded_by` (use case ID links)
  - `change_reason` (short rationale)
- Include governance signaling metadata in `use-cases.yml`:
  - `source.cascade_readiness` (`ready_for_advancement_review|not_ready_for_advancement`)
  - `governance_signal`:
    - `workspace_id` (optional)
    - `cascade_layer` (`requirements|enterprise_architecture|solution_architecture|domain_architecture|implementation|unknown`)
    - `cascade_recommendation` (`ready_for_review|remediation_required|block_advancement`)
    - `remediation_status` (`none|pending|complete`)
    - `note` (short governance summary)

## Notes

- Enforce truthfulness: do not claim interface behavior as verified without evidence.
- Preserve stable use case IDs (`uc-*`) once published.
- Stable IDs do not mean immutable semantics: use revision and supersession metadata to evolve use cases safely when requirements change.
- This skill emits governance signal only; cascade-state mutation remains in architecture skills.
## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
