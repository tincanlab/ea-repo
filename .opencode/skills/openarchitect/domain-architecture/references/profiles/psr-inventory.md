# Domain Profile: PSR Inventory (Product, Service, Resource Inventory)

## Domain Scope

Unified inventory management spanning Product Inventory (TMF637/TMFC005), Service Inventory (TMF638/TMFC008), and Resource Inventory (TMF639/TMFC012). Owns lifecycle management of instantiated products, services, and resources -- the "what is actually deployed and assigned" layer, as opposed to catalogs which define "what can exist."

## Precedence Rule

**ResourceInventory -> ServiceInventory -> ProductInventory.** Downstream inventories never redefine upstream entities. They must validate via upstream inventories and subscribe to upstream events. Catalog consistency checks (TMF620/TMF633/TMF634) are required when creating or modifying inventory items.

## Core TMF APIs

| API ID | ODA Component | Name | Role in Domain |
|---|---|---|---|
| TMF637 | TMFC005 | Product Inventory Management | Customer-assigned product instances, lifecycle, organization, auditing |
| TMF638 | TMFC008 | Service Inventory Management | CFS/RFS instances, CFS-to-RFS mapping, lifecycle, monitoring |
| TMF639 | TMFC012 | Resource Inventory Management | Logical/physical/software resource instances, topology, configuration tracking |

Additional TMF APIs to consider based on context:
- TMF620: Product Catalog (consistency checks for product instances)
- TMF633/TMF657: Service Catalog (consistency checks for service instances)
- TMF634: Resource Catalog (consistency checks for resource instances)
- TMF632: Party Management (customer/owner identity)
- TMF669: Party Role Management (RBAC)
- TMF673/674/675: Geographic Address/Site/Location (resource location)
- TMF651: Agreement Management (agreement terms for product instances)

## Inventory Boundaries

| Inventory | Key Resources | Owns |
|---|---|---|
| **Product Inventory (TMF637)** | Product instances assigned to parties | Customer product lifecycle, organization, search/filter, monitoring/tracking, auditing, catalog consistency |
| **Service Inventory (TMF638)** | CFS/RFS instances | Service instance lifecycle, CFS-to-RFS mapping, organization, monitoring, catalog consistency |
| **Resource Inventory (TMF639)** | Logical/physical/software resource instances | Resource instance lifecycle, topology, discovery, configuration tracking and verification, catalog consistency |

## Typical Components

| Component Pattern | Purpose | Technology Patterns |
|---|---|---|
| Product Inventory Service | Product instance CRUD, party assignment, lifecycle | API-first, ETag/If-Match for concurrent updates |
| Service Inventory Service | CFS/RFS instance management, mapping | API-first, CQRS for fast status reads |
| Resource Inventory Service | Resource instance lifecycle, topology management | API-first, graph-aware topology queries |
| Resource Discovery Engine | Auto-discovery of physical/logical resources | Polling + event-driven, reconciliation pipeline |
| Configuration Tracker | Resource configuration verification and drift detection | Snapshot comparison, compliance checks |
| Inventory Event Publisher | Lifecycle and state change events per TMFC spec | Event streaming, correlation-id, DLQ policy |
| Catalog Consistency Checker | Validate inventory items against catalog specs | Batch + on-write validation |

## Domain Workflows

- **Product instance lifecycle**: Created -> Active -> Suspended -> Terminated (with catalog consistency on create/modify)
- **Service instance lifecycle**: Designed -> Reserved -> Active -> Suspended -> Terminated (CFS/RFS mapping maintained throughout)
- **Resource instance lifecycle**: Planned -> Available -> Reserved -> Active -> Decommissioned (with configuration tracking)
- **Resource discovery**: Scan network -> Match to catalog spec -> Create/update inventory -> Reconcile drift
- **Cross-inventory consistency**: Product instance references Service instance(s) -> validate in TMF638; Service instance references Resource instance(s) -> validate in TMF639

## Compliance Requirements

| Standard | Applicability | Key Controls |
|---|---|---|
| TM Forum ODA (TMFC005/008/012) | All inventory operations | Strict per-spec CRUD, event contracts, RBAC |
| TMF669 RBAC | Inventory operations | Role-based access: inventory operator, inventory auditor, inventory admin |
| Asset management regulations | Resource inventory | Asset tracking, depreciation records, audit trails |
| Network compliance | Resource configuration | Configuration verification, drift detection, compliance snapshots |

## Data Model Patterns

- **Product Inventory aggregate**: Product -> ProductCharacteristic -> ProductRelationship -> ProductPrice -> RelatedParty
- **Service Inventory aggregate**: Service -> ServiceCharacteristic -> ServiceRelationship -> SupportingResource -> RelatedParty
- **Resource Inventory aggregate**: Resource -> ResourceCharacteristic -> ResourceRelationship -> Place -> RelatedParty
- **Cross-inventory references**: Product.service[] (refs TMF638 instances), Service.supportingResource[] (refs TMF639 instances)
- **Key consistency requirement**: Cross-inventory referential integrity enforced at write time; catalog consistency checked against TMF620/633/634; configuration drift detected via periodic reconciliation

## Integration Patterns

- **Upstream (triggers)**: Ordering/provisioning domains create inventory items (COM triggers product inventory, SOM triggers service/resource inventory)
- **Downstream (consumed by)**: Assurance (monitors service/resource instances), billing (product instances for rating), reporting
- **External**: Network management systems (resource discovery), OSS (configuration management), asset management
- **Pattern**: Sync for CRUD and consistency checks; event-driven for lifecycle state propagation; batch for discovery/reconciliation; graph queries for resource topology

## Anti-Corruption Layers

- Network element management: adapter per vendor behind unified resource inventory interface
- Legacy inventory migration: strangler fig with inventory federation (query both, write to new); reconciliation jobs to detect and resolve mismatches
- Cloud infrastructure inventory: adapter for cloud provider APIs (AWS/Azure/GCP) mapping to TMF639 resource model
- Enterprise graph sync: inventory changes propagate to enterprise current-state graph via event-driven updates

## Relationship to Enterprise Graph

The PSR Inventory domain is a primary source of truth that feeds the enterprise current-state graph. When `enterprise-graph` MCP is available:
- Resource inventory items map to canonical nodes in the enterprise graph
- Resource topology relationships map to canonical edges
- Configuration changes propagate as graph updates
- Consistency between inventory and enterprise graph should be verified periodically

This makes PSR Inventory a key integration point between the design-time architecture (OpenArchitect workspaces) and the runtime current-state (enterprise graph).
