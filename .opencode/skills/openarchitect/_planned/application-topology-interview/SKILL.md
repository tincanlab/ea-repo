---
name: application-topology-interview
description: Interview stakeholders to map "applications" and their deployment topology on top of auto-discovered cloud inventory. Produces a reusable app topology artifact and optional classification rules for future automated mapping.
---

# Application Topology Interview

## Overview

Auto-discovered cloud inventory (accounts, VPCs, subnets, load balancers, services, databases) is necessary but not sufficient to answer leadership questions like:
- What applications do we run?
- Where are they deployed?
- Who owns them?
- What do they depend on?

This skill performs a bounded interview to turn discovered infrastructure into an application topology map with explicit evidence and explicit gaps.

This skill is LLM-driven and evidence-bound:
- facts must come from inventory queries (MCP tools) or explicit user answers
- unknowns must be recorded as gaps, not guessed

Authority model:
- `observed_raw` facts come from `oa_enterprise_raw_*` evidence and are authoritative for discovered infra.
- declared assertions are additive overlays for gaps and are classified as:
  - `declared_internal_unobserved` (internal but currently uncollectable)
  - `declared_external` (third-party/COTS/out-of-scope collection)
- declared overlays must not overwrite raw observed facts; conflicts are flagged for review.

## Repository Convention

- Default folder: `architecture/app_topology/`
- Canonical output files:
  - `app_topology.md` (human-readable narrative + diagrams)
  - `app_topology.yml` (structured topology for reuse by other skills/agents)
- Optional outputs:
  - `app_classification_rules.yml` (how to derive app boundaries from tags/names)
  - `app_topology_interview_log.md` (questions + answers + decisions)

If the project uses different paths, state them explicitly before running.

## Inputs

Required:
- `enterprise_id` and `environment`

Optional:
- initial app candidate name(s) (if stakeholder wants to start with a specific app)
- known tag keys (e.g., `app`, `service`, `owner`, `team`, `cost_center`)

## Required MCP Server

- `enterprise-graph`

## Required MCP Tools (minimum)

- `health()`
- `query_nodes(...)`, `count_nodes(...)`
- `query_edges(...)`, `list_edges(...)`
- `path_between_nodes(...)` or `explain_path_between_nodes(...)` for multi-hop evidence
- `sql_readonly(...)` only when structured tools are insufficient

Recommended tools (if available):
- `list_labels(...)`
- `list_relationship_types(...)`
- `get_nodes_batch(...)`
- `get_subgraph(...)` (bounded)

## Workflow (bounded interview)

The goal is to ask the fewest questions that unlock high-confidence grouping.
Ask exactly one question per turn unless the user explicitly invites more.

### Phase 0: Preconditions

1. Call `health()` and record:
- DB reachable and inventory tables present
- any degraded status

2. Confirm scope:
- `enterprise_id`
- `environment`
- whether to map "one app" or "all apps"

### Phase 1: Discover candidates from inventory

Use discovered inventory to propose app candidates:
- Prefer tag-based grouping when tags exist (for example `props->>'app'`).
- Otherwise infer candidates from stable entry points:
  - load balancers, API gateways, ingress endpoints
  - compute runtimes (ECS services, EKS namespaces if available, Lambdas)

Output of this phase:
- a small ranked list of candidate apps and why they were chosen
- what evidence exists (node IDs + key props)
- explicit gaps (missing tags, ambiguous naming)

### Phase 2: Interview to define app boundary rules

Ask a short set of high-value questions, stopping early when stable rules emerge:

1. App naming and boundaries
- "What tag key or naming convention defines an application here?"

2. Ownership
- "Which tag key or system records the owning team/oncall?"

3. Environments
- "How do you distinguish lower environments (dev/test/stage) from prod?"

4. Criticality
- "Which apps are most critical (top 3) and what makes them critical?"

5. Shared services
- "Which shared platforms should be excluded from app ownership mapping (logging, CI, shared DB, etc.)?"

Capture answers in `app_topology_interview_log.md`.

### Phase 3: Construct application topology with evidence

For each app:
- entry points (LB/API)
- runtimes (compute/services)
- data stores (DB/cache/buckets) when evidence exists
- network placement (accounts/VPC/subnets) when evidence exists
- dependencies (edges and multi-hop paths) with explicit evidence

For every relationship, record:
- evidence node IDs and edge types
- a confidence score (high/medium/low)
- source classification (`observed_raw`, `declared_internal_unobserved`, `declared_external`)

For each declared assertion, capture required metadata:
- `reason_code` (for example `security_restricted`, `collector_not_implemented`, `policy_blocked`, `third_party_black_box`)
- `owner`
- `reviewed_by`
- lifecycle `state` (`proposed`, `approved`, `rejected`, `superseded`)

### Phase 4: Produce artifacts

Write:
- `app_topology.yml` (structured)
- `app_topology.md` (human narrative, executive summary first)

Optionally write:
- `app_classification_rules.yml` (rules to derive `app_id`, `owner`, `env` from inventory)

## Output Contract (`app_topology.yml`)

Suggested shape:

```yaml
enterprise_id: <enterprise_id>
environment: <environment>
generated_at: <iso8601>
sources:
  - kind: inventory
    scope: enterprise_state.public.oa_enterprise_raw_*
    evidence_note: "All factual topology elements must trace to node/edge IDs."
  - kind: declared_overlay
    scope: interview + governed review
    authority_note: "Declared overlays are additive and must not replace observed raw facts."
apps:
  - app_id: <stable-id>
    name: <display name>
    owner:
      team: <string or null>
      oncall: <string or null>
    criticality: critical | high | medium | low | unknown
    evidence:
      nodes: [<node_id>]
      edges: [<edge_id-or-descriptor>]
      notes: [<short bullets>]
    topology:
      entry_points:
        - ref: <node_id-or-external-ref>
          source_class: observed_raw | declared_internal_unobserved | declared_external
          state: observed | proposed | approved | rejected | superseded
          reason_code: <required when declared>
      runtimes:
        - ref: <node_id-or-external-ref>
          source_class: observed_raw | declared_internal_unobserved | declared_external
          state: observed | proposed | approved | rejected | superseded
          reason_code: <required when declared>
      data_stores:
        - ref: <node_id-or-external-ref>
          source_class: observed_raw | declared_internal_unobserved | declared_external
          state: observed | proposed | approved | rejected | superseded
          reason_code: <required when declared>
      external_dependencies:
        - ref: <node_id-or-text>
          source_class: observed_raw | declared_internal_unobserved | declared_external
          state: observed | proposed | approved | rejected | superseded
          reason_code: <required when declared>
    gaps:
      - <missing fact>
assumptions:
  - <explicit assumption>
declared_assertions:
  approval_policy:
    domain_architect_scope: "can approve declared_internal_unobserved within one domain"
    arch_scope: "required for declared_external, cross-domain, or enterprise-scope"
  validity_policy:
    expires_automatically: false
    requires_manual_change: true
  review:
    last_reviewed_at: <iso8601>
    next_review_due_at: <iso8601-or-null>
next_questions:
  - <single next best question, if needed>
```

## Truthfulness Rules

- Do not invent an app boundary; if the interview cannot establish rules, report that as a gap.
- Do not claim ownership without explicit evidence (tag, CMDB field, or user answer).
- Prefer "insufficient evidence" over guessing.
- Do not label declared assertions as observed facts.
- Keep declared assertions until manually changed; emit stale-review warnings instead of auto-expiring entries.
