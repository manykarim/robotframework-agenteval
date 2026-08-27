## ADDED Requirements

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
