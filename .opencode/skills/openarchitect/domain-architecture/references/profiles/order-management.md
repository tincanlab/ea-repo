# Domain Profile: Customer Order Management (COM)

## Domain Scope

Customer-facing order capture, order validation, business rule evaluation, order orchestration, fulfillment coordination, fallout management, and order lifecycle tracking.

## Core TMF APIs

| API ID | Name | Role in Domain |
|---|---|---|
| TMF620 | Product Catalog Management | Product/offer lookup for order validation |
| TMF622 | Product Ordering Management | Order lifecycle, order item management |
| TMF637 | Product Inventory Management | Inventory check, reservation, allocation |

Additional TMF APIs to consider based on context:
- TMF663: Shopping Cart Management (pre-order basket)
- TMF666: Account Management (customer account for order context)
- TMF632: Party Management (customer identity)
- TMF691: Federated Identity Management (customer auth)

## Typical Components

| Component Pattern | Purpose | Technology Patterns |
|---|---|---|
| Order Capture | Customer-facing order entry, basket management | API-first, stateless, validation pipeline |
| Order Validation Engine | Business rule evaluation, eligibility checks | Rule engine, configurable policy |
| Order Orchestration Engine | Multi-step order fulfillment coordination | Saga pattern, state machine |
| Inventory Manager | Stock/capacity check, reservation | CQRS (fast reads, consistent writes) |
| Order Tracking | Order status visibility, notifications | Event-driven, read model projection |
| Fallout Management | Exception handling, manual intervention queue | Work queue, escalation rules |

## Domain Workflows

- **Order lifecycle**: Draft -> Submitted -> Validated -> In-Progress -> Fulfilled -> Completed (with cancel/reject/fallout branches)
- **Order orchestration saga**: Validate -> Reserve inventory -> Initiate provisioning -> Activate billing -> Confirm (with compensating actions: release inventory, cancel provisioning, reverse billing)
- **Fallout handling**: Exception detected -> Categorize -> Auto-retry OR Manual queue -> Resolution -> Resume order flow

## Compliance Requirements

| Standard | Applicability | Key Controls |
|---|---|---|
| TM Forum Order Lifecycle | Order state management | Standard state transitions, audit trail |
| Consumer protection regulations | Order commitments, cancellation rights | Cooling-off period, clear pricing disclosure |
| GDPR | Customer PII in orders | Data minimization, consent, erasure |

## Data Model Patterns

- **Order aggregate**: ProductOrder -> OrderItem -> OrderItemAction -> OrderNote
- **Cart aggregate**: ShoppingCart -> CartItem -> CartPrice
- **Inventory aggregate**: InventoryReservation -> ReservedItem -> AllocationRecord
- **Key consistency requirement**: Order state transitions require strong consistency with saga compensation; inventory reservations use optimistic locking with TTL-based expiry

## Integration Patterns

- **Upstream**: Product catalog (offers, eligibility), customer management (account context)
- **Downstream**: Service order management (provisioning trigger), billing (activation), fulfillment
- **External**: CRM, e-commerce frontend, partner order gateways
- **Pattern**: Saga for multi-step orchestration; event-driven for order status propagation; sync for validation/eligibility checks

## Anti-Corruption Layers

- Product catalog integration: adapter translating catalog offer model to order-internal product representation
- Legacy order systems: strangler fig with order routing (new vs legacy path based on product type)
- Partner order gateways: facade normalizing partner-specific order formats
