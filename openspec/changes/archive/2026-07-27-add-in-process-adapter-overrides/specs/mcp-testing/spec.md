## ADDED Requirements

### Requirement: MCPLibrary captures and exposes a server's instructions

When connecting to a live MCP server, `MCPLibrary` SHALL capture the top-level
`instructions` field of the server's `InitializeResult` into the returned session
metadata, alongside the negotiated protocol version and server info. The captured
value SHALL be a string when the server provides one and `None` when it does not
(a non-string value SHALL be treated as `None`). The session metadata SHALL expose
it as a readable attribute (`${session.instructions}`), and `MCPLibrary` SHALL
provide a Tier-1 reader keyword `MCP.Get Server Instructions` that returns it for a
given session. Capturing instructions SHALL require the `[mcp]` extra (it happens
during a live connect) and SHALL be additive — existing session fields and
keywords are unchanged.

This makes a server's own workflow guidance available both for Tier-1 config-drift
checks (asserting a server ships the expected instructions) and for injection into
the in-process agent adapter (`get_adapter("in-process", instructions=${session.instructions})`).

#### Scenario: A server's instructions are captured on connect

- **WHEN** a user connects to an MCP server that advertises `instructions` and then
  reads `${session.instructions}` (or calls `MCP.Get Server Instructions`)
- **THEN** the advertised instruction string is returned

#### Scenario: A server without instructions reports None

- **WHEN** a user connects to an MCP server that advertises no `instructions`
- **THEN** the captured value is `None` rather than an error or an empty-object placeholder
