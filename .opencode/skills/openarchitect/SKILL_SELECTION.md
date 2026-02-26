# OpenArchitect Skill Selection Guide

Use this guide to pick the right skill and understand how `governance_signal` moves between skills.

## Fast Routing

1. Need enterprise strategy, guardrails, and capability priorities?
   - Run `enterprise-architecture`.
2. Need to capture project intake into the portfolio pipeline before EA routing?
   - Run `project-intake`.
3. Need to turn intake into architecture-ready requirements?
   - Run `requirement-analysis`.
4. Need stakeholder approvals, RACI, and decision gates for requirements?
   - Run `stakeholder-mapping`.
5. Need concrete use-case flows tied to requirement IDs?
   - Run `use-case-elaboration`.
6. Need solution-level decomposition and cross-domain contracts?
   - Run `solution-architecture`.
7. Need domain-internal design from SA handoff?
   - Run `domain-architecture`.
8. Need policy/constraint conformance evidence?
   - Run `constraint-validation`.
9. Need repository planning/creation for produced artifacts?
   - Run `repo-creation`.
10. Need TMF design package and service scaffolding?
   - Run `tmf-domain-architect`, then `tmf-developer`.
11. Need a quick health check before deeper work?
   - Run `quick-start`.

## Decision Tree

1. Are you defining enterprise-wide direction first?
   - Yes: `enterprise-architecture`.
   - No: continue.
2. Do you need to create or update `architecture/portfolio/initiative-pipeline.yml` first?
   - Yes: `project-intake`.
   - No: continue.
3. Do you already have a stable requirements baseline (`architecture/requirements/requirements.yml`)?
   - No: `requirement-analysis`.
   - Yes: continue.
4. Are governance approvals or decision gates unclear?
   - Yes: `stakeholder-mapping`.
   - No: continue.
5. Are end-to-end user/business flows still ambiguous?
   - Yes: `use-case-elaboration`.
   - No: continue.
6. Are you designing across multiple domains/components?
   - Yes: `solution-architecture`.
   - No: continue.
7. Are you refining one domain (or a redirected component workspace)?
   - Yes: `domain-architecture`.
   - No: continue.
8. Do you need formal pass/fail evidence against constraints?
   - Yes: `constraint-validation`.
9. Do outputs require repo provisioning or mapping updates?
   - Yes: `repo-creation`.

## Governance Signal Flow

`governance_signal` contract: `common/references/schemas/governance-signal.schema.json`

Normal signal flow:

1. `requirement-analysis` emits requirements-layer readiness in:
   - `architecture/requirements/requirements.yml`
2. `stakeholder-mapping` emits governance readiness evidence in:
   - `architecture/requirements/stakeholders.yml`
3. `use-case-elaboration` emits requirements-readiness evidence in:
   - `architecture/requirements/use-cases.yml`
4. `enterprise-architecture` emits EA readiness for downstream SA in:
   - `architecture/enterprise/target-architecture.yml`
   - `architecture/enterprise/capability-map.yml`
5. `solution-architecture` and `domain-architecture` consume upstream signals and perform human-gated cascade advancement.
6. `constraint-validation` emits recommendation signals (`ready_for_review | remediation_required | block_advancement`) without mutating cascade state.
7. `tmf-domain-architect` and `tmf-developer` emit advisory governance signals only; architecture skills remain the mutators.

Interpretation guideline:

1. `ready_for_review`: proceed to human gate/approval.
2. `remediation_required`: fix gaps before promotion.
3. `block_advancement`: stop downstream progression until resolved.

## Recommended Sequences

Architecture baseline:

1. `requirement-analysis`
2. `stakeholder-mapping` (when approvals matter)
3. `use-case-elaboration` (when flow detail is needed)
4. `solution-architecture`
5. `domain-architecture`
6. `constraint-validation`
7. `repo-creation` (if provisioning is needed)

Enterprise-first:

1. `project-intake`
2. `enterprise-architecture`
3. `solution-architecture`
4. `domain-architecture`
5. `constraint-validation`

TMF implementation track:

1. `tmf-domain-architect`
2. `tmf-developer`

## Notes

- Git artifacts are the default source of truth.
- MCP usage is additive unless a specific skill step depends on MCP-only evidence.
- If unsure between adjacent skills, choose the upstream skill first.
