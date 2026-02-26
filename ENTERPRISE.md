# ENTERPRISE

This repo is the authoritative, Git-first entrypoint for enterprise architecture (EA) artifacts and roll-ups across solution repos.

Start here:
- `VISION.md` (EA-owned long-term enterprise direction and guardrails)
- `ROADMAP.md` (EA-owned enterprise roadmap; roll-up across solutions)
- `AGENTS.md` (how to work in this repo)

## Scope

- Enterprise key: `enterprise-01`
- Owners:
  - EA: `Enterprise Architecture Team`

## Canonical Artifacts (This Repo)

- Target architecture (narrative): `architecture/enterprise/target-architecture.md`
- Target architecture (structured): `architecture/enterprise/target-architecture.yml`
- Capability map: `architecture/enterprise/capability-map.yml`
- Portfolio assessment: `architecture/enterprise/portfolio-assessment.yml`
- Governance: `architecture/enterprise/governance.yml`

## Solutions (External Solution Repos)

Human quick links:
- [Product Catalog (TMF620)](https://github.com/tincanlab/product-catalog/blob/main/ROADMAP.md)
- [Order Management (TMF629)](https://github.com/tincanlab/order-management/blob/main/ROADMAP.md)
- [Customer Management (TMF622)](https://github.com/tincanlab/customer-management/blob/main/ROADMAP.md)
- [Billing (TMF635)](https://github.com/tincanlab/billing/blob/main/ROADMAP.md)

EA roll-up behavior:
- EA reads each solution repo `ROADMAP.md` (human) and optional `ROADMAP.yml` (machine) to build the enterprise roadmap.
- EA can inspect domain repo `inputs/` snapshots (via solution->domain links) to understand cross-solution timelines and conflicts.

## Enterprise Domains

| Domain ID | Name | TMF API | Solution Repo | Status |
|-----------|------|---------|---------------|--------|
| `domain-product` | Product Catalog | TMF620 | [product-catalog](https://github.com/tincanlab/product-catalog) | Planned |
| `domain-order` | Order Management | TMF629 | [order-management](https://github.com/tincanlab/order-management) | Planned |
| `domain-customer` | Customer Management | TMF622 | [customer-management](https://github.com/tincanlab/customer-management) | Planned |
| `domain-billing` | Billing | TMF635 | [billing](https://github.com/tincanlab/billing) | Planned |

## TM Forum Alignment

This enterprise architecture is aligned with TM Forum Open Digital Architecture (ODA):

- **Product Catalog Management** - TMF620 Product Catalog Management API
- **Order Management** - TMF629 Order Management API
- **Customer Party Management** - TMF622 Customer Party Management API
- **Billing and Accounts Receivable** - TMF635 Billing and Accounts Receivable API

For more details, see `architecture/enterprise/target-architecture.yml` and `architecture/enterprise/capability-map.yml`.
