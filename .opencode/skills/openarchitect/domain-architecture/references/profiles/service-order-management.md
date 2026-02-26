# Domain Profile: Service Order Management (SOM)

## Domain Scope

Service order decomposition, service provisioning orchestration, service catalog management, service inventory, activation/deactivation lifecycle, and network resource coordination.

## Core TMF APIs

| API ID | Name | Role in Domain |
|---|---|---|
| TMF641 | Service Ordering Management | Service order lifecycle |
| TMF642 | Alarm Management | Service alarm correlation |
| TMF643 | Service Quality Management | Service quality monitoring |
| TMF644 | Service Activation & Configuration | Service provisioning execution |

Additional TMF APIs to consider based on context:
- TMF638: Service Inventory Management (service instance tracking)
- TMF633: Service Catalog Management (service specifications)
- TMF640: Service Activation & Configuration (activation workflows)
- TMF639: Resource Inventory Management (underlying resource tracking)

## Typical Components

| Component Pattern | Purpose | Technology Patterns |
|---|---|---|
| Service Catalog Manager | Service specification lifecycle, feasibility | API-first, versioned catalog |
| Service Order Orchestrator | Service order decomposition and fulfillment | State machine, saga pattern |
| Provisioning Engine | Service activation, configuration push | Workflow engine, idempotent commands |
| Service Inventory | Service instance tracking, current state | CQRS (fast status reads, consistent writes) |
| Resource Coordinator | Network/infra resource allocation | Integration layer to network management |
| Service Quality Monitor | SLA monitoring, threshold alerting | Stream processing, metrics pipeline |

## Domain Workflows

- **Service order lifecycle**: Acknowledged -> In-Progress -> Designed -> Reserved -> Provisioned -> Active (with cancel/failed/suspended branches)
- **Provisioning saga**: Decompose order -> Reserve resources -> Configure network elements -> Activate service -> Update inventory -> Confirm (compensating: release resources, rollback config, deactivate)
- **Service modification**: Change request -> Impact assessment -> Schedule -> Execute provisioning delta -> Verify -> Update inventory
- **Service deactivation**: Deactivation request -> Graceful drain -> Deactivate -> Release resources -> Archive

## Compliance Requirements

| Standard | Applicability | Key Controls |
|---|---|---|
| TM Forum Service Lifecycle | Service state management | Standard state transitions per TMF641 |
| Network change management | Provisioning impact | Change window enforcement, rollback procedures |
| SLA compliance | Service quality | Continuous monitoring, breach notification |
| Regulatory (lawful intercept) | Service activation | Conditional intercept hooks during activation |

## Data Model Patterns

- **ServiceOrder aggregate**: ServiceOrder -> ServiceOrderItem -> ServiceCharacteristic -> ServiceOrderRelationship
- **Service aggregate**: Service -> ServiceCharacteristic -> ServiceRelationship -> SupportingResource
- **Resource aggregate**: Resource -> ResourceCharacteristic -> ResourceRelationship
- **Key consistency requirement**: Provisioning operations require idempotency and rollback capability; service inventory updates require strong consistency; resource reservations use distributed locking with TTL

## Integration Patterns

- **Upstream**: Customer order management (order decomposition trigger), product catalog (service specs)
- **Downstream**: Network management systems, resource provisioning controllers, service assurance
- **External**: Network element managers (NEM), SDN controllers, virtualization platforms
- **Pattern**: Saga for multi-step provisioning; async commands for network operations (long-running); event-driven for status propagation; sync for feasibility/inventory checks

## Anti-Corruption Layers

- Network element integration: adapter per vendor/technology (Ericsson, Nokia, Huawei) behind unified provisioning interface
- Legacy OSS integration: facade normalizing legacy CORBA/SOAP interfaces to REST/event patterns
- Cloud/NFV integration: adapter for cloud-native provisioning (Kubernetes, OpenStack) vs traditional network provisioning

## Quality Attributes (SOM-specific)

- **Traceability**: Every provisioning step must be auditable (who, what, when, result)
- **Auditability**: Full change history for service instances and resource allocations
- **Consistency**: Service inventory must reflect actual network state; reconciliation process for drift detection
- **Reliability**: Provisioning failures must not leave partial state; rollback to last known good configuration
