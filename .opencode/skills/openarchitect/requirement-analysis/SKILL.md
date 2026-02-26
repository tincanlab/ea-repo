---
name: requirement-analysis
description: Refine raw product/business intake into clear, testable, architect-ready requirements with stable IDs, acceptance criteria, scope boundaries, NFRs, assumptions, dependencies, and a capped/deduped open-questions list. Use for requirement analysis handoffs to solution architecture and downstream domain teams.
---

# Requirement Analysis

## Overview

Turn ambiguous input (tickets, emails, meeting notes, PRDs) into an architecture-ready baseline that downstream design and implementation can execute without reinterpretation.

This skill is legacy-ported and runs as a deterministic phased workflow:
- initial analysis and requirement expansion
- clarification backlog and answer processing
- final baseline freeze
- enrichment mapping (TMF or domain context)
- report generation (default terminal step)

For legacy prompt behavior parity, use:
- `references/prompt-pack.md`
- `agents/sub-agents.yaml`
- `agents/prompts/orchestrator.md`
- `agents/prompts/requirement_expansion.md`
- `agents/prompts/clarification.md`
- `agents/prompts/data_enrichment.md`
- `agents/prompts/report_generation.md`
- `agents/prompts/requirements_analyst.md` (optional deeper decomposition)

## Repository Convention

- Default requirements folder: `architecture/requirements/`
- Canonical baseline files:
  - `requirements.md` for narrative requirements
  - `requirements.yml` for structured, traceable requirements
- Domain refinement (optional, deeper scope):
  - `architecture/domains/<domain>/requirements.md`
  - `architecture/domains/<domain>/requirements.yml`
- Optional enrichment/report files:
  - `enrichment.md`
  - `enrichment.yml`
  - `requirements_report.md`
- If the project uses different paths, state them explicitly in the prompt before running the workflow.

## Outputs (write to repo as separate files)

Core outputs:
- `architecture/requirements/requirements.md`
- `architecture/requirements/requirements.yml`
- `governance_signal` section in `architecture/requirements/requirements.yml` (requirements-layer readiness contract)

Optional domain refinement outputs (when producing domain-level requirements):
- `architecture/domains/<domain>/requirements.md`
- `architecture/domains/<domain>/requirements.yml`

Optional advanced outputs:
- `architecture/requirements/enrichment.md`
- `architecture/requirements/enrichment.yml`
- `architecture/requirements/requirements_report.md`

Use the templates in:
- `references/requirements.md.template`
- `references/requirements.yml.template`
- `references/domain-requirements.md.template`
- `references/domain-requirements.yml.template`
- `references/enrichment.md.template`
- `references/enrichment.yml.template`
- `references/prompt-pack.md` (orchestrator + specialist prompt contract)

Execution prompt assets:
- `agents/sub-agents.yaml` (capability and routing contract)
- `agents/prompts/*.md` (specialist prompt bodies)

## Context Platform Integration

Git-local execution is the default path.
Use MCP servers as optional add-ons when available.

Optional MCP servers:
- `openarchitect` (workspace/artifact indexing add-on)
- `tmf-mcp` (TMF enrichment add-on)

MCP runtime (HTTP, configured in `.cursor/mcp.json`):
- `openarchitect` -> `http://localhost:8101/mcp`
- `tmf-mcp` -> `http://localhost:8000/mcp`

When `openarchitect` MCP is unavailable:
- Continue in Git-local mode and complete the workflow.
- Do not block on workspace selection/creation.
- State that workspace indexing/registration was skipped.
- Do not claim workspace evidence (`workspace_id`, `artifact_id`, cascade state) without MCP tool evidence.

Current limitations in active skills:
- Local workspace-state persistence is not automated.
- Workspace artifact registration is optional and may be unavailable in some environments.

Quality helpers:
- `scripts/detect_repo_context.py` (detect `ENTERPRISE.md`/`SOLUTION.md`/`DOMAIN.md`, infer repo context, and list upstream requirement snapshots in `inputs/`)
- `scripts/validate_requirements.py` (schema + quality checks for `requirements.yml`; blocks accidental `approved`)
- `scripts/validate_enrichment.py` (schema + hierarchy verification checks for `enrichment.yml`)

Discovery-first tool policy:
- At workflow start (and when context changes), discover available tools and bind them by capability.
- Prefer canonical tool names below when present, but do not fail just because an alias/name differs.
- If a required capability is unavailable, continue in degraded mode and record an explicit gap.

Preferred tool aliases by capability:
- Workspace discovery/select/create:
  - `openarchitect.workspaces_list(limit)`
  - `openarchitect.workspaces_search(query, tenant_id, limit)`
  - `openarchitect.workspaces_select(workspace_id|query, tenant_id, candidate_index)`
  - `openarchitect.workspaces_create(name, tenant_id, persist)` (arch profile when create is needed; persist is client-managed)
- Context and artifact retrieval:
  - `openarchitect.get_design_context(workspace_id, domain, level)` (or project equivalent if workspace is unavailable)
  - `openarchitect.get_cascade_state(workspace_id)` (or project equivalent if workspace is unavailable)
  - `openarchitect.list_artifacts(workspace_id, kind, limit)`
- Artifact registration:
  - Register outputs when workspace artifact registration tooling is available.
  - If unavailable, continue in Git-local mode and explicitly record the gap.
- TMF enrichment capabilities (bind by capability first; aliases below are examples):
  - eTOM process search: `search_etom_processes(...)`
  - eTOM hierarchy expansion: `get_process_hierarchy(...)` (or graph hierarchy variant)
  - ODA component search: `search_oda_components(...)`
  - ODA component link traversal: `get_component_links(...)` (or graph link variant)
  - Process/function intersection: `components_by_proc_func(...)`
  - SID entity search: `search_sid_entities(...)`
  - TMF Open API resource/operation mapping: use whichever Open API search/mapping tools are discovered
- Optional async/task capabilities:
  - `openarchitect.submit_task(...)`
  - `openarchitect.get_task(task_id)` / `openarchitect.get_result(task_id)`
  - `openarchitect.list_checkpoints(workspace_id, status, limit)` / `openarchitect.answer_checkpoint(checkpoint_id, answer_segments)`

## Workflow (Legacy-ported, deterministic)

1. Detect repository context at startup:
   - Set `<skills_root>` once for your runtime:
     - OpenCode: `.opencode/skills/openarchitect`
     - Codex: `.codex/skills/openarchitect`
   - Run: `python <skills_root>/requirement-analysis/scripts/detect_repo_context.py`
   - Context routing:
     - If `SOLUTION.md` is present (default), run solution-level requirement analysis.
     - If `DOMAIN.md` is present, read `DOMAIN.md` to identify domain context and inspect `inputs/` for upstream solution requirements.
     - If `DOMAIN.md` is present, ask the user one explicit question before proceeding:
       - "Detected a domain repo (`DOMAIN.md`). Do you want domain-level requirement analysis using upstream inputs?"
     - If `ENTERPRISE.md` only, confirm whether this run should produce enterprise-scoped intake or redirect to solution/domain scope.

2. Start in Git-local mode (default):
   - Read/write `architecture/requirements/requirements.md` and `architecture/requirements/requirements.yml` directly in repo.
   - Do not require workspace selection/creation to proceed.

3. Optional workspace branch (only when `openarchitect` tools are actually available):
   - Resolve workspace explicitly (or via MCP search/list) if you need workspace context/indexing.
   - Load workspace context (`get_design_context`, `get_cascade_state`, `list_artifacts`) when available.
   - Skip this branch entirely if `openarchitect` tools are unavailable.

4. Run phase-driven requirement workflow:
    - At workflow start, offer analysis mode once:
      - `strict`: minimal depth, fastest pass.
      - `balanced`: standard depth (default).
      - `deep`: maximum depth and broader enrichment coverage.
    - Record mode in `requirements.yml.analysis_mode`.
    - `initial_analysis` phase:
      - Normalize intake, restate problem, define scope boundaries, produce expanded requirements and measurable NFRs.
      - Write/update `requirements.md` and `requirements.yml`.
      - After first expansion draft, offer explicit optional deepening by area:
        - `scope`, `nfr`, `integrations`, `compliance`, `data`, `ux`, or `none`.
        - Record selection in `expansion_focus_areas`.
    - `clarification` phase:
      - Maintain one backlog in `requirements.yml.open_questions`.
      - Set clarification profile once (user-selectable, bounded):
        - `strict` -> `max_questions_total = 5`
        - `balanced` -> `max_questions_total = 10` (default)
        - `deep` -> `max_questions_total = 20` (bounded max)
        - `max_new_questions_per_turn` remains bounded (max 5).
      - Never exceed hard safety bound `max_questions_total <= 20`.
      - Dedupe rule: lowercase, strip punctuation, collapse whitespace; skip near-duplicates.
      - Ask exactly one targeted question per turn unless user invites more.
      - Apply user answers in batch and update question status.
      - Do not apply answer processing twice to the same user input.
      - After processing answers, if no updates occurred or all questions are answered, move to next step.
    - `final_processing` phase:
      - Freeze baseline when no open clarification questions remain.
      - Ensure every requirement has acceptance criteria and priority.
      - Ensure assumptions/constraints/dependencies are explicit.
      - Do not auto-approve requirements; keep status as `draft` unless user explicitly approves.
      - Emit/update governance metadata in `requirements.yml`:
        - `source.cascade_readiness = ready_for_advancement_review | not_ready_for_advancement`
        - `governance_signal.cascade_layer = requirements`
        - `governance_signal.cascade_recommendation = ready_for_review | remediation_required | block_advancement`
        - `governance_signal.remediation_status = none | pending | complete`
        - `governance_signal.note` must summarize readiness rationale or blocking gaps.

5. Enrichment phase (recommended after baseline freeze):
    - Trigger enrichment when requirements baseline is stable or user explicitly requests mapping.
    - For each requirement, query TMF context by discovered capability (do not hardcode names):
      - eTOM process search capability:
        - Use discovered alias (for example `search_etom_processes(query, top_k=3)`).
      - eTOM hierarchy expansion capability (when available):
        - Use discovered hierarchy alias (for example `get_process_hierarchy(process_identifier, depth=1, include_siblings=true)`).
        - Include parent/child/sibling as secondary candidates to improve coverage.
        - Keep bounded expansion (depth 1; limited anchors per requirement).
      - ODA component search capability:
        - Use discovered alias (for example `search_oda_components(query, top_k=3)`).
      - Deep mode functional mapping (when corresponding capabilities are available):
        - Derive ODA component candidates from the discovered ODA capability.
        - Use discovered component-link capability (for example `get_component_links(component_id)`) to extract linked Functional Framework functions.
        - Optionally cross-check via discovered process/function intersection capability (for example `components_by_proc_func(process_identifier, function_id)`).
      - SID entity search capability:
        - Use discovered alias (for example `search_sid_entities(query, top_k=3)`).
      - Optional deep mode TMF Open API mapping:
        - Use discovered Open API mapping/search capability when available.
    - Write outputs to:
      - `architecture/requirements/enrichment.yml` (canonical mapping)
      - `architecture/requirements/enrichment.md` (human-readable summary)
    - If TMF MCP or Open API search tooling is unavailable, write a partial enrichment with explicit gaps and no fabricated mappings.
    - Verification gate:
      - If hierarchy tools are available and eTOM anchors exist, verify hierarchy expansion was executed before finalizing.
      - If not executed, run it (or record explicit evidence for why it was skipped).
      - Record verification fields in enrichment evidence.
    - Run quality check before report phase:
      - Run: `python <skills_root>/requirement-analysis/scripts/validate_enrichment.py`

6. Report phase (default final step):
   - Produce `architecture/requirements/requirements_report.md` at the end of the workflow by default.
   - If the user explicitly opts out, note that report generation was skipped by request.
   - Include original intake, expanded requirements, clarification summary, enrichment highlights, risks, and roadmap.

7. Optional artifact registration (workspace add-on only):
    - `requirements_markdown` -> `architecture/requirements/requirements.md`
    - `requirements_structured` -> `architecture/requirements/requirements.yml`
    - `enrichment` -> `architecture/requirements/enrichment.yml`
    - `report` -> `architecture/requirements/requirements_report.md`
    - Register when workspace artifact tooling is available; otherwise record that registration was skipped.

8. Optional runtime-task mode (closest to legacy service behavior):
   - Submit `requirements.intake` via `submit_task` for worker-driven processing.
   - If task returns `needs_input`, use checkpoint tools and continue clarification loop.
   - Then submit `requirements.enrich` and `requirements.report` as separate tasks.
   - Use `get_result` and artifact refs for traceability.

## Cross-Skill Guidance (BA Workflow)

From a business-process perspective, `requirement-analysis`, `stakeholder-mapping`, and `use-case-elaboration` are typically part of one BA workflow, but they are implemented as separate skills so teams can run them independently.

Recommended sequencing:

1. Run `requirement-analysis` to produce/update the baseline:
   - `architecture/requirements/requirements.md`
   - `architecture/requirements/requirements.yml`
   - `requirements.yml.governance_signal` and `source.cascade_readiness` (downstream readiness signal)
2. If the change involves approvals, governance, or cross-domain work, run `stakeholder-mapping` next using the requirements baseline as input.
3. When the baseline is stable enough to design interfaces and sequences, run `use-case-elaboration` to expand into concrete flows.

The skill cannot auto-invoke other skills. It should end with a short "Next recommended skills" section when appropriate, including suggested prompts for the user to run them.

## Output Format Rules

- Use `references/requirements.schema.json` as the contract for `requirements.yml`.
- Use `references/domain-requirements.schema.json` as the contract for `architecture/domains/<domain>/requirements.yml`.
- Use `references/enrichment.schema.json` as the contract for `enrichment.yml`.
- Keep `requirements.md` concise; treat `requirements.yml` as the canonical source for traceability.
- `requirements.yml` must include:
  - `source.cascade_readiness` (`ready_for_advancement_review | not_ready_for_advancement`)
  - `governance_signal.workspace_id` (optional), `governance_signal.cascade_layer`, `governance_signal.cascade_recommendation`, `governance_signal.remediation_status`, `governance_signal.note`
- Keep `enrichment.md` concise; treat `enrichment.yml` as the canonical source for mapping traceability.
- In `requirements.md`, include a short "Context Evidence" section listing tools used and key artifact references; include `workspace_id` only when workspace tools were actually used.
- In `enrichment.md`, cite tool calls and confidence/fit notes for each mapping batch.

## Notes

- Enforce truthfulness: do not claim verified mapping without tool evidence.
- Prefer additive updates and stable IDs; do not renumber existing requirement IDs.
- Preserve open question history and answered records for auditability.
- Never auto-approve, auto-signoff, or auto-advance governance gates; require explicit user confirmation.
