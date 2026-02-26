---
name: solution-architecture
description: Design solution architectures from requirements baselines - system decomposition, component specs, interface contracts, NFR budgets, integration patterns, SLO/SLI, and implementation roadmaps. TM Forum aligned (eTOM/SID/ODA/Open APIs). Use when requirements are stable and the next step is technical design, or when reviewing/evolving an existing architecture.
---

# Solution Architecture

## Overview

Translate architecture-ready requirements into concrete, traceable design artifacts: system architecture, component specifications, interface contracts, NFR budgets, integration patterns, and implementation roadmaps. Aligned to TM Forum standards (eTOM, SID, ODA, Open APIs) where applicable.

This skill is legacy-ported from the SA agent runtime. It runs as a deterministic phased workflow driven by the LLM, not by hardcoded tool stubs.

## Repository Convention

- Default deployment model: SA and DA run in separate repositories.
- Solution repo entrypoints (repo root):
  - `SOLUTION.md` (human TOC for this solution)
  - `VISION.md` (SA-owned long-term intent and target outcomes)
  - `ROADMAP.md` (SA-owned solution/initiative/project roadmap; aggregates domain roadmaps from domain repos)
  - `solution-index.yml` (machine-authoritative scope manifest: domains, repos, entrypoints)
- Default solution folder: `architecture/solution/`
- Non-default co-located mode only: `architecture/domains/<domain-name>/`
- Canonical output files:
  - `architecture/solution/architecture-design.md` (narrative system architecture)
  - `architecture/solution/architecture-design.yml` (structured architecture)
  - `architecture/solution/interface-contracts.yml` (canonical interface contracts)
  - `architecture/solution/domain-handoffs/<domain>/component-specs.yml` (SA-to-DA handoff component specs per domain)
- If the project uses different paths, state them explicitly before running.

## Inputs

This skill consumes the outputs of `requirement-analysis`:
- `architecture/requirements/requirements.yml` (structured requirements baseline)
- `architecture/requirements/requirements.md` (narrative requirements)
- Optionally: `architecture/requirements/enrichment.yml` (TMF mappings)
- Optionally: `architecture/requirements/stakeholders.yml` (decision gates)

If requirements artifacts do not exist, the skill asks the user whether to run requirement-analysis first or proceed with ad-hoc input.

## Outputs (write to repo as separate files)

Core outputs:
- `SOLUTION.md`
- `VISION.md`
- `ROADMAP.md`
- `solution-index.yml`
- `architecture/solution/architecture-design.md`
- `architecture/solution/architecture-design.yml`
- `architecture/solution/interface-contracts.yml`

Provisioning outputs (Git-first; Context Registry DB optional):
- `architecture/solution/repo-plan.yml`
- `architecture/solution/repo-creation-request.yml`

Context Registry DB add-on outputs (only when DB routing/provisioning is enabled):
- `architecture/solution/workspace-plan.yml`
- `architecture/solution/workspace-creation-request.yml`

Per-domain outputs (when decomposition produces domain boundaries):
- `architecture/solution/domain-handoffs/<domain>/component-specs.yml` (input handoff for DA)

Optional outputs:
- `ROADMAP.yml` (optional; machine-readable roadmap roll-up generated from `ROADMAP.md`; use `references/ROADMAP.yml.template`)
- `architecture/solution/adr/` (architecture decision records)
- `architecture/validation/validation_report.yml` (constraint validation results)
- `architecture/solution/workspace-creation-request.md` (human approval summary)
- `architecture/solution/repo-creation-request.md` (human approval summary)

## Context Platform Integration

MCP servers (optional add-ons):
- `openarchitect` (Context Registry DB: workspace/artifact index + MCP tools)
- `enterprise-graph` (enterprise current-state, constraint validation, topology)
- TMF MCP (eTOM processes, ODA components, SID entities, Open API schemas)

MCP runtime (HTTP, configured in `.cursor/mcp.json`):
- `openarchitect` -> `http://localhost:8101/mcp`
- `enterprise-graph` -> `http://localhost:8102/mcp`
- `tmf-mcp` -> `http://localhost:8000/mcp` (optional)

Git-only mode (when MCP is unavailable or intentionally unused):
- The skill can read/write repo artifacts and complete the design workflow using Git as the source of truth.
- Must clearly state that Context Registry indexing/registration and enterprise validation were skipped.
- Must not claim DB workspace evidence or enterprise compliance without MCP tool evidence.

Current limitations in active skills:
- Local workspace-state persistence is not automated.
- Workspace artifact registration is optional and may be unavailable in some environments.

Quality helpers:
- `scripts/validate_component_specs.py` (schema checks for SA handoff component specs and `interface-contracts.yml`)

If `openarchitect` MCP is available, use these tools:
- `openarchitect.workspaces_list(limit)`
- `openarchitect.workspaces_search(query, tenant_id, enterprise_id, limit)`
- `openarchitect.workspaces_select(workspace_id|query, tenant_id, enterprise_id, candidate_index)`
- `openarchitect.get_workspace(workspace_id)`
- `openarchitect.get_design_context(workspace_id, domain, level)`
- `openarchitect.get_cascade_state(workspace_id)`
- `openarchitect.list_artifacts(workspace_id, kind, limit)`
- `openarchitect.list_workspace_relations(workspace_id|source_workspace_id|target_workspace_id, relation_type, status, limit)`
- `openarchitect.list_workspace_repos(workspace_id, limit)`

Optional MCP tools (enterprise-graph):
- `enterprise-graph.list_constraints(enterprise_id, environment, ...)`
- `enterprise-graph.get_constraint(enterprise_id, environment, constraint_id)`
- `enterprise-graph.query_nodes(enterprise_id, environment, label, ...)`
- `enterprise-graph.get_impact(enterprise_id, environment, start_keys, depth)`
- `enterprise-graph.get_tmf_coverage(workspace_id, tmf_kind, active_only)`

## Design Principles

Carry forward from legacy SA agent, extended with workspace topology and cascade governance guidance in `../references/cascade-governance.md`.

- **NFR-first**: Define latency, availability, throughput, cost, and security budgets before selecting patterns. Ensure traceability from NFRs to component SLOs and test/telemetry hooks.
- **TM Forum alignment**: Map to eTOM processes, SID models, ODA components. Prefer TMF Open APIs. Use MCP evidence when available; note gaps explicitly when not.
- **Security-by-design**: Enforce privacy/regulatory controls (PII classification, GDPR, lawful intercept where applicable). Define SLO/SLI and operability standards (runbooks, golden signals).
- **Contracts over prose**: Prefer interface contracts (API specs, event schemas, data contracts) over narrative descriptions. Contracts are the enforceable surface for both human and agent consumers.
- **Stable IDs**: Use `comp-<kebab>` for components, `ifc-<kebab>` for interfaces, `adr-<NNN>` for decisions. Never renumber.
- **Design, not operations**: Produce architectures, contracts, and roadmaps. Do not embed runtime tasks.
- **Static workspace/repo policy, SA-owned planning**: Treat workspace and repo policies as static platform rules. SA defines required workspaces/repos, checks current mappings, and emits creation requests; SA does not directly execute provisioning.
- **Git-authoritative solution scope**: Treat `solution-index.yml` as the machine-authoritative definition of solution scope (domains, repos, entrypoints). `SOLUTION.md` is a human TOC that points to the index and canonical artifacts. Any DB registry is optional and derived.
- **Workspace-kind-aware**: Check `workspace_kind` on the resolved workspace. SA primarily operates on `domain` or `project` workspaces. If the workspace is `enterprise`, the skill produces strategic architecture (patterns, guardrails, capability map) not component-level specs. If the workspace is `component`, redirect to `domain-architecture` for component-internal design.
- **Clear artifact ownership**: SA does not write domain-internal files under `architecture/domains/<domain>/`. SA writes handoff artifacts under `architecture/solution/domain-handoffs/<domain>/`; DA owns domain-local files.
- **Cascade governance (human-gate)**: Respect the cascade lifecycle. Do not begin SA work if the upstream requirements layer is not at least `proposed`. Do not advance the `solution_architecture` cascade layer beyond `draft` without explicit user approval. Automation starts after human approval at each gate (`draft` -> `proposed` -> `approved`).
- **Cross-workspace contract awareness**: When decomposing interfaces that cross domain boundaries, structure contracts with explicit `provider_workspace` and `consumer_workspace` fields. This prepares for the Phase 2 cross-workspace interface contract mechanism (see `../references/cascade-governance.md`). Today, register the contract in the owning workspace and note the cross-workspace dependency for manual follow-up.
- **Topology as coordination backbone**: Use workspace topology to discover context: what domain this workspace belongs to, what sibling components exist, what enterprise-level constraints apply. The topology graph is the same coordination surface whether execution is fully manual, human-in-the-loop, or agent-driven.
- **Component dependency capture**: When decomposing into components, explicitly record which component interfaces depend on which other component interfaces. This prepares for Phase 4 dependency ordering even though the `component_depends_on` relation type does not yet exist.

## Workflow (deterministic, phased)

### Phase 0: Workspace, Topology, and Cascade Resolution

Before workspace selection (or in Git-only mode), establish repo entrypoints:
- Ensure `solution-index.yml` exists (use `references/solution-index.yml.template`).
- Ensure `SOLUTION.md` exists (use `references/SOLUTION.md.template`).
- Keep `solution-index.yml` as the authoritative list of domain repos and entrypoints.
- `SOLUTION.md` should include direct human-friendly links to domain repo entrypoints (for example `DOMAIN.md`/`AGENTS.md`), and must stay consistent with `solution-index.yml`.

1. Resolve workspace deterministically:
   - Use explicit `workspace_id` when provided.
   - If no explicit `workspace_id`, search/list and auto-select only when exactly one clear candidate.
   - If multiple candidates, present top 2-3 and ask user to choose.

2. Check workspace kind and adapt behavior:
   - Call `get_workspace(workspace_id)` or inspect workspace metadata.
   - If `workspace_kind = enterprise`: produce strategic architecture (capability map, guardrails, NFR budget envelopes, domain decomposition plan). Do not produce component-level specs.
   - If `workspace_kind = domain` or `project`: full SA workflow (architecture design, component decomposition, interface contracts, SLOs).
   - If `workspace_kind = component`: stop SA decomposition and redirect to `domain-architecture` for component-internal design.
   - If `workspace_kind = unknown`: warn user and ask them to set the workspace kind before proceeding.

3. Discover topology context:
   - If `openarchitect` MCP is available, call `get_workspace_topology(workspace_id, direction="both", depth=1)` (when available) or `list_workspace_relations(workspace_id)`.
   - Identify: parent enterprise/domain workspace (upstream constraints), sibling component workspaces (peer interfaces), linked project workspaces (cross-cutting scope).
   - Record the topology snapshot (workspace IDs and relation types) for traceability. This is the baseline for this design cycle.

4. Check cascade state (governance gate):
   - Call `get_cascade_state(workspace_id)`.
   - Check upstream layer status:
     - If `requirements` layer is `draft` (not yet proposed/approved): warn user that requirements are not yet baselined. Ask whether to proceed with draft requirements or wait.
     - If `requirements` layer is `proposed` or `approved`: proceed normally.
   - Check current `solution_architecture` layer status:
     - If already `approved`: warn that re-editing an approved design will require re-approval. Ask user to confirm.
     - If `draft` or `proposed`: proceed.

5. Load existing design context:
   - Call `get_design_context(workspace_id, "solution", "architecture")`.
   - Call `list_artifacts(workspace_id, kind="architecture", limit=20)`.
   - If parent domain/enterprise workspace is known from topology, load its constraints and interface contracts for conformance checking.

6. Migration-first registration:
    - If repo artifacts exist but workspace lacks them, register before edits:
      - `architecture_design` -> `architecture/solution/architecture-design.yml`
      - `interface_contracts` -> `architecture/solution/interface-contracts.yml`
      - `component_specs_handoff` -> `architecture/solution/domain-handoffs/<domain>/component-specs.yml`
    - If registration tooling is unavailable, continue and record that registration was skipped.

### Phase 1: Requirements Intake and Scoping

7. Load and validate requirements baseline:
   - Read `architecture/requirements/requirements.yml` and `requirements.md`.
   - If enrichment exists, read `architecture/requirements/enrichment.yml` for TMF mappings.
   - If stakeholders exist, read `architecture/requirements/stakeholders.yml` for decision gates.
   - If requirements are missing, ask user whether to run `requirement-analysis` first.

8. Extract architectural drivers:
   - Identify key NFRs (latency, availability, throughput, cost, security) with measurable targets.
   - Identify integration constraints and dependencies.
   - Identify regulatory/compliance requirements.
   - If parent workspace constraints were loaded in step 5, incorporate them as additional drivers.
   - Summarize in 5-10 bullets as the design brief.

### Phase 2: System Architecture Design

9. Design system architecture:
   - Define system boundaries, deployment topology, and major component groupings.
   - Select architecture patterns (microservices, event-driven, API-first, CQRS, etc.) justified by NFR drivers.
   - Map to TM Forum alignment where applicable:
     - Query TMF MCP for ODA component candidates (when available).
     - Query TMF MCP for eTOM process alignment (when available).
     - Note TMF gaps explicitly if MCP unavailable.
   - Define NFR budget allocation per component/tier.
   - Write `architecture/solution/architecture-design.md` and `architecture-design.yml` (use `references/architecture-design.yml.template` which includes topology snapshot and cascade context).

10. Produce strategic blueprint (recommended before detailed contracts):
   - Use the `strategic_blueprint` specialist to create a decision-ready strategic blueprint.
   - Include target-state posture, transition phases, top risks, and mitigation options.
   - Keep this strategic layer consistent with requirement IDs and architecture drivers.

11. Record architecture decisions:
    - For each significant decision, write an ADR to `architecture/solution/adr/adr-NNN-<title>.md`.
    - ADR format: Status, Context, Decision, Consequences, Alternatives Considered.

### Phase 3: Component Handoff and Interface Contracts

12. Decompose into components:
    - For each domain boundary identified in Phase 2, create `architecture/solution/domain-handoffs/<domain>/component-specs.yml`.
    - Treat this as SA handoff scope only (external interfaces, ownership boundaries, required dependencies). Do not perform domain-internal design in SA.
    - Each component must have: `id` (comp-kebab), `description`, `provided_interfaces`, `consumed_interfaces`.
    - Validate against `references/component-handoff.schema.json`.
    - For each component, record explicit dependencies on other components' interfaces in the `dependencies` section (with `required_before` phase). This captures build ordering even before the platform supports `component_depends_on` relation types.

13. Define interface contracts:
    - For each inter-component boundary, add entry to `architecture/solution/interface-contracts.yml`.
    - Each interface must have: `id` (ifc-kebab), `type` (api|event), `owner_component_id`, `version`, `spec_path`.
    - Validate against `references/interface-contracts.schema.json`.
    - For API interfaces, specify: method, path, request/response schema, auth, rate limits.
    - For event interfaces, specify: topic, schema (avro/json), ordering guarantees, retention.

14. Handle cross-workspace interface contracts:
    - If an interface crosses domain boundaries (provider in domain A, consumer in domain B), add `cross_workspace` metadata:
      - `provider_workspace_id`, `consumer_workspace_ids` (when known from topology)
      - `provider_domain`, `consumer_domains` (human-readable)
    - Register the contract in the provider's workspace. Note the cross-workspace dependency explicitly in the contract's `notes` field.
    - Today this is a manual follow-up; when the Phase 2 cross-workspace artifact reference mechanism ships, this metadata enables automated linking.
    - Do not fabricate workspace IDs; use topology evidence or ask the user.

### Phase 4: NFR and SLO Definition

15. Define SLO/SLI per component:
    - Availability target, latency p50/p95/p99, error budget, throughput.
    - Observability requirements: traces, metrics, alerts, dashboards.
    - Map SLOs back to requirement NFRs for traceability.
    - Include in component-specs or as annotations in architecture-design.yml.

### Phase 5: Integration and Delivery Patterns

16. Define integration patterns:
    - For each cross-component or external integration:
      - Pattern: sync REST, async event, streaming, batch.
      - Resiliency: circuit breakers, retries, bulkheads, timeouts.
      - Data contract: schema, versioning, backward compatibility.
    - Define coexistence/cutover strategy when replacing legacy systems:
      - Strangler fig, canary, feature flags, data migration approach.
    - Include in interface-contracts.yml or as separate integration specs.

### Phase 6: Workspace Planning and Request Generation (DB Add-on)

17. Define workspace plan and check existing candidates:
    - Draft `architecture/solution/workspace-plan.yml` (use `references/workspace-plan.yml.template`).
    - For each required domain/project/component boundary, decide workspace action: reuse existing workspace or request new workspace.
    - Use `workspaces_search(query, tenant_id, enterprise_id)` to record existing matches.
    - Use `list_workspace_relations(workspace_id=...)` to record relation updates needed after creation (for example `project_in_domain`, `component_in_domain`).
    - For any proposed create action, include explicit `reason` and required `workspace_kind`.

18. Generate workspace creation request artifact:
    - If new workspaces are needed, write `architecture/solution/workspace-creation-request.yml` (use `references/workspace-creation-request.yml.template`).
    - Include: `name`, `enterprise_id`, `workspace_kind`, `created_by`, `reason`, and required relation upserts.
    - If no new workspaces are needed, still write the file with `workspaces_requested: []` and `execution.state: not_required` for deterministic audit trace.
    - This skill only generates requests; execution is handled by the `workspace-creation` skill.

### Phase 7: Repository Planning and Request Generation (Git-first)

19. Define repository plan and check existing mappings:
    - Draft `architecture/solution/repo-plan.yml` (use `references/repo-plan.yml.template`).
    - For each deployable ownership boundary, decide repo strategy: reuse existing repo or request new repo.
    - Call `list_workspace_repos(workspace_id)` and mark existing mappings in `repo-plan.yml`.
    - For any proposed non-default repo target, mark `requires_explicit_selection: true`.

20. Generate repo creation request artifact:
    - If new repositories are needed, write `architecture/solution/repo-creation-request.yml` (use `references/repo-creation-request.yml.template`).
    - Include: `repo_key`, owner, name, visibility, default-for-workspace flag, `purpose` (`design|domain|api|infra|other`), reason, and source components.
    - If no new repositories are needed, still write the file with `repos_requested: []` and `execution.state: not_required` to keep a deterministic audit trail.
    - This skill only generates requests; execution is handled by the `repo-creation` skill, which also updates repo-root `solution-index.yml` in Git-only mode.

### Phase 8: Validation (optional, when enterprise-graph is available)

21. Validate against enterprise constraints:
    - If `enterprise-graph` MCP is available:
      - Call `list_constraints(enterprise_id, environment, ...)`.
      - For each applicable constraint, evaluate proposed architecture.
      - Record results in `architecture/validation/validation_report.yml`.
    - If unavailable, note that enterprise validation was skipped.
    - Reference the `constraint-validation` skill for full validation workflow.

22. Validate conformance to parent workspace constraints:
    - If topology identified a parent domain or enterprise workspace in Phase 0:
      - Load parent workspace's architecture artifacts and constraints.
      - Check that component interfaces conform to parent-defined interface schemas.
      - Check that technology choices conform to parent-defined stack policies (when available).
      - Note any conformance gaps explicitly.

### Phase 9: Roadmap (optional, on request)

23. Create implementation roadmap:
    - Phase deliverables by dependency order and risk.
    - Use the component dependency graph from Phase 3 step 12 to sequence work: components providing interfaces must be designed/approved before consumers.
    - For each phase: duration, components, deliverables, dependencies, acceptance criteria.
    - Write to repo-root `ROADMAP.md` (canonical path).

### Phase 10: Cascade State and Registration

24. Advance cascade state (with human gate):
    - After all design artifacts are written and validated, present a summary to the user:
      - Components defined, interfaces specified, workspace/repo plan status, validation results, open questions.
    - Ask user whether to advance `solution_architecture` cascade layer from `draft` to `proposed`.
    - Do NOT auto-advance. The user must explicitly confirm.
    - If user approves advancement: update cascade state via MCP (when available). Note that this signals readiness for downstream work (component-level implementation in child workspaces). Today this is a manual signal; when Phase 3 cascade triggers ship, this will automatically create/unblock component tasks.

25. Register output artifacts:
    - `architecture_design` -> `architecture/solution/architecture-design.yml`
    - `interface_contracts` -> `architecture/solution/interface-contracts.yml`
    - `component_specs_handoff` -> `architecture/solution/domain-handoffs/<domain>/component-specs.yml` (per domain)
    - `workspace_plan` -> `architecture/solution/workspace-plan.yml`
    - `workspace_creation_request` -> `architecture/solution/workspace-creation-request.yml`
    - `repo_plan` -> `architecture/solution/repo-plan.yml`
    - `repo_creation_request` -> `architecture/solution/repo-creation-request.yml`
    - Register artifacts when tooling is available; otherwise explicitly record the skip.
    - Include the topology snapshot from Phase 0 step 3 as traceability metadata.

## Cross-Skill Guidance (Cascade Position)

This skill sits in the middle of the design cascade as defined in `../references/cascade-governance.md`:

1. **Upstream**: `requirement-analysis` produces the requirements baseline this skill consumes. Requirements layer must be at least `proposed` before SA begins (cascade gate).
2. **Parallel**: `stakeholder-mapping` identifies decision gates for architecture review sign-off.
3. **Parallel/Downstream**: `workspace-creation` consumes `workspace-plan.yml` and `workspace-creation-request.yml` to verify/create required workspaces and apply relation updates.
4. **Parallel/Downstream**: `repo-creation` consumes `repo-plan.yml` and `repo-creation-request.yml` to verify/create repos and update workspace repo mappings.
5. **Downstream**: `constraint-validation` validates designs against enterprise policy (can run as part of Phase 8 or independently).
6. **Downstream (cascade)**: When `solution_architecture` layer reaches `approved`, this signals readiness for component-level work. Today this is manual; with Phase 3 cascade triggers it will auto-create component tasks in child workspaces.
7. **Downstream**: `domain-architecture` consumes SA handoff specs from `architecture/solution/domain-handoffs/<domain>/component-specs.yml` and produces domain-internal `architecture/domains/<domain>/component-specs.yml`.
8. **Roadmap boundary**: SA `ROADMAP.md` is solution/initiative/project scope. DA `ROADMAP.md` is domain/system/product scope in domain repos.

The cascade flow: `requirement-analysis` (requirements layer) -> `solution-architecture` (solution_architecture layer) -> component implementation (implementation layer).

End with a "Next recommended skills" section when appropriate, including:
- `workspace-creation` when `workspace-creation-request.yml` contains requested workspaces
- `repo-creation` when `repo-creation-request.yml` contains requested repos
- `constraint-validation` if enterprise-graph validation was skipped
- Component-level implementation if cascade state is advanced
- `stakeholder-mapping` if decision gates are unclear

## Output Format Rules

- `architecture/solution/domain-handoffs/<domain>/component-specs.yml` must validate against `references/component-handoff.schema.json`.
- `interface-contracts.yml` must validate against `references/interface-contracts.schema.json`.
- Keep `.md` files concise and decision-oriented; treat `.yml` as canonical for traceability.
- Include a "Context Evidence" section in markdown outputs: workspace_id, tools used, artifact refs.
- Use `references/SOLUTION.md.template` for the repo-root solution entrypoint.
- Use `references/solution-index.yml.template` for the machine-authoritative scope manifest.
- Use `references/architecture-design.yml.template` for system architecture structure (includes topology snapshot and cascade context).
- Use `references/component-handoff.yml.template` for SA-to-DA component handoff artifacts.
- Use `references/component-specs.md.template` and `references/interface-contracts.md.template` for narrative structure.
- Use `references/workspace-plan.yml.template` and `references/workspace-creation-request.yml.template` for workspace planning outputs.
- Use `references/repo-plan.yml.template` and `references/repo-creation-request.yml.template` for repository planning outputs.

## Notes

- Enforce truthfulness: do not claim TMF alignment without MCP evidence or explicit notation of local knowledge.
- Preserve stable IDs across iterations; do not renumber components or interfaces.
- Never auto-approve, auto-signoff, or auto-advance governance gates; require explicit user confirmation. This is the human-gate principle from `../references/cascade-governance.md`.
- When enterprise-graph is unavailable, designs are "locally valid" but not "enterprise validated" -- state this explicitly.
- Prefer additive updates; do not remove components/interfaces without recording the decision in an ADR.
- Cross-workspace contracts are a known Phase 2 gap. Structure contracts with provider/consumer workspace metadata now so they are ready for automated cross-workspace linking when that capability ships.
- Component dependency ordering is a known Phase 4 gap. Capture `dependencies` in component-specs now so the platform can compute build order when `component_depends_on` relations are available.
- Topology pinning is a known Phase 3 gap. Record the topology snapshot at skill start for traceability; when pinning is implemented, this becomes the formal cascade baseline.
- SA should not directly create workspaces or GitHub repositories. SA defines required workspaces/repos and emits request artifacts; execution is delegated to `workspace-creation` and `repo-creation` skills with separately controlled access.
- This skill works identically whether the downstream executor is a human developer, a human+agent pair, or a fully autonomous agent. The artifacts and contracts are the same coordination surface across all execution modes.
## Execution Prompt Assets

- agents/sub-agents.yaml (capability and routing contract)
- agents/prompts/orchestrator.md (workflow controller prompt)
- agents/prompts/*.md (specialist prompt bodies)
