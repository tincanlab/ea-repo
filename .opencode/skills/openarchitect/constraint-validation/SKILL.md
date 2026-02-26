---
name: constraint-validation
description: Validate architecture proposals and connectivity paths against enterprise constraints/rules/policies stored in enterprise state. Use for AI architect checks before design sign-off.
---

# Constraint Validation

## Overview

Evaluate a proposed design or path against enterprise policy constraints with a consistent, auditable output. This skill is LLM-driven but evidence-bound: every decision must cite retrieved constraints and graph facts.

## Repository Convention

- Default folder: `architecture/validation/`
- Canonical output files:
  - `validation_report.md` for human-readable findings
  - `validation_report.yml` for structured verdicts
- If the project uses different paths, state them explicitly before running.

## Inputs

- `enterprise_id` and `environment` (required)
- Proposal payload (one of):
  - connectivity query (source, target, intent/protocol), or
  - architecture change summary, or
  - explicit path candidate(s)
- Optional scope:
  - `constraint_tags`
  - `severity_min`
  - specific `constraint_id` list
  - governance context (`workspace_id` and `cascade_layer`) when you want explicit cascade signaling in the report

## Required MCP Server

- `enterprise-graph`

## Required MCP Tools

- `health()`
- `list_constraints(enterprise_id, environment, severity_min, tags, status, as_of, limit)`
- `get_constraint(enterprise_id, environment, constraint_id, as_of, status)`
- `get_node(enterprise_id, environment, node_id)`
- `get_nodes_batch(enterprise_id, environment, node_ids, include_props)`
- `query_nodes(...)` and `query_edges(...)` as needed for evidence
- `path_between_nodes(...)` or `explain_path_between_nodes(...)` for connectivity checks
- `sql_readonly(...)` only when structured tools are insufficient

## Optional MCP Server (Cascade Governance Add-on)

- `openarchitect`

Optional tools when available:
- `get_cascade_state(workspace_id)`
- `list_artifacts(workspace_id, kind, limit)`

## Workflow (LLM + evidence discipline)

1. Resolve scope
   - Confirm `enterprise_id`, `environment`, and validation objective.
   - If objective is ambiguous, ask exactly one targeted clarification question.
   - If governance signaling is requested and `openarchitect` is available, resolve `workspace_id` and target `cascade_layer` for report context.

2. Collect constraints
   - Call `list_constraints(...)` with relevant tags/severity where possible.
   - Fetch full details for candidates via `get_constraint(...)`.
   - Build a working set of applicable constraints.

3. Collect design evidence
   - Retrieve nodes/edges/path facts needed to test each constraint.
   - Prefer structured graph tools first; use `sql_readonly` only as fallback.
   - Record concrete evidence artifacts (node IDs, edge types, traversed hops, key properties).

4. Evaluate
   - For each applicable constraint, determine:
     - `compliant`, `violated`, or `insufficient_evidence`
   - Do not infer missing facts as compliant.
   - If evidence is missing, mark gap explicitly and state what tool query would close it.

5. Produce structured verdict
   - Write `validation_report.yml` with one record per evaluated constraint.
   - Write `validation_report.md` with summary, highest-severity blockers, and remediation options.

6. Emit governance/cascade signal (report-level; no auto-mutation)
   - Record a `governance_signal` section in `validation_report.yml`:
     - `cascade_recommendation = block_advancement` for `deny`.
     - `cascade_recommendation = remediation_required` for `needs_clarification`.
     - `cascade_recommendation = ready_for_review` for `allow`.
   - Set `remediation_status = pending` whenever recommendation is `block_advancement` or `remediation_required`.
   - Do not auto-advance or auto-update cascade state from this skill; architecture skills consume this signal and perform gated advancement.

## Output Contract (`validation_report.yml`)

Use this shape:

```yaml
validation_id: val-<timestamp-or-stable-id>
enterprise_id: <enterprise_id>
environment: <environment>
proposal_summary: <short text>
overall_decision: allow | deny | needs_clarification
evaluated_at: <iso8601>
results:
  - constraint_id: <id>
    severity: critical | high | medium | low
    decision: compliant | violated | insufficient_evidence
    rationale: <short explanation>
    evidence:
      - type: node | edge | path | query_result
        ref: <id or query label>
        details: <short fact>
gaps:
  - <missing fact/query needed>
assumptions:
  - <explicit assumption>
recommended_actions:
  - <remediation or follow-up step>
governance_signal:
  workspace_id: <optional workspace id>
  cascade_layer: <requirements|enterprise_architecture|solution_architecture|domain_architecture|implementation|unknown>
  cascade_recommendation: ready_for_review | remediation_required | block_advancement
  remediation_status: none | pending | complete
  note: <short governance summary>
```

## Decision Rules

- `overall_decision = deny` if any `critical` or `high` constraint is `violated`.
- `overall_decision = needs_clarification` if:
  - no `critical/high` violations but one or more constraints are `insufficient_evidence`, or
  - one or more `medium/low` constraints are `violated` (risk/remediation required before clean pass).
- `overall_decision = allow` only when all applicable constraints are `compliant`.

## Truthfulness and Safety Rules

- Never claim compliance without citing at least one constraint and one evidence item.
- Never suppress conflicts between constraints; list conflicts explicitly.
- Never treat missing data as pass.
- Prefer explicit uncertainty over speculative conclusions.

## Notes

- This skill intentionally keeps policy logic in data (`oa_enterprise_constraint`) and evaluation in a reusable workflow.
- It is suitable for your current LLM-first approach and can later be upgraded with deterministic evaluators without changing report shape.
## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
