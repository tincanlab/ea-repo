---
name: enterprise-architecture
description: Define enterprise-wide target architecture, capability maps, governance frameworks, technology portfolio assessments, and strategic roadmaps. Top of the design cascade -- outputs drive SA and domain architecture downstream. TOGAF/Zachman aligned, TM Forum aware. Use when defining or reviewing enterprise strategy, governance, capability priorities, portfolio rationalization, or target architecture guardrails.
---

# Enterprise Architecture

## Overview

Define the enterprise-level architecture that governs all downstream design: target architecture vision, business capability maps, technology portfolio assessments, governance frameworks, and strategic roadmaps. This is the top of the design cascade -- EA artifacts set the guardrails, NFR envelopes, and strategic direction that SA and domain architects must conform to.

Legacy-ported from the EA agent runtime. Consolidated from hardcoded tool stubs into an LLM-driven phased workflow with workspace topology awareness and cascade governance.

## Repository Convention

- Enterprise repo entrypoints (repo root):
  - `ENTERPRISE.md` (enterprise TOC + links to solution repos + selector manifest)
  - `ROADMAP.md` (EA-owned enterprise roadmap; roll-up across solutions)
  - `AGENTS.md` (how to work in this repo)
- Upstream evidence:
  - `inputs/` (optional; pinned snapshots/references to solution/domain roadmaps and key upstream artifacts)
- Default enterprise folder: `architecture/enterprise/`
- Canonical output files:
  - `architecture/enterprise/target-architecture.md` (narrative target architecture)
  - `architecture/enterprise/target-architecture.yml` (structured target architecture)
  - `architecture/enterprise/capability-map.yml` (business capability heatmap)
  - `architecture/enterprise/portfolio-assessment.yml` (technology/application portfolio)
  - `architecture/enterprise/governance.yml` (governance framework, policies, controls)
  - `architecture/portfolio/initiative-pipeline.yml` (portfolio source owned by PM/business/IT)
  - `architecture/portfolio/initiatives.yml` (EA selector manifest: initiative -> solution repo mapping)
  - `ROADMAP.md` (strategic implementation roadmap; repo-root)
  - Optional `ROADMAP.yml` (machine-readable roll-up for aggregation)
- If the project uses different paths, state them explicitly before running.

## Inputs

This skill is driven by business vision and strategy -- it translates strategic intent into architectural guardrails:

- **Business vision and strategy** (primary driver): corporate strategy documents, board directives, annual/multi-year plans, market positioning, growth targets, M&A plans, digital transformation mandates. These define the "why" and "where" that EA translates into architectural "how."
- `architecture/portfolio/initiative-pipeline.yml` (portfolio lifecycle source; if present, generate selector manifest from it)
- `architecture/requirements/requirements.yml` (requirements baseline from `requirement-analysis`, if available)
- Regulatory and compliance mandates (GDPR, SOX, industry-specific regulations)
- Existing enterprise architecture artifacts for review/evolution

If business vision/strategy documents are not provided, ask the user to supply them or summarize the strategic direction before proceeding. EA without strategic grounding produces architecture without purpose.

## Outputs (write to repo as separate files)

Core outputs:
- `ENTERPRISE.md`
- `ROADMAP.md`
- `architecture/enterprise/target-architecture.md`
- `architecture/enterprise/target-architecture.yml`
- `architecture/enterprise/capability-map.yml`
- `architecture/portfolio/initiatives.yml`
- `governance_signal` section in both `target-architecture.yml` and `capability-map.yml` (EA readiness contract for downstream SA)

Optional outputs (on request or as workflow dictates):
- `architecture/portfolio/initiative-pipeline.yml` (if portfolio lifecycle source was missing, initialize from template and maintain)
- `architecture/enterprise/portfolio-assessment.yml`
- `architecture/enterprise/governance.yml`
- `ROADMAP.yml`
- `architecture/enterprise/adr/` (enterprise-level architecture decision records)

## Context Platform Integration

MCP servers (recommended):
- `openarchitect` (workspace/artifact context)

Optional MCP servers:
- `enterprise-graph` (enterprise current-state topology, constraints, blast radius)
- TMF MCP (ODA domains/components, eTOM processes, reference models)

MCP runtime (HTTP, configured in `.cursor/mcp.json`):
- `openarchitect` -> `http://localhost:8101/mcp`
- `enterprise-graph` -> `http://localhost:8102/mcp`
- `tmf-mcp` -> `http://localhost:8000/mcp` (optional)

Degraded mode (when MCP is unavailable):
- The skill can read/write repo artifacts and complete the design workflow locally.
- Must clearly state that workspace context, enterprise graph, and artifact registration were skipped.
- Must not claim enterprise topology or constraint evidence without MCP tool results.

Current limitations in active skills:
- Local workspace-state persistence is not automated.
- Workspace artifact registration is optional and may be unavailable in some environments.

MCP tools to use when `openarchitect` is available:
- `openarchitect.workspaces_list(limit)`
- `openarchitect.workspaces_search(query, tenant_id, limit)`
- `openarchitect.workspaces_select(workspace_id|query, tenant_id, candidate_index)`
- `openarchitect.get_design_context(workspace_id, domain, level)`
- `openarchitect.get_cascade_state(workspace_id)`
- `openarchitect.list_artifacts(workspace_id, kind, limit)`

Optional MCP tools (enterprise-graph):
- `enterprise-graph.list_labels(enterprise_id, environment)` -- discover entity types in current state
- `enterprise-graph.list_constraints(enterprise_id, environment, ...)` -- enterprise policies
- `enterprise-graph.query_nodes(enterprise_id, environment, label, ...)` -- current-state inventory
- `enterprise-graph.count_nodes(enterprise_id, environment, label)` -- topology statistics
- `enterprise-graph.get_impact(enterprise_id, environment, start_keys, depth)` -- blast radius analysis
- `enterprise-graph.get_tmf_coverage(workspace_id, tmf_kind, active_only)` -- TMF standards coverage

## Design Principles

Carry forward from legacy EA agent, extended with workspace topology and cascade governance guidance in `../references/cascade-governance.md`.

- **Strategic, not tactical**: Produce enterprise-level guardrails, capability maps, and governance -- not component-level specs. Breadth over depth.
- **Framework-aligned**: Align to TOGAF ADM phases, Zachman perspectives, or FEAF layers as appropriate. Cite framework alignment explicitly.
- **Capability-driven**: Map business capabilities before selecting technology. Prioritize by business value, maturity gap, and strategic alignment.
- **Governance-first**: Define governance policies, review gates, waivers, and compliance controls before downstream design begins. EA governance is the enforcement mechanism for architectural consistency.
- **NFR envelopes**: Define enterprise-wide NFR budget envelopes (latency, availability, security class, cost) that SA must allocate within. Do not specify per-component targets -- that is SA's job.
- **Current-state aware**: When enterprise-graph is available, ground decisions in actual topology -- what exists today, what the blast radius of changes is, where constraints apply.
- **TM Forum strategic alignment**: Map capabilities to ODA functional blocks and eTOM process areas. Use TMF MCP for evidence when available.
- **Stable IDs**: Use `cap-<kebab>` for capabilities, `gov-<kebab>` for governance policies, `adr-<NNN>` for decisions. Never renumber.
- **Workspace-kind-aware**: EA operates on `enterprise` workspaces. If workspace is `domain`, `project`, or `component`, redirect to `solution-architecture` or `domain-architecture`.
- **Cascade governance (human-gate)**: EA is the cascade origin. Do not advance the `enterprise_architecture` layer beyond `draft` without explicit user approval. Advancement signals SA that enterprise guardrails are baselined.
- **Topology as planning surface**: Use workspace topology to see the full enterprise structure -- which domains and projects exist, their current cascade state, and their relationship to the enterprise plan. This is the EA's primary coordination view.
- **Portfolio rationalization**: When assessing portfolio, use enterprise-graph current-state to identify actual applications, overlaps, and dependencies -- not just declared architecture.

## Workflow (deterministic, phased)

### Phase 0: Workspace, Topology, and Cascade Resolution

1. Resolve workspace deterministically:
   - Use explicit `workspace_id` when provided.
   - If no explicit `workspace_id`, search/list and auto-select only when exactly one clear candidate.
   - If multiple candidates, present top 2-3 and ask user to choose.

2. Check workspace kind:
   - If `workspace_kind = enterprise`: proceed with full EA workflow.
   - If `workspace_kind = domain`, `project`, or `component`: warn and suggest `solution-architecture` or `domain-architecture` instead.
   - If `workspace_kind = unknown`: warn user and ask to set workspace kind.

3. Discover enterprise topology:
   - If `openarchitect` MCP is available, discover child workspaces (domains, projects) linked to this enterprise workspace.
   - Build a topology overview: which domains exist, which projects, current cascade state of each.
   - Record the topology snapshot for traceability.

4. Check cascade state:
   - Call `get_cascade_state(workspace_id)`.
   - If `requirements` layer is available and `draft`, note that requirements are not yet baselined.
   - Check `enterprise_architecture` layer: if already `approved`, warn about re-editing.

5. Load existing context:
   - Call `get_design_context(workspace_id, "enterprise", "architecture")`.
   - Call `list_artifacts(workspace_id, kind="enterprise_architecture", limit=20)`.

6. Load enterprise current-state (when enterprise-graph is available):
   - Call `list_labels(enterprise_id, environment)` to understand what entity types exist.
   - Call `count_nodes(enterprise_id, environment, label)` for key entity types.
   - Call `list_constraints(enterprise_id, environment)` for existing enterprise policies.
   - This grounds the EA in what actually exists, not just what was planned.

7. Migration-first registration:
   - If repo artifacts exist but workspace lacks them, register before edits when registration tooling is available.
   - If tooling is unavailable, continue in Git-local mode and record that migration/backfill registration was skipped.

### Phase 1: Business Vision, Strategy, and Scoping

8. Load and analyze business vision and strategy:
   - Business vision and strategy documents (primary input -- ask user if not provided):
     - Corporate mission, vision, and strategic pillars.
     - Growth targets, market expansion, M&A plans.
     - Digital transformation objectives and timelines.
     - Competitive positioning and differentiation strategy.
   - Requirements baseline (`architecture/requirements/requirements.yml`) if available.
   - Regulatory and compliance mandates.
   - Existing enterprise architecture artifacts for evolution.

9. Translate strategy into architectural drivers:
   - Business context: industry, market position, strategic objectives, growth trajectory.
   - Strategic priorities: which business capabilities must improve to deliver the strategy.
   - Regulatory context: compliance mandates, jurisdictions, reporting requirements.
   - Technology context: current state summary (from enterprise-graph if available).
   - Investment constraints: budget envelope, timeline horizons, build/buy preferences.
   - Summarize as a strategic brief (5-10 bullets) that anchors all downstream architecture decisions. Every EA output must trace back to a strategic driver.

### Phase 2: Target Architecture Vision

10. Define target architecture:
    - Enterprise vision statement and architecture principles.
    - Domain decomposition: which business domains exist, their boundaries, and interdependencies.
    - Technology strategy: preferred platforms, cloud strategy, build/buy/partner decisions.
    - Integration strategy: enterprise integration patterns, API management, event backbone.
    - Security architecture: identity model, data classification, compliance controls.
    - Write `architecture/enterprise/target-architecture.md` and `target-architecture.yml`.

11. Record enterprise architecture decisions:
    - For each strategic decision, write an ADR to `architecture/enterprise/adr/adr-NNN-<title>.md`.

### Phase 3: Capability Mapping

12. Map business capabilities:
    - Level 1 capabilities (strategic): broad business functions.
    - Level 2 capabilities (tactical): specific capability areas within each L1.
    - For each capability:
      - Current maturity: `initial | developing | defined | managed | optimized`
      - Target maturity: desired state.
      - Strategic priority: `critical | high | medium | low`
      - Owning domain(s): which domain workspace(s) are responsible.
      - TMF alignment: ODA functional block mapping (when TMF MCP available).
    - Write `architecture/enterprise/capability-map.yml`.

### Phase 4: Portfolio Assessment (optional, on request)

13. Assess technology/application portfolio:
    - If enterprise-graph is available, query current-state for applications, services, infrastructure.
    - For each application/technology:
      - Business value: `high | medium | low`
      - Technical health: `green | amber | red`
      - Recommendation: `invest | maintain | migrate | retire`
      - Dependencies and blast radius (from enterprise-graph impact analysis).
    - Identify overlaps, redundancies, and consolidation opportunities.
    - Write `architecture/enterprise/portfolio-assessment.yml`.

### Phase 5: Governance Framework (optional, on request)

14. Define governance framework:
    - Architecture review board structure and cadence.
    - Review gates: what decisions require EA approval.
    - Waiver process: how exceptions are requested, evaluated, and tracked.
    - Standards and policies: technology standards, naming conventions, security policies.
    - Compliance controls: regulatory mapping, audit requirements.
    - Write `architecture/enterprise/governance.yml`.

### Phase 6: Enterprise NFR Envelopes

15. Define enterprise-wide NFR envelopes:
    - Availability tiers: what availability classes exist and which domains fall into each.
    - Latency classes: acceptable latency ranges per tier.
    - Security classification: data sensitivity tiers and corresponding controls.
    - Cost envelopes: budget allocation strategy per domain.
    - These are the budgets that SA must allocate within during solution design.
    - Include in `target-architecture.yml` or as a dedicated section.

### Phase 7: Strategic Roadmap (optional, on request)

16. Create enterprise strategic roadmap:
    - Phase by business value and dependency order.
    - For each phase: initiatives, affected domains, investment, expected outcomes.
    - Map to capability priorities from Phase 3.
    - Write repo-root `ROADMAP.md` (canonical path).

17. Maintain initiative routing artifacts from portfolio decisions:
    - Keep `architecture/portfolio/initiative-pipeline.yml` as the full portfolio lifecycle source (intake, sizing, ROI, prioritization, approvals).
    - Generate runtime selector manifest:
      - `python <skills_root>/enterprise-architecture/scripts/generate_initiatives_selector.py --pipeline architecture/portfolio/initiative-pipeline.yml --out architecture/portfolio/initiatives.yml`
    - Do not manually edit `initiatives.yml` unless recovering from an incident.
    - Validate selector drift (recommended in CI):
      - `python <skills_root>/enterprise-architecture/scripts/generate_initiatives_selector.py --pipeline architecture/portfolio/initiative-pipeline.yml --out architecture/portfolio/initiatives.yml --check`

### Phase 8: Cascade State and Registration

18. Advance cascade state (with human gate):
    - Present enterprise architecture summary:
      - Target architecture defined, capabilities mapped, governance set, NFR envelopes established.
    - Ask user whether to advance `enterprise_architecture` cascade layer from `draft` to `proposed`.
    - Do NOT auto-advance. EA advancement is the cascade origin -- it signals that enterprise guardrails are baselined and SA work can begin on domain/project workspaces.
    - Today this is a manual signal. When Phase 3 cascade triggers ship, this will automatically create/unblock SA tasks in child workspaces.
    - Record/update `governance_signal` in both `target-architecture.yml` and `capability-map.yml`:
      - `cascade_layer = enterprise_architecture`
      - `cascade_recommendation = ready_for_review` when EA is complete and user confirms readiness for advancement review
      - `cascade_recommendation = remediation_required` or `block_advancement` when gaps/blockers remain
      - Include a concrete `note` with approval/defer rationale.

19. Register output artifacts:
    - If workspace artifact registration tooling is available, register:
      - `enterprise_architecture` -> `architecture/enterprise/target-architecture.yml`
      - `capability_map` -> `architecture/enterprise/capability-map.yml`
      - `portfolio_assessment` -> `architecture/enterprise/portfolio-assessment.yml`
      - `governance` -> `architecture/enterprise/governance.yml`
    - If registration tooling is unavailable, skip registration and record the explicit reason in output evidence.
    - Include topology snapshot as traceability metadata.

## Cross-Skill Guidance (Cascade Origin)

This skill is the **top of the design cascade** as defined in `../references/cascade-governance.md`:

1. **Upstream**: Business vision and strategy is the primary driver. `requirement-analysis` may produce a requirements baseline as a secondary input. EA translates strategic intent into architectural guardrails.
2. **Parallel**: `stakeholder-mapping` identifies executive sponsors, architecture board members, and governance decision gates.
3. **Downstream**: `solution-architecture` consumes EA guardrails, NFR envelopes, and domain decomposition to produce solution-level designs in domain/project workspaces.
4. **Downstream (cascade)**: When `enterprise_architecture` reaches `approved`, it signals SA that guardrails are baselined. SA can begin on child workspaces.
5. **Validation**: `constraint-validation` can validate that SA/domain designs conform to EA governance policies.

The cascade flow: `enterprise-architecture` (enterprise_architecture layer) -> `solution-architecture` (solution_architecture layer) -> `domain-architecture` (domain_architecture layer) -> component implementation.

End with a "Next recommended skills" section when appropriate:
- `solution-architecture` for domain/project workspaces once EA is baselined
- `stakeholder-mapping` if governance decision gates are unclear
- `constraint-validation` to verify downstream conformance

## Output Format Rules

- Keep `.md` files concise and decision-oriented; treat `.yml` as canonical for traceability.
- Include a "Context Evidence" section in markdown outputs: workspace_id, enterprise_id, tools used, artifact refs.
- Use `references/target-architecture.yml.template` for structured output shape.
- Use `references/capability-map.yml.template` for capability mapping shape.
- Use `references/initiative-pipeline.yml.template` for portfolio source shape when initializing.
- Generate `architecture/portfolio/initiatives.yml` from `architecture/portfolio/initiative-pipeline.yml` with `scripts/generate_initiatives_selector.py`.
- `target-architecture.yml` and `capability-map.yml` must include top-level `governance_signal`:
  - `workspace_id` (optional), `cascade_layer`, `cascade_recommendation`, `remediation_status`, `note`

## Notes

- Enforce truthfulness: do not claim enterprise-graph evidence without MCP tool results. Do not claim TMF alignment without MCP evidence or explicit local-knowledge notation.
- Preserve stable IDs across iterations; do not renumber capabilities, governance policies, or decisions.
- Never auto-approve, auto-signoff, or auto-advance governance gates; require explicit user confirmation. EA is the cascade origin -- its advancement is the most consequential governance gate.
- When enterprise-graph is unavailable, architecture is "strategically valid" but not "current-state grounded" -- state this explicitly.
- EA does not produce component-level specs. If user asks for component detail, redirect to `solution-architecture` or `domain-architecture`.
- Portfolio assessment without enterprise-graph is based on declared architecture only, not actual topology -- note this limitation.
- This skill works identically whether downstream execution is manual, human-in-the-loop, or agent-driven. EA artifacts are the same governance surface across all modes.
## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
- scripts/generate_initiatives_selector.py (portfolio source -> selector manifest generator)
