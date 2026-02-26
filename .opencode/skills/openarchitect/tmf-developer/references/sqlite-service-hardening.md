# SQLite Service Hardening

Use this checklist after generating the TMF service scaffold.

## Security

1. Add authentication and authorization before exposing endpoints publicly.
2. Enforce allow-listed fields for create/patch operations per TMF resource.
3. Add request size limits and rate limiting.
4. Sanitize and validate callback URLs for `/hub` subscriptions.

## Data Integrity

1. Add schema-level validation for mandatory TMF attributes.
2. Add optimistic locking (`version` or `updatedAt` checks) for update operations.
3. Add migration tooling (`alembic`) once schema changes start.

## Reliability

1. Add structured logging and request IDs.
2. Add retries/timeouts when calling external dependencies.
3. Add health checks for both DB connectivity and service readiness.

## Performance

1. Index high-cardinality query fields used for filtering.
2. Cap pagination limits and add server-side defaults.
3. Move to PostgreSQL or MySQL for concurrent production workloads.

## Testing

1. Add CRUD integration tests for each generated TMF resource.
2. Add negative tests for missing IDs, invalid payloads, and duplicate IDs.
3. Add contract tests against expected TMF responses.

