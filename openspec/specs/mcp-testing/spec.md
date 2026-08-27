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

### Requirement: MCPLibrary parses remote HTTP and SSE server entries

`MCPLibrary` SHALL accept remote MCP server entries in Tier-1 `.mcp.json` parsing.
An entry declared as a remote server — `type` of `http` or `sse` (or, leniently, an
entry that carries a `url` and no `command`) — SHALL parse successfully **without** a
`command` field, and SHALL instead require a non-empty `url`. A default or `stdio`
entry SHALL keep requiring `command` exactly as before. The accepted `type` set SHALL
be `{http, sse, stdio}`; an unrecognized `type` SHALL fail loud with an
`InvalidConfigError` whose field pointer names the `type` key. Optional `headers`
SHALL be accepted as a string-to-string map; the parser SHALL pass header values
through **unexpanded** and SHALL NOT resolve, log, or reject `${VAR}` placeholders
(the documented convention for auth headers). A missing/empty `url` on a remote entry
and a non-string-map `headers` SHALL each fail loud with a field pointer naming the
offending key. This requirement governs only static config parsing; it does not open
a live session.

#### Scenario: A remote http entry parses without command

- **WHEN** a user calls `MCP.Get Server Config` on a `.mcp.json` whose server entry
  declares `type: http` and a `url` (and optional `headers`) with no `command`
- **THEN** the entry parses successfully and the returned config preserves its
  `type`, `url`, and `headers`

#### Scenario: An sse entry parses without command

- **WHEN** a user parses a server entry declaring `type: sse` with a `url`
- **THEN** the entry parses successfully without requiring `command`

#### Scenario: Header placeholders are returned unexpanded

- **WHEN** a remote entry's `headers` contains a `${VAR}` placeholder value (e.g.
  `Authorization: "Bearer ${API_KEY}"`)
- **THEN** the parsed config returns that header value with the `${VAR}` placeholder
  unexpanded, and the parser neither resolves it from the environment nor rejects it

#### Scenario: A remote entry missing a url fails with a pointer

- **WHEN** a user parses a `type: http` entry that omits `url`
- **THEN** the library raises `InvalidConfigError` whose field pointer names the
  entry's `url` key

#### Scenario: An unrecognized type fails with a pointer

- **WHEN** a user parses an entry whose `type` is outside `{http, sse, stdio}`
- **THEN** the library raises `InvalidConfigError` whose field pointer names the
  entry's `type` key

#### Scenario: A default stdio entry still requires command

- **WHEN** a user parses an entry with no `type`/`url` (or an explicit `transport:
  stdio`) and no `command`
- **THEN** the library still raises `InvalidConfigError` pointing at the entry's
  `command` key, unchanged from prior behavior

### Requirement: MCPLibrary connects to remote MCP servers over HTTP and SSE transports

`MCPLibrary` SHALL open live sessions to a remote MCP server over the Streamable-HTTP
and SSE transports, in addition to the existing `stdio` and `in_memory` transports,
using only the MCP SDK already provided by the `[mcp]` extra (via the SDK's
non-deprecated client entry points; no new dependency). The live session keywords
(`MCP.Connect To Server`, `MCP.List Tools`, `MCP.Call Tool`, and
`MCP.Get Server Instructions`) SHALL work against such a server without a local
subprocess, reusing the existing session lifecycle. A remote transport SHALL require a
`url`. Auth `headers` MAY carry `${VAR}` placeholders that the library expands from the
environment **at connect time only**, passing the resolved values solely to the
transport's HTTP client. A resolved auth-header value SHALL NOT be returned to Robot
Framework, stored on the handle in resolved form, written to any log, or included in an
exception; the handle SHALL redact header values in its representation. A missing
environment variable referenced by a header placeholder SHALL fail loud naming the
variable, not its value. Streamable-HTTP SHALL no longer be rejected as unsupported.

#### Scenario: Connect to a Streamable-HTTP server and list its tools

- **WHEN** a user builds a handle with a `streamable_http` transport and a `url`,
  connects, and calls `MCP.List Tools`
- **THEN** the library opens an HTTP session, completes the MCP handshake, and returns
  the server's advertised tools without spawning a local process

#### Scenario: Connect to an SSE server

- **WHEN** a user builds a handle with an `sse` transport and a `url` and connects
- **THEN** the library opens an SSE session and returns handshake metadata

#### Scenario: A resolved auth header is never exposed

- **WHEN** a remote server is connected with a `headers` entry containing a `${VAR}`
  placeholder whose environment variable is set
- **THEN** the library sends the resolved header value only on the wire, and that
  resolved value does not appear in the Robot Framework log, the handle representation,
  any returned value, or any raised exception

#### Scenario: A missing header environment variable fails loud

- **WHEN** a user connects a remote handle whose header placeholder references an unset
  environment variable
- **THEN** the keyword fails naming the missing variable, without emitting its value

#### Scenario: A missing url on a remote transport fails loud

- **WHEN** a user attempts to connect a remote (`streamable_http`/`sse`) handle that
  has no `url`
- **THEN** the keyword raises a structured error stating that a remote transport
  requires a `url`

