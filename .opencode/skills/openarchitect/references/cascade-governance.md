# Cascade Governance Reference (Shared)

This shared reference defines the design cascade contract for OpenArchitect skills in Git-only and containerized environments.

## Canonical Layer Order

1. `requirements` (when present)
2. `enterprise_architecture` (when present)
3. `solution_architecture`
4. `domain_architecture`
5. `implementation` (downstream execution)

## Governance Gates

- Human gate required for all layer promotion actions.
- Do not auto-advance any layer beyond `draft`.
- Progression intent:
  - `draft` -> working baseline
  - `proposed` -> review-ready
  - `approved` -> downstream-unblocking signal

## Layer Roles

- **Enterprise architecture**:
  - Defines enterprise guardrails and governance constraints.
  - Acts as the cascade origin for architecture policy.
- **Solution architecture**:
  - Consumes requirements and enterprise guardrails.
  - Produces cross-domain solution design and SA-to-DA handoff artifacts.
- **Domain architecture**:
  - Refines SA handoffs into domain-bounded internal design artifacts.
  - Prepares implementation-ready domain contracts and component boundaries.

## Draft-Mode Execution

- `requirements` is the cascade intake layer and has no upstream architecture gate; it produces the baseline readiness signal for downstream design skills.
- SA work should not start if upstream requirements are below `proposed`, unless the user explicitly accepts draft-mode execution.
- DA work should not start if `solution_architecture` is below `proposed`, unless the user explicitly accepts draft-mode execution.

## Cross-Workspace Contract Guidance

- For contracts crossing domain boundaries, include explicit provider and consumer workspace metadata for traceability.
