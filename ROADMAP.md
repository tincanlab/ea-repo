# ROADMAP (Enterprise)

Owner: Enterprise Architect (EA)

Purpose: a single enterprise roadmap that aggregates solution roadmaps and reconciles cross-solution dependencies and constraints.

Authoring contract:
- Humans edit `ROADMAP.md` only.
- Tools/skills generate `ROADMAP.yml` from this file (do not hand-edit `ROADMAP.yml`).

## Scope

- Enterprise key: `enterprise-01`
- Time horizon: 2026-2027
- Solution sources: solution repo `ROADMAP.md` / optional `ROADMAP.yml`
- Provenance evidence: solution/domain repo `inputs/` snapshots (when needed)

## Current Status

- Health: `green`
- Current theme: `EA foundation established`
- Next theme: `Domain solution architecture`
- Top enterprise risks:
  - None identified

## Roadmap

### Themes / Initiatives

- `ea-init`: Initialize EA repository with baseline artifacts: 2026-Q1
- `product-catalog`: Deploy TMF620 Product Catalog Management API: 2026-Q2
- `order-management`: Deploy TMF629 Order Management API: 2026-Q3
- `billing-integration`: Integrate TMF635 Billing and Accounts Receivable: 2026-Q4

### Milestones

- `EA repo initialized`: 2026-Q1: Baseline EA artifacts committed and validated
- `TMF620 live`: 2026-Q2: Product catalog API available for integration
- `TMF629 live`: 2026-Q3: Order management with product catalog integration
- `Full stack demo`: 2026-Q4: End-to-end product-to-bill workflow demonstrated

### Cross-Solution Dependencies

- `order-management` depends on `product-catalog`: Order creation requires valid product references: 2026-Q2
- `billing-integration` depends on `order-management`: Billing triggers on order completion: 2026-Q3

### Solution Roll-Up (Links)

- None yet

## Decision Log

- `2026-02-21`: Initialize EA repo with placeholder artifacts
- `2026-02-21`: Define demo EA vision with TM Forum ODA alignment
- `2026-02-21`: Establish cloud-first, API-first architecture principles
