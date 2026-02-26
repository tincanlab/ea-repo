# Domain Profile: Billing

## Domain Scope

Billing, charging, rating, usage tracking, invoice generation, payment processing, revenue management, and financial settlement.

## Core TMF APIs

| API ID | Name | Role in Domain |
|---|---|---|
| TMF678 | Customer Bill Management | Bill lifecycle, bill presentment |
| TMF676 | Payment Management | Payment processing, refunds, settlement |
| TMF670 | Usage Consumption | Usage record collection and aggregation |
| TMF666 | Account Management | Customer account lifecycle |
| TMF635 | Usage Management | Usage event mediation and rating |
| TMF677 | Payment Methods | Payment instrument management |
| TMF632 | Party Management | Party/customer identity for billing |
| TMF669 | Party Role Management | Billing roles and responsibilities |

Additional TMF APIs to consider based on context:
- TMF667: Document Management (invoice attachments, statements)
- TMF701: Process Flow Management (billing cycle workflows)
- TMF637: Product Inventory (rated product instances)
- TMF620: Product Catalog (pricing and offer definitions)

## Typical Components

| Component Pattern | Purpose | Technology Patterns |
|---|---|---|
| Rating Engine | Real-time usage rating, tariff application | Stream processing, in-memory cache for tariff lookup |
| Invoice Generator | Bill cycle execution, invoice rendering | Batch processing, template engine |
| Payment Processor | Payment orchestration, gateway integration | Saga pattern, idempotent operations |
| Usage Tracker | Usage event collection, mediation | Event streaming, dedup pipeline |
| Account Manager | Account lifecycle, balance management | CQRS for balance reads vs writes |
| Revenue Assurance | Reconciliation, leakage detection | Batch analytics, anomaly detection |

## Domain Workflows

- **Bill cycle**: Scheduled -> Usage aggregation -> Rating -> Tax calculation -> Invoice generation -> Presentment -> Payment due
- **Payment processing**: Payment initiated -> Validation -> Gateway submission -> Settlement -> Reconciliation (with compensating actions for failures)
- **Dispute/adjustment**: Dispute filed -> Review -> Credit/debit adjustment -> Rebilling (if applicable)

## Compliance Requirements

| Standard | Applicability | Key Controls |
|---|---|---|
| PCI DSS | Payment card data handling | Tokenization, encryption at rest/transit, access control, audit logging |
| SOX | Financial reporting accuracy | Audit trail, segregation of duties, change management |
| GDPR | Customer PII in billing records | Data minimization, right to erasure, consent management |
| Revenue recognition (ASC 606 / IFRS 15) | Multi-element arrangements | Revenue allocation, contract modification tracking |

## Data Model Patterns

- **Account aggregate**: Account -> BillingProfile -> PaymentMethods -> BillHistory
- **Usage aggregate**: UsageRecord -> RatedUsage -> UsageSummary
- **Invoice aggregate**: Invoice -> InvoiceLineItem -> TaxDetail -> PaymentAllocation
- **Key consistency requirement**: Balance operations require strong consistency; usage aggregation can be eventual

## Integration Patterns

- **Upstream**: Product catalog (pricing), order management (subscription activation)
- **Downstream**: Revenue assurance, financial reporting, collections
- **External**: Payment gateways (Stripe, Adyen), tax services, banking settlement
- **Pattern**: Event-driven for usage ingestion; sync for payment processing; batch for bill cycles

## Anti-Corruption Layers

- Payment gateway integration: adapter per gateway vendor behind a unified payment interface
- Tax calculation: external tax service behind a tax calculation interface (varying by jurisdiction)
- Legacy billing migration: strangler fig with dual-write during transition
