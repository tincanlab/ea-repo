---
name: domain-architecture
description: Detail domain-level architecture within a bounded domain context (e.g., Billing, Order Management, Service Provisioning). Consumes SA handoff component-specs and interface-contracts, produces detailed domain designs, data models, workflow specifications, and integration specs. TM Forum aligned. Use when SA has decomposed system into domains and the next step is domain-depth design, or when refining an existing domain architecture.
---

# Domain Architecture

## Overview

Produce detailed, implementation-ready domain architecture within a specific bounded context. This skill takes SA handoff component-specs and interface-contracts as input and produces domain-depth designs: data models, workflow specifications, detailed API designs, domain events, provisioning logic, and compliance mappings.

Legacy-ported from three separate domain architect agents (billing, COM, SOM). Consolidated into one parameterized skill with domain-specific profiles as reference files.

## Domain Profiles

Domain-specific knowledge (TMF APIs, component patterns, compliance, workflow patterns) lives in reference files rather than hardcoded logic. Read the applicable profile before starting design work:

- `references/profiles/billing.md` -- Billing, charging, rating, payment processing
- `references/profiles/order-management.md` -- Customer order capture, validation, orchestration
- `references/profiles/service-order-management.md` -- Service order management, provisioning, catalog
- `references/profiles/catalog-management.md` -- Product/Service/Resource catalog management (TMF620/633/634, TMFC001/006/010)
- `references/profiles/psr-inventory.md` -- Product/Service/Resource inventory management (TMF637/638/639, TMFC005/008/012)

If the target domain has no profile, the skill operates generically using SA constraints and TMF MCP evidence. New profiles can be added for additional domains (e.g., assurance, partner-management, network-management).

## Repository Convention

- Default deployment model: DA runs in a domain repo separate from the SA solution repo.
- Default domain folder: `architecture/domains/<domain-name>/`
- Canonical output files:
  - `architecture/domains/<domain>/domain-design.md` (narrative domain architecture)
  - `architecture/domains/<domain>/domain-design.yml` (structured domain architecture)
  - `architecture/domains/<domain>/component-specs.yml` (DA-owned component specs)
  - `architecture/domains/<domain>/data-model.yml` (domain data model / entity relationships)
  - `architecture/domains/<domain>/workflows.yml` (domain workflow definitions)
- Required repo-root entrypoints (for domain repos):
  - `DOMAIN.md` (domain repo TOC + progressive links to downstream component/API repos, when they exist)
  - `ROADMAP.md` (DA-owned domain/system/product roadmap; developer-facing implementation targets)
  - `ROADMAP.yml` (optional; machine-readable roadmap roll-up for SA aggregation)
- Non-default co-located mode (DA and SA in one repo): do not overwrite solution root `ROADMAP.md`; write domain roadmap to `architecture/domains/<domain>/ROADMAP.md` instead.
- If the project uses different paths, state them explicitly before running.

## Inputs

This skill consumes the outputs of `solution-architecture`:
- `architecture/solution/architecture-design.yml` (system architecture with domain decomposition)
- `architecture/solution/interface-contracts.yml` (cross-domain interface contracts)
- `architecture/solution/domain-handoffs/<domain>/component-specs.yml` (SA handoff specs for this domain)

And from `requirement-analysis`:
- `architecture/requirements/requirements.yml` (requirements baseline)
- `architecture/requirements/enrichment.yml` (TMF mappings, if available)

If SA artifacts do not exist, ask user whether to run `solution-architecture` first or proceed with ad-hoc domain input.

## Outputs (write to repo as separate files)

Core outputs:
- `architecture/domains/<domain>/domain-design.md`
- `architecture/domains/<domain>/domain-design.yml`
- `architecture/domains/<domain>/component-specs.yml` (DA-owned, produced from SA handoff baseline)

Optional outputs:
- `architecture/domains/<domain>/data-model.yml` (domain entities, relationships, storage strategy)
- `architecture/domains/<domain>/workflows.yml` (state machines, sagas, orchestration flows)
- `architecture/domains/<domain>/adr/` (domain-level architecture decision records)
- `DOMAIN.md` (repo-root domain TOC; use `references/DOMAIN.md.template` when the domain spans downstream repos)
- `ROADMAP.md` (repo-root in domain repos; DA-owned domain/system/product roadmap; use `references/ROADMAP.md.template`)
- `architecture/domains/<domain>/ROADMAP.md` (use in non-default co-located mode to avoid collision with SA `ROADMAP.md`)
- `ROADMAP.yml` (repo-root machine-readable roadmap; use `references/ROADMAP.yml.template`)

## Context Platform Integration

MCP servers (recommended):
- `openarchitect` (workspace/artifact context)

Optional MCP servers:
- `enterprise-graph` (enterprise current-state, constraint validation)
- TMF MCP (eTOM processes, ODA components, SID entities, Open API schemas)

MCP runtime (HTTP, configured in `.cursor/mcp.json`):
- `openarchitect` -> `http://localhost:8101/mcp`
- `enterprise-graph` -> `http://localhost:8102/mcp`
- `tmf-mcp` -> `http://localhost:8000/mcp` (optional)

Degraded mode (when MCP is unavailable):
- The skill can read/write repo artifacts and complete the design workflow locally.
- Must clearly state that workspace context, enterprise validation, and artifact registration were skipped.
- Must not claim workspace or TMF evidence without MCP tool results.

Current limitations in active skills:
- Local workspace-state persistence is not automated.
- Workspace artifact registration is optional and may be unavailable in some environments.

Quality helpers:
- `scripts/validate_domain_design.py` (schema checks for domain-design.yml and component-specs.yml)

MCP tools to use when `openarchitect` is available:
- `openarchitect.workspaces_list(limit)`
- `openarchitect.workspaces_search(query, tenant_id, limit)`
- `openarchitect.workspaces_select(workspace_id|query, tenant_id, candidate_index)`
- `openarchitect.get_design_context(workspace_id, domain, level)`
- `openarchitect.get_cascade_state(workspace_id)`
- `openarchitect.list_artifacts(workspace_id, kind, limit)`

Optional MCP tools (enterprise-graph):
- `enterprise-graph.list_constraints(enterprise_id, environment, ...)`
- `enterprise-graph.query_nodes(enterprise_id, environment, label, ...)`
- `enterprise-graph.get_impact(enterprise_id, environment, start_keys, depth)`

## Design Principles

Carry forward from legacy domain architect agents, extended with workspace topology and cascade governance guidance in `../references/cascade-governance.md`.

- **Domain-bounded**: Each invocation designs within one domain boundary. Do not cross into sibling domains; reference their interface contracts instead.
- **SA-constrained**: Respect SA-level guardrails, NFR budgets, and architectural patterns. If domain design requires deviating from SA constraints, record the deviation as an ADR and flag for SA review.
- **TM Forum depth**: Use domain-specific TMF APIs from the applicable profile. Query TMF MCP for detailed schema and operation alignment. Note gaps explicitly.
- **DDD alignment**: Model domain aggregates, entities, value objects, and domain events. Define bounded context boundaries. Specify anti-corruption layers for external integrations.
- **Workflow-first for orchestration domains**: For domains involving order lifecycle, provisioning, or billing cycles, define state machines and saga patterns with explicit compensating actions.
- **Data model ownership**: Each domain owns its data model. Define storage strategy (relational, event store, CQRS projections) justified by access patterns and consistency requirements.
- **Compliance-aware**: Apply domain-specific compliance (PCI DSS for billing/payment, TM Forum lifecycle for order/service management, regulatory for lawful intercept). Use profile references.
- **Stable IDs**: Continue `comp-<kebab>` and `ifc-<kebab>` IDs from SA. Add domain-specific IDs: `ent-<kebab>` for entities, `wf-<kebab>` for workflows, `evt-<kebab>` for domain events.
- **Cascade governance (human-gate)**: Do not begin domain design if the upstream `solution_architecture` layer is not at least `proposed`. Do not advance the `domain_architecture` cascade layer beyond `draft` without explicit user approval.
- **Workspace-kind-aware**: This skill primarily operates on `domain` workspaces. If the workspace is `component`, refine only that component's domain-internal design. If the workspace is `enterprise` or `project`, redirect to `solution-architecture`.
- **Clear artifact ownership**: DA owns `architecture/domains/<domain>/component-specs.yml`. Treat SA handoff artifacts under `architecture/solution/domain-handoffs/<domain>/` as read-only baseline input.
- **Cross-workspace conformance**: Check that domain interface implementations conform to the SA-level interface contracts. Flag deviations as conformance issues.
- **Topology as context**: Use workspace topology to discover parent SA workspace (for constraints) and sibling domain workspaces (for cross-domain interface verification).

## Workflow (deterministic, phased)

### Phase 0: Workspace, Topology, and Cascade Resolution

1. Resolve workspace deterministically:
   - Use explicit `workspace_id` when provided.
   - If no explicit `workspace_id`, search/list and auto-select only when exactly one clear candidate.
   - If multiple candidates, present top 2-3 and ask user to choose.

2. Check workspace kind and adapt behavior:
   - If `workspace_kind = domain`: full domain architecture workflow.
   - If `workspace_kind = component`: refine one component within domain constraints.
     - This path may be invoked directly by the user or redirected from `solution-architecture` when SA detects a component workspace.
     - Treat it as SA-to-DA handoff mode: consume SA handoff artifacts first, then refine only the targeted component (do not run full-domain decomposition).
   - If `workspace_kind = enterprise` or `project`: warn and suggest `solution-architecture` skill instead.
   - If `workspace_kind = unknown`: warn user and ask to set workspace kind.

3. Discover topology context:
   - If `openarchitect` MCP is available, discover parent and sibling workspaces.
   - Identify: parent SA/domain workspace (upstream constraints), sibling domain workspaces (cross-domain interfaces).
   - Record the topology snapshot for traceability.

4. Check cascade state (governance gate):
   - Call `get_cascade_state(workspace_id)`.
   - If `solution_architecture` layer is `draft` (not yet proposed/approved): warn user that SA design is not yet baselined. Ask whether to proceed or wait.
   - If `solution_architecture` layer is `proposed` or `approved`: proceed normally.
   - Check `domain_architecture` layer: if already `approved`, warn about re-editing.

5. Load existing context:
   - Call `get_design_context(workspace_id, "<domain-name>", "architecture")`.
   - Call `list_artifacts(workspace_id, kind="domain_architecture", limit=20)`.
   - Load parent workspace's architecture-design.yml and interface-contracts.yml for conformance baseline.

6. Migration-first registration:
   - If repo artifacts exist but workspace lacks them, register before edits.
   - If registration tooling is unavailable, continue and record that registration was skipped.

### Phase 1: Domain Context Loading

7. Identify domain and load profile:
   - Determine the target domain from workspace metadata, user input, or folder structure.
   - Read the applicable domain profile from `references/profiles/<domain>.md`.
   - If no profile exists, proceed generically but note the gap.

8. Load SA-level inputs:
    - Read `architecture/solution/architecture-design.yml` for system-level patterns and NFR budgets.
    - Read `architecture/solution/interface-contracts.yml` for contracts this domain must implement.
    - Read `architecture/solution/domain-handoffs/<domain>/component-specs.yml` as the SA baseline handoff.
    - Validate SA handoff against `../solution-architecture/references/component-handoff.schema.json` when validation tooling is available.
    - If the handoff is missing, ask whether to run `solution-architecture` for this domain first.
   - Read `architecture/requirements/requirements.yml` for domain-relevant requirements.
   - Read `architecture/requirements/enrichment.yml` for TMF mappings (if available).

9. Extract domain architectural drivers:
   - NFR budget allocated to this domain from SA.
   - Interface contracts this domain must provide and consume.
   - Domain-specific compliance requirements (from profile).
   - TMF API alignment targets (from profile + enrichment).
   - Summarize in 5-10 bullets as the domain design brief.

### Phase 2: Domain Architecture Design

10. Design domain-internal architecture:
    - Define domain aggregates, entities, value objects, and their relationships.
    - Select domain patterns (DDD aggregates, CQRS, event sourcing, saga) justified by access patterns and consistency requirements.
    - Define storage strategy per aggregate (relational, document, event store, cache).
    - Map to TMF alignment:
      - Query TMF MCP for SID entity alignment (when available).
      - Query TMF MCP for Open API operation details (when available).
      - Use profile default TMF APIs as baseline.
    - Write `architecture/domains/<domain>/domain-design.md` and `domain-design.yml`.

11. Define domain data model:
    - For each aggregate/entity, specify: fields, types, constraints, indexes.
    - Define relationships between entities (one-to-many, many-to-many, references).
    - Map to SID models where applicable.
    - Write to `architecture/domains/<domain>/data-model.yml` (optional, on request or when data model is non-trivial).

12. Record domain architecture decisions:
    - For each significant decision, write an ADR to `architecture/domains/<domain>/adr/adr-NNN-<title>.md`.

### Phase 3: Component Refinement

13. Refine component specifications:
    - Take SA handoff component-specs as baseline. Refine with:
      - Detailed API operations (not just interface refs, but full CRUD + domain operations).
      - Internal component structure (layers, modules, key classes).
      - Data access patterns and storage per component.
      - Error handling and resilience patterns.
    - Write DA-owned output to `architecture/domains/<domain>/component-specs.yml`.
    - Validate refined specs against `references/component-specs.schema.json` (reuse from solution-architecture).

14. Define domain workflows:
    - For orchestration-heavy domains (order management, provisioning, billing cycles):
      - Define state machines with states, transitions, guards, and actions.
      - Define saga patterns with steps and compensating actions.
      - Define lifecycle events emitted at each state transition.
    - Write to `architecture/domains/<domain>/workflows.yml`.

### Phase 4: Interface Implementation Design

15. Design interface implementations:
    - For each interface contract this domain must provide (from SA interface-contracts.yml):
      - Detailed API spec: full request/response schemas, error codes, pagination, auth.
      - Event spec: payload schema, ordering, idempotency, dead-letter handling.
    - For each interface this domain consumes from sibling domains:
      - Anti-corruption layer design: how to map external contracts to domain model.
      - Resilience: circuit breakers, retries, timeouts, fallback behavior.
    - Verify conformance to SA-level interface contracts. Flag deviations.

### Phase 5: Validation

16. Validate against SA constraints:
    - Check NFR budget conformance: do component SLOs fit within SA-allocated budget?
    - Check interface conformance: do implemented interfaces match SA contract schemas?
    - Check pattern conformance: do domain patterns align with SA-level architectural patterns?
    - Record any deviations as issues requiring SA review.

17. Validate against enterprise constraints (optional):
    - If `enterprise-graph` MCP is available, validate against applicable constraints.
    - Reference the `constraint-validation` skill for full validation workflow.

18. Validate TMF alignment:
    - For each TMF API in the domain profile, verify coverage:
      - Which domain components implement which TMF operations?
      - Which SID entities map to which domain entities?
    - Note uncovered TMF APIs as gaps.

### Phase 6: Cascade State and Registration

19. Advance cascade state (with human gate):
    - Present design summary: components refined, workflows defined, interfaces designed, validation results.
    - Ask user whether to advance `domain_architecture` cascade layer from `draft` to `proposed`.
    - Do NOT auto-advance.
    - Advancement signals readiness for component-level implementation. Today manual; Phase 3 cascade triggers will automate.

20. Register output artifacts:
    - `domain_design` -> `architecture/domains/<domain>/domain-design.yml`
    - `component_specs` -> `architecture/domains/<domain>/component-specs.yml`
    - `domain_data_model` -> `architecture/domains/<domain>/data-model.yml`
    - `domain_workflows` -> `architecture/domains/<domain>/workflows.yml`
    - Register artifacts when tooling is available; otherwise explicitly record the skip.
    - Include topology snapshot as traceability metadata.

## Cross-Skill Guidance (Cascade Position)

This skill sits below SA in the design cascade:

1. **Upstream**: `solution-architecture` produces the system design, component-specs, and interface-contracts this skill consumes. SA solution_architecture layer must be at least `proposed`. For `workspace_kind=component`, SA may explicitly redirect to DA; DA then runs in component-scoped refinement mode.
2. **Parallel**: `stakeholder-mapping` may identify domain-specific decision gates.
3. **Downstream**: `constraint-validation` validates against enterprise policy.
4. **Downstream (cascade)**: When `domain_architecture` reaches `approved`, signals readiness for component implementation tasks.
5. **Sibling**: Other domain-architecture invocations for sibling domains. Cross-domain interfaces should be verified for compatibility.

The cascade flow: `requirement-analysis` -> `solution-architecture` -> `domain-architecture` -> component implementation.

End with a "Next recommended skills" section when appropriate, including:
- `constraint-validation` if enterprise validation was skipped
- Sibling `domain-architecture` for related domains not yet designed
- Component implementation guidance if cascade state is advanced

## Output Format Rules

- `component-specs.yml` must validate against the shared `component-specs.schema.json`.
- SA handoff input `architecture/solution/domain-handoffs/<domain>/component-specs.yml` should conform to `../solution-architecture/references/component-handoff.schema.json`.
- Keep `.md` files concise and decision-oriented; treat `.yml` as canonical for traceability.
- Include a "Context Evidence" section in markdown outputs: workspace_id, domain, tools used, artifact refs.
- Use `references/domain-design.yml.template` for structured output shape.
- Use `references/domain-design.md.template` for narrative structure.

## Notes

- Enforce truthfulness: do not claim TMF alignment without MCP evidence or profile-sourced knowledge (cite which).
- Preserve stable IDs across iterations; do not renumber components, interfaces, entities, or workflows.
- Never auto-approve, auto-signoff, or auto-advance governance gates; require explicit user confirmation.
- If SA constraints are missing, designs are "domain-internally consistent" but not "SA-validated" -- state this.
- SA deviations must be recorded as ADRs and flagged for SA review. Do not silently override SA patterns.
- This skill works identically for manual, human-in-the-loop, or agent-driven downstream execution.
## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
