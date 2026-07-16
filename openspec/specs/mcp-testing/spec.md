# mcp-testing Specification

## Purpose
Test MCP servers - deterministic tool-schema validation, server lifecycle and tool-call assertions, coverage metrics, and agent-mode tool-discoverability scoring. Shipped as `MCPLibrary`.

## Requirements

### Requirement: MCPLibrary validates tool schemas deterministically

`MCPLibrary` SHALL provide Tier-1 keywords to read a server's declared configuration, fetch a tool's input schema, and validate a tool schema against the MCP contract. Schema-level validation SHALL be possible without a live server session.

#### Scenario: Validate a tool schema

- **WHEN** a user calls `MCP.Validate Tool Schema` on a tool with a well-formed input schema
- **THEN** the keyword passes; a malformed schema fails with a pointer to the offending field

### Requirement: MCPLibrary manages server lifecycle and invokes tools

`MCPLibrary` SHALL provide keywords to start or connect to an MCP server, list its tools, call a tool, and stop the server. `MCP.Call Tool` SHALL accept natural Robot Framework keyword arguments and a dict form; supplying both forms SHALL be a structured error. Live server keywords SHALL require the `[mcp]` extra.

#### Scenario: Call a tool with RF kwargs

- **WHEN** a user calls `MCP.Call Tool    search    query=robots`
- **THEN** the library invokes the `search` tool with `{"query": "robots"}` and returns the tool result

#### Scenario: Conflicting argument forms are rejected

- **WHEN** a user supplies both a dict argument and inline kwargs to `MCP.Call Tool`
- **THEN** the keyword raises a structured error explaining that only one form is allowed

#### Scenario: Live testing needs the mcp extra

- **WHEN** a user calls `MCP.Start Server` without the `[mcp]` extra installed
- **THEN** the keyword raises an error naming the `[mcp]` extra to install

### Requirement: MCPLibrary reports tool-call coverage metrics deterministically

`MCPLibrary` SHALL provide Tier-1 metrics over a recorded run — which tools were called, call counts, and hit/success/unnecessary-call rates — sourced from the shared trace projection.

#### Scenario: Assert a tool was exercised

- **WHEN** a test inspects coverage after exercising a server
- **THEN** it can assert deterministically that an expected tool was called and flag tools never called

### Requirement: MCPLibrary scores tool discoverability in agent mode

`MCPLibrary` SHALL provide a Tier-3 discoverability evaluation that drives a real coding agent against an MCP server for a set of tasks and scores whether the agent selects the right tools. Cross-adapter comparison (pairwise deltas, heatmaps) SHALL NOT be included in the base library.

#### Scenario: Single-adapter discoverability

- **WHEN** a user runs `MCP.Get Tool Discoverability` for a server over a task set with one adapter
- **THEN** the library returns a tool-selection score for that adapter
