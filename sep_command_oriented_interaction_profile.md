# SEP: Command-Oriented Interaction Profile for MCP

## Status

Draft

## Authors

Zhong (working draft with AI assistance)

## Abstract

This proposal defines an optional MCP interaction profile that allows clients and servers to negotiate a command-oriented interface in addition to the existing tool, resource, and prompt model.

The profile introduces a first-class command layer for environments where a flat tool catalog becomes difficult for language models to use effectively. It adds standardized methods for command discovery, command description, and command execution, while preserving backward compatibility with existing MCP servers and clients.

This proposal does not replace tools. It adds a higher-level interaction abstraction that can map to tools internally.

## Problem Statement

MCP standardizes connectivity well, but it primarily exposes server capabilities as tools, resources, and prompts. That works well when the server exposes a relatively small number of tools.

In larger environments, especially enterprise environments, clients may need to present dozens or hundreds of related capabilities to a language model. In those cases, flat tool catalogs create several problems:

- The model must reason over a large list of tool names and schemas.
- Discoverability becomes weaker because related capabilities are not presented as a coherent operational surface.
- Operational reasoning becomes fragmented across many tool descriptions instead of being expressed through a stable command language.
- Built-in MCP clients in major agent environments tend to inherit the same problem because the protocol does not currently provide a first-class command abstraction.

Human operators often interact with systems through command grammars rather than through large lists of unrelated function signatures. This proposal brings that shape into MCP as an optional profile.

## Goals

This profile is intended to:

- Provide a standardized command-oriented abstraction on top of MCP.
- Reduce cognitive overhead for language models when capability surfaces are large.
- Preserve backward compatibility with existing MCP clients and servers.
- Allow commands to be implemented natively or mapped to existing tools.
- Support discovery-before-execution, including syntax, examples, and safety metadata.

## Non-Goals

This proposal does not:

- Replace `tools/list` or `tools/call`.
- Provide arbitrary shell access.
- Change MCP transport, wire format, authorization model, or lifecycle semantics.
- Require hosts to expose commands directly to end users.
- Force any existing client to adopt command interaction.

## Terminology

For this proposal:

- A **command** is a structured operational action exposed through a command grammar.
- A **command profile** is the negotiated MCP capability that enables command discovery and execution.
- A **commandAst** object is a structured representation of a parsed command.
- A **qualified command name** is the unique server-defined identifier for a command.
- A **tool mapping** is a server-side implementation pattern where commands are routed internally to existing tools.

## Design Principles

### 1. Backward compatibility

Existing tool-based servers and clients continue to work unchanged.

### 2. Optional negotiation

Command interaction is enabled only when both client and server advertise support.

### 3. Command language, not shell access

Commands are an operational abstraction, not OS process execution.

### 4. Discovery before execution

Clients should be able to inspect available commands and their grammar before issuing them.

### 5. Commands may map to tools internally

A server may implement commands by routing them to existing MCP tools.

## Rationale

The current MCP model is excellent for interoperability. It standardizes connectivity, discovery, and invocation for tools and other server capabilities.

However, interoperability alone does not guarantee good client cognition.

When a capability surface becomes large, a model may perform better if it interacts through a command language that has:

- consistent grammar
- discoverable syntax
- grouped semantics
- examples
- explicit risk metadata

This proposal separates two concerns that are currently often collapsed together:

- The execution substrate, which can remain tool-based.
- The interaction abstraction, which can become command-based.

That separation lets tools continue to serve as the execution layer while giving clients a more coherent interface for LLM reasoning.

## Specification

### 1. Capability Negotiation

A client that supports this profile advertises support for a new optional capability:

```json
{
  "commands": {
    "extensions": ["status", "explain"]
  }
}
```

A server that supports this profile advertises the same capability in its initialization response.

The minimum valid shape is:

```json
{
  "commands": {}
}
```

If either side does not advertise `commands`, command methods are unavailable and normal MCP behavior continues unchanged.

The base profile defined here includes `commands/list`, `commands/describe`, and `commands/execute`.

Optional extensions are advertised through `commands.extensions`. This draft defines the extension names `status`, `explain`, and `complete`.

When both client and server advertise extensions, the effective extension set is the intersection of the two advertised lists. A server SHOULD advertise the full set of extensions it supports so clients can determine the intersection directly.

### 2. Command Identity and Grammar

This profile standardizes a canonical command identity and a canonical string syntax so that independently implemented clients and servers can interoperate predictably.

Every command MUST have:

- a `namespace`
- a `resource`
- an `action`
- a `qualifiedName`

Conceptually, a command is composed of a namespace-qualified resource, an action, named arguments, and optional boolean flags. In the metadata model used by this profile, flags are represented as arguments whose type is `boolean`.

The canonical qualified command name is:

```text
<namespace>/<resource> <action>
```

Examples:

- `crm/customer get`
- `billing/balance adjust`

The canonical string command syntax is:

```text
<namespace>/<resource> <action> [--<arg-name> <value>]... [--<flag>]...
```

Rules for the canonical syntax:

- `namespace`, `resource`, and `action` SHOULD use lowercase ASCII tokens with hyphens when needed.
- Argument names in string form MUST use long-form kebab-case, for example `--dry-run`.
- The canonical syntax defined by `commands/describe.syntax` MUST NOT require positional arguments.
- Servers MAY support aliases, shorthand, or richer syntaxes, but the advertised canonical syntax and examples MUST conform to this grammar.
- Clients SHOULD prefer the canonical syntax when generating string commands.

This choice keeps the grammar tight enough for interoperability while remaining conservative and easy for existing servers to implement.

### 3. New Methods

#### 3.1 `commands/list`

Returns a summary view of the command surface exposed by the server.

This method MUST support cursor-based pagination.

Request:

```json
{
  "cursor": null,
  "limit": 50,
  "namespace": "billing",
  "tags": ["mutation"],
  "query": "adjust account balance"
}
```

Request fields:

- `cursor`: optional pagination cursor
- `limit`: optional page size
- `namespace`: optional exact namespace filter
- `tags`: optional tag filter
- `query`: optional server-defined discovery query; servers MAY interpret this lexically, semantically, or both

Servers that do not support `query` filtering MUST ignore the field.

Response:

```json
{
  "commands": [
    {
      "qualifiedName": "crm/customer get",
      "namespace": "crm",
      "name": "customer get",
      "summary": "Fetch a customer by ID",
      "riskLevel": "read",
      "tags": ["customer", "lookup"]
    },
    {
      "qualifiedName": "billing/balance adjust",
      "namespace": "billing",
      "name": "balance adjust",
      "summary": "Adjust an account balance",
      "riskLevel": "write",
      "tags": ["billing", "mutation"]
    }
  ],
  "nextCursor": "page_2_token"
}
```

`commands/list` intentionally returns summary metadata only. Detailed syntax, arguments, execution semantics, and full safety metadata are returned by `commands/describe`.

#### 3.2 `commands/describe`

Returns detailed metadata for a specific command.

Request:

```json
{
  "qualifiedName": "billing/balance adjust"
}
```

Response:

```json
{
  "qualifiedName": "billing/balance adjust",
  "namespace": "billing",
  "name": "balance adjust",
  "resource": "balance",
  "action": "adjust",
  "summary": "Adjust an account balance",
  "syntax": "billing/balance adjust --account <id> --amount <number> [--dry-run]",
  "arguments": [
    {
      "name": "account",
      "cliName": "account",
      "type": "string",
      "required": true,
      "description": "Account identifier"
    },
    {
      "name": "amount",
      "cliName": "amount",
      "type": "number",
      "required": true,
      "description": "Adjustment amount"
    },
    {
      "name": "dryRun",
      "cliName": "dry-run",
      "type": "boolean",
      "required": false,
      "description": "Simulate the result without applying the change"
    }
  ],
  "riskLevel": "write",
  "reversible": false,
  "approvalRequired": true,
  "idempotent": false,
  "examples": [
    "billing/balance adjust --account 456 --amount 10 --dry-run"
  ],
  "supportsCommandAst": true,
  "supportsStringForm": true
}
```

The `name` field in `arguments` is the canonical JSON identifier used in `commandAst.args`. The `cliName` field is the canonical string-form flag name.

Clients SHOULD use `supportsCommandAst` and `supportsStringForm` to choose an execution form when both are not guaranteed. Because `commandAst` support is mandatory in the base profile, `supportsCommandAst` MUST be `true` for compliant servers.

#### 3.3 `commands/execute`

Executes a command.

Servers implementing this profile MUST support the structured `commandAst` form. Servers MAY additionally support a string `command` form as a convenience layer for human-authored or model-authored text commands.

Structured request form:

```json
{
  "commandAst": {
    "namespace": "billing",
    "resource": "balance",
    "action": "adjust",
    "args": {
      "account": "456",
      "amount": 10,
      "dryRun": true
    }
  }
}
```

Optional string request form:

```json
{
  "command": "billing/balance adjust --account 456 --amount 10 --dry-run"
}
```

Success response:

```json
{
  "status": "success",
  "commandAst": {
    "namespace": "billing",
    "resource": "balance",
    "action": "adjust",
    "args": {
      "account": "456",
      "amount": 10,
      "dryRun": true
    }
  },
  "command": "billing/balance adjust --account 456 --amount 10 --dry-run",
  "data": {
    "currentBalance": 15,
    "projectedBalance": 25
  },
  "message": "Dry run completed successfully",
  "retryable": false
}
```

Application error response:

```json
{
  "status": "error",
  "commandAst": {
    "namespace": "billing",
    "resource": "balance",
    "action": "adjust",
    "args": {
      "account": "456",
      "amount": "ten"
    }
  },
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "Argument 'amount' must be numeric"
  },
  "retryable": false
}
```

Pending response for long-running execution:

```json
{
  "status": "pending",
  "commandAst": {
    "namespace": "billing",
    "resource": "export",
    "action": "run",
    "args": {
      "account": "456"
    }
  },
  "operationId": "op_01JXYZ",
  "message": "Export queued",
  "retryable": false
}
```

#### 3.4 Optional `commands/status`

If the `status` extension is advertised, clients MAY poll for completion of a pending command.

Request:

```json
{
  "operationId": "op_01JXYZ"
}
```

Response:

```json
{
  "status": "pending",
  "operationId": "op_01JXYZ",
  "progress": {
    "phase": "exporting",
    "percent": 40
  },
  "retryable": false
}
```

The final response from `commands/status` uses the same result envelope as `commands/execute`. `success` and `error` are terminal states. `pending` is a non-terminal state.

Servers SHOULD retain terminal results for a reasonable implementation-defined period so that polling a completed `operationId` returns the terminal result envelope. If the server no longer recognizes the `operationId`, it SHOULD return a command-level error result with `status: "error"`.

#### 3.5 Optional `commands/explain`

Optional method for model-oriented explanation.

Request:

```json
{
  "qualifiedName": "billing/balance adjust"
}
```

Response:

```json
{
  "qualifiedName": "billing/balance adjust",
  "explanation": "Use this command to adjust an account balance. Prefer dry-run before execution for write operations."
}
```

#### 3.6 Optional `commands/complete`

Optional method for human-oriented completion and suggestion.

This method is not part of the base profile because it primarily serves interactive UIs rather than machine-driven discovery.

Request:

```json
{
  "partial": "billing/balance adj"
}
```

Response:

```json
{
  "completions": [
    "billing/balance adjust"
  ]
}
```

## Safety Metadata

Servers should expose safety-related metadata directly.

Required field:

- `riskLevel`: `read` | `simulate` | `write` | `admin`

Recommended fields:

- `reversible`: boolean
- `approvalRequired`: boolean
- `idempotent`: boolean

`riskLevel` MUST appear in both `commands/list` and `commands/describe`. The remaining safety fields SHOULD appear in `commands/describe`, and MAY appear in `commands/list` if a server wants to help clients make earlier policy decisions.

This allows clients and hosts to reason about whether a command should be previewed, simulated, approved, or blocked.

## Error Model

This profile distinguishes between protocol errors and command-level errors.

- Transport failures, malformed JSON-RPC requests, and unknown MCP methods MUST use normal JSON-RPC error responses.
- Command parsing failures, validation failures, authorization denials, approval denials, and business-state failures SHOULD be returned as successful JSON-RPC results whose body uses the normalized command result envelope with `status: "error"`.

This keeps the protocol/error boundary aligned with MCP and JSON-RPC while giving clients a stable application-level command response model.

## Result Envelope

Command execution results should follow a normalized envelope.

Recommended fields:

- `status`: `success` | `error` | `pending`
- `commandAst`
- `command` when string form was supplied or echoed back
- `data` on success
- `message`
- `retryable`
- `operationId` when `status` is `pending`
- `progress` when supported
- `error` when `status` is `error`

`retryable: true` means the same command MAY be retried without modification because the failure is considered transient by the server. Clients SHOULD NOT automatically retry mutating commands unless the server separately guarantees safe retry semantics.

This gives clients a stable structure regardless of the underlying implementation.

## Server Implementation Strategies

Servers may implement this profile in either of two ways.

### Native command handling

The server directly implements command discovery, parsing, validation, and execution.

### Command-to-tool mapping

The server exposes command methods externally, but internally maps them to existing tools.

Example:

Command:

```json
{
  "commandAst": {
    "namespace": "crm",
    "resource": "customer",
    "action": "get",
    "args": {
      "id": "123"
    }
  }
}
```

Internal tool mapping:

```json
{
  "tool": "execute_capability",
  "arguments": {
    "capability": "customer.get",
    "args": {
      "id": "123"
    }
  }
}
```

This implementation path allows existing tool-based servers to add command support incrementally.

## Client Behavior

A client supporting this profile may choose one of three interaction modes.

### Tool mode

Use existing tools only.

### Command-preferred mode

Use commands when available and fall back to tools otherwise.

### Hybrid mode

Use commands for large operational domains and tools for narrow or special-purpose capabilities.

This proposal does not mandate one client behavior. It standardizes the command surface so hosts can choose the experience they want.

## Backward Compatibility

Backward compatibility is preserved.

Servers that do not advertise `commands` continue to function unchanged.

Clients that do not support `commands` ignore the capability and continue using tools, resources, and prompts normally.

No existing MCP methods are removed or modified.

No transport or lifecycle changes are required.

## Security Considerations

This proposal must not be interpreted as arbitrary shell execution.

Commands are an interaction abstraction, not implicit OS access.

Servers must continue to enforce all authorization, validation, and policy checks.

If a command maps to underlying tools, the security boundary remains the server-side implementation and its policies.

Clients should not assume that all commands are safe simply because they are exposed through a command grammar. Safety metadata is advisory unless enforced by server policy.

Servers should reject ambiguous or malformed commands with structured errors.

For write or admin-level commands, servers should strongly consider approval flows, dry-run support, or both.

Long-running or batch operations should prefer `status: "pending"` over holding open an execution request indefinitely.

## Open Questions

The following questions remain open for discussion.

- Should the optional `query` field on `commands/list` eventually be standardized as lexical search, semantic search, or a hybrid contract?
- Should this profile eventually define notifications or streaming updates in addition to polling through `commands/status`?
- Should mutating commands gain a standardized idempotency token to support safe automated retry behavior?
- Should aliases or shorthand forms be discoverable in `commands/describe`, or remain entirely implementation-defined?

## Example End-to-End Flow

### Initialization

Client advertises support for:

```json
{
  "commands": {
    "extensions": ["status", "explain"]
  }
}
```

Server advertises the same capability.

### Discovery

Client calls:

```json
{
  "method": "commands/list",
  "params": {
    "namespace": "crm",
    "limit": 25,
    "query": "lookup customer"
  }
}
```

### Inspection

Client calls `commands/describe` for `crm/customer get`.

### Execution

Client calls:

```json
{
  "commandAst": {
    "namespace": "crm",
    "resource": "customer",
    "action": "get",
    "args": {
      "id": "123"
    }
  }
}
```

### Response

```json
{
  "status": "success",
  "commandAst": {
    "namespace": "crm",
    "resource": "customer",
    "action": "get",
    "args": {
      "id": "123"
    }
  },
  "data": {
    "id": "123",
    "name": "Alice"
  },
  "message": "Customer retrieved successfully",
  "retryable": false
}
```

## Reference Implementation Sketch

A minimal implementation can be added without changing the underlying execution substrate:

1. Add optional `commands` capability negotiation.
2. Define stable namespaces and canonical command names.
3. Implement paginated `commands/list` with summary metadata and optional filtering.
4. Implement `commands/describe` with canonical syntax, argument metadata, and safety metadata.
5. Implement `commands/execute` for `commandAst`, with optional support for string commands.
6. Internally map command execution to existing tools where appropriate.
7. Return normalized result envelopes, and add `commands/status` if long-running work must be supported.

This enables incremental adoption while preserving full compatibility with existing MCP tooling.

## Conclusion

MCP standardized connectivity between AI hosts and external capabilities.

The next scaling problem is not only connectivity. It is how clients present large operational capability surfaces to models without overwhelming them.

This proposal addresses that problem by adding an optional command-oriented interaction profile that remains compatible with existing MCP servers, tools, and clients.

Tools remain the execution substrate. Commands become an optional interaction profile.
