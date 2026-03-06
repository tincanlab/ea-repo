# ENTERPRISE

EA portfolio repo entrypoint. Routes initiatives to solution repos via the Git-first decomposition cascade.

## Read First

1. This file - enterprise context and navigation

## Parent

Not applicable

## Critical File Contract

- Keep required section headings from this template.
- Do not rename or delete required sections.
- Keep this file concise: identity, routing semantics, and links.
- Put detailed/mutable operational values in canonical artifacts and link them here.
- If a required section has no content, keep it and write `Not applicable`.

## Knowledge Store Layout

```text
ENTERPRISE.md                             <- you are here
AGENTS.md                                 <- repo-specific agent instructions
VISION.md                                 <- (optional) EA direction and guardrails
ROADMAP.md                                <- (optional) cross-solution roadmap
architecture/
|-- portfolio/
|   |-- initiative-pipeline.yml           <- portfolio source of truth
|   `-- initiatives.yml                   <- selector catalog (INITIATIVE_ID routing)
`-- enterprise/
    |-- domain-registry.yml               <- domain governance registry
    |-- target-architecture.md            <- (optional)
    |-- capability-map.yml                <- (optional)
    |-- portfolio-assessment.yml          <- (optional)
    `-- governance.yml                    <- (optional)
```

## Canonical Artifacts

- `architecture/portfolio/initiative-pipeline.yml` (portfolio lifecycle source)
- `architecture/portfolio/initiatives.yml` (runtime routing selector)
- `architecture/enterprise/domain-registry.yml` (enterprise domain governance)
- `architecture/enterprise/target-architecture.yml` (target architecture detail, scope, TMF alignment)
- `architecture/enterprise/capability-map.yml` (capability mapping)
- `architecture/enterprise/governance.yml` (governance framework)
- `architecture/enterprise/portfolio-assessment.yml` (portfolio assessment)

## Routing

`INITIATIVE_ID` -> `initiatives.yml` -> `solution_repo_url` + `solution_entrypoint`

## Policy

- Active-only routing; fail-closed on non-active status.
- Automation routes via selector catalogs; humans follow `SOLUTION.md` links in target repos.

## Solutions (External)

- `product-catalog`: https://github.com/tincanlab/product-catalog/blob/main/SOLUTION.md
- `order-management`: https://github.com/tincanlab/order-management/blob/main/SOLUTION.md
- `customer-management`: https://github.com/tincanlab/customer-management/blob/main/SOLUTION.md
- `billing`: https://github.com/tincanlab/billing/blob/main/SOLUTION.md

## Enterprise Identity

See `architecture/enterprise/target-architecture.yml` for:
- Enterprise key: `enterprise-01`
- Vertical: Telco
- Standards Baseline: TM Forum (ODA, eTOM, Open APIs)
- Owners: Enterprise Architecture Team
- Full domain registry (35 TMF ODA components)
- TMF alignment details
