# Domain Profile: Catalog Management (Product, Service, Resource)

## Domain Scope

Unified catalog architecture spanning Product Catalog (TMF620/TMFC001), Service Catalog (TMF633+TMF657/TMFC006), and Resource Catalog (TMF634/TMFC010). Owns lifecycle management of specifications, offerings, candidates, categories, pricing, and import/export across all three catalog tiers.

## Precedence Rule

**Resource -> Service -> Product.** Downstream catalogs never redefine upstream entities. They must validate via upstream APIs and subscribe to upstream events. On conflict, prefer the upstream catalog spec and document rationale.

## Core TMF APIs

| API ID | ODA Component | Name | Role in Domain |
|---|---|---|---|
| TMF620 | TMFC001 | Product Catalog Management | Commercial constructs -- specifications, offerings, pricing, bundles, categories |
| TMF633 | TMFC006 | Service Catalog Management | Service specifications (CFSS/RFSS), candidates, categories, lifecycle |
| TMF657 | TMFC006 | Service Quality Management | Service level specifications (SLO/SLS) bound to service catalog |
| TMF634 | TMFC010 | Resource Catalog Management | Resource specifications, candidates, categories, logical/physical/software capabilities |

Additional TMF APIs to consider based on context:
- TMF671: Promotion Management (product promotions)
- TMF701: Process Flow Management (catalog workflows)
- TMF632: Party Management (authoring party identity)
- TMF669: Party Role Management (RBAC for catalog authoring vs publishing)
- TMF651: Agreement Management (agreement terms for offerings)
- TMF662: Entity Catalog Management (generic entity catalog)
- TMF673/674/675: Geographic Address/Site/Location (geo-eligibility)

## Catalog Boundaries

| Catalog | Key Resources | Owns |
|---|---|---|
| **Product (TMF620)** | catalog, category, productSpecification, productOffering, productOfferingPrice, bundles, importJob/exportJob | Commercial constructs, pricing, promotions, channel exports |
| **Service (TMF633/657)** | catalog, category, serviceSpecification (CFSS/RFSS), serviceCandidate, serviceLevelSpecification | Delivered service definitions, SLO/SLS, quality artifacts |
| **Resource (TMF634)** | resourceCatalog, resourceCategory, resourceSpecification, resourceCandidate, importJob/exportJob | Technical capability definitions, logical/physical/software |

## Typical Components

| Component Pattern | Purpose | Technology Patterns |
|---|---|---|
| Product Catalog Service | ProductSpec, ProductOffering, pricing CRUD + lifecycle | API-first, ETag/If-Match for concurrent updates |
| Service Catalog Service | ServiceSpec (CFSS/RFSS), SLO/SLS management | API-first, versioned specs |
| Resource Catalog Service | ResourceSpec, capability definitions, discovery | API-first, import/export pipelines |
| Catalog Import/Export Engine | Bulk ingestion and extraction across all three tiers | Batch processing, idempotent imports, SLI tracking |
| Catalog Event Publisher | Lifecycle and attribute change events per TMFC spec | Event streaming, correlation-id, DLQ policy |
| Catalog RBAC Gateway | Authoring vs publishing access control | TMF669 enforcement, policy-based |

## Domain Workflows

- **Specification lifecycle**: Draft -> Review -> Published -> Deprecated -> Retired (with version branching)
- **Offering lifecycle**: Draft -> Approved -> Active -> Suspended -> End-of-life
- **Import/export**: Job submitted -> Validation -> Processing -> Complete/Failed (with retry + DLQ)
- **Cross-catalog validation**: Product references Service spec -> validate exists in TMF633; Service references Resource spec -> validate exists in TMF634

## Compliance Requirements

| Standard | Applicability | Key Controls |
|---|---|---|
| TM Forum ODA (TMFC001/006/010) | All catalog operations | Strict per-spec CRUD operations, event contracts, RBAC |
| TMF669 RBAC | Authoring and publishing | Role-based access: catalog author, catalog publisher, catalog admin |
| Data governance | Specification versioning | Additive-by-default, deprecation windows, backward compatibility |

## Data Model Patterns

- **Product aggregate**: ProductCatalog -> Category -> ProductSpecification -> ProductOffering -> ProductOfferingPrice
- **Service aggregate**: ServiceCatalog -> Category -> ServiceSpecification (CFSS/RFSS) -> ServiceCandidate -> ServiceLevelSpecification
- **Resource aggregate**: ResourceCatalog -> ResourceCategory -> ResourceSpecification -> ResourceCandidate
- **Cross-catalog references**: ProductSpec.serviceSpecification[] (refs TMF633), ServiceSpec.resourceSpecification[] (refs TMF634)
- **Key consistency requirement**: Cross-catalog referential integrity at write time; quarantine or reject invalid references

## Integration Patterns

- **Upstream (consumed by)**: Ordering domains (product/service/resource ordering uses catalog for validation and eligibility)
- **Downstream (consumes)**: Resource catalog is upstream to service catalog, service catalog is upstream to product catalog
- **External**: Channel management (product catalog exports), partner portals, pricing engines
- **Pattern**: Sync for CRUD and validation; event-driven for lifecycle propagation across tiers; batch for import/export

## Anti-Corruption Layers

- Legacy catalog migration: strangler fig with dual-read during transition; new writes go to new catalog, reads fall through to legacy if not found
- External pricing engines: adapter behind product offering price interface
- Partner catalog sync: facade normalizing partner catalog formats to TMF620 import contracts
