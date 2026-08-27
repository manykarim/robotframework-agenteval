## Why

`MCPLibrary` cannot be used at all against a **remote/hosted MCP server** — the
deployment shape Claude Code itself documents (`type: "http"` or `"sse"` with a
`url` and auth `headers`, no local binary). Both halves of the surface reject it:

- **Tier-1 config parsing (issue #16).** `MCPLibrary/_config.py::_validate_entry`
  opens (L137-143) with `if "command" not in entry: raise InvalidConfigError(...)`,
  which fires for **every** entry before any other field is examined. A remote
  entry with `type`/`url` and no `command` fails outright, so
  `MCP.Get Server Config` / `MCP.Get Tool Schema` / `MCP.Validate Tool Schema` are
  unusable against any `.mcp.json` that points at a remote server. (The
  `SUPPORTED_TRANSPORTS` constant at L42 is the enum for the entry's *optional
  `transport` field* — a different concept from Claude Code's entry `type`; it is
  not what gates this.)
- **Live keywords (issue #17).** `MCPLibrary/_transport.py` implements only
  `open_stdio_session` and `open_in_memory_session`; there is no HTTP/SSE opener.
  The `Transport` alias (L43) lists `streamable_http` but nothing constructs it, and
  `_lifecycle.py::_validate_for_connect` (L181-182) **explicitly rejects** it. So
  `MCP.Connect To Server` / `List Tools` / `Call Tool` / `Get Server Instructions`
  cannot reach a remote server either.

This undercuts the "test the agentic stack" pitch for the common enterprise case: an
internally-hosted MCP server behind bearer-token auth. Grouped as one capability
change because both are the same user-facing story (*test a remote MCP server*) and
share the `mcp-testing` capability. They stay independently shippable — #16's parser
change is useful on its own and its tests do not depend on the transport code.

## What Changes

- **Accept remote (`http`/`sse`) `.mcp.json` entries in Tier-1 parsing (#16).**
  `_validate_entry` becomes type-aware: an entry classified *remote* requires a
  non-empty `url` and does **not** require `command`; a default/`stdio` entry keeps
  the existing `command`-required behavior verbatim. Optional `headers` are accepted
  as a string-map and passed through with `${VAR}` placeholders **unexpanded** — the
  parser never resolves or returns a secret. The accepted `type` set is
  `{http, sse, stdio}`; an unrecognized `type` fails loud. `url`/`type`/`headers`
  flow through the existing raw-passthrough return (`dict(entry)`, L200); **no new
  dataclass**.
- **Add HTTP and SSE live transports (#17).** New `open_http_session(url, headers)`
  over the SDK's **`streamable_http_client`** (the non-deprecated entry point — see
  design D2) and `open_sse_session(url, headers)` over `mcp.client.sse.sse_client`,
  both returning the existing `TransportSession` shape. The handle `Transport` alias
  gains `"sse"`. Both clients are in the pinned `mcp==1.27.1` — **no new dependency**.
- **Wire the transports into the existing lifecycle end-to-end.** `MCPServerHandle`
  gains `url`/`headers`; `start_server` gains explicit `streamable_http` and `sse`
  branches (both require `url`); `_open_session` gains `streamable_http`/`sse`
  branches; `_validate_for_connect`'s rejection becomes a `url`-required check.
  The warm-session actor, timeouts, `atexit` teardown, and cold-path fallback are
  already transport-agnostic and are reused unchanged. `MCP.Start Server` gains
  `url=`/`headers=` args — the direct, honest path (there is no config→handle
  auto-bridge today, and this change does not add one; see design D3).
- **Never leak an auth header.** Header values are treated as opaque secrets:
  `${VAR}` placeholders are expanded from `os.environ` **only at connect time**, onto
  the transport's HTTP client, and the resolved value is never returned, never stored
  resolved on the handle, and never logged. `MCPServerHandle` redacts header values in
  its `repr`. `MCP.Get Server Config` returns headers with placeholders unexpanded.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `mcp-testing`: ADD a requirement that Tier-1 config parsing accepts remote
  (`http`/`sse`) server entries (`url` required, `command` not required, `headers`
  passed through unexpanded, unknown `type` fails). ADD a requirement that the live
  session keywords connect to a remote MCP server over the Streamable-HTTP and SSE
  transports, with auth headers env-sourced at connect time and never logged.

## Impact

- **Code:** `src/MCPLibrary/_config.py` (`_validate_entry` type-aware branching + a
  `type` validator); `src/MCPLibrary/_transport.py` (`open_http_session` over
  `streamable_http_client` + an `httpx.AsyncClient`, `open_sse_session`, `Transport`
  += `sse`); `src/MCPLibrary/_lifecycle.py` (`MCPServerHandle.url/headers` with
  redacted repr, `start_server` http/sse branches, `_open_session` http/sse branches,
  `_validate_for_connect` url check, connect-time `${VAR}` expansion,
  `_is_connection_lost` extended for `StreamableHTTPError`/`httpx` errors);
  `src/MCPLibrary/library.py` (`MCP.Start Server` `url=`/`headers=` args + docstrings).
- **Tests:** `tests/surfaces/mcp/test_config.py` — remote http/sse parse, missing-url
  pointer, unknown-`type` pointer, `${VAR}` passthrough-unexpanded, stdio-still-
  requires-command regression; transport tests mirroring the stdio session mock for
  http/sse open + connect + list/call; **secret-leak tests** (resolved header value
  absent from RF log, handle repr, and every return; missing-env-var fails at connect);
  a pin-drift/signature test around `streamable_http_client`.
- **Docs:** the MCP recipe / README remote-server example (`type: http` `.mcp.json`
  with a `${VAR}` auth header); `CHANGELOG.md` (additive capability).
- **Out of scope / deliberately not done:** `MCP.Get Tool Discoverability` — it does
  **not** open a live MCP session (`library.py:450` discards its `mcp_server` arg;
  `_discoverability.py` never lists/injects/calls tools from a handle), so it is not a
  remote-capable keyword and is not claimed as one. A config→handle convenience bridge
  (`Start Server From Config`) — net-new API, left as a clean follow-up. OAuth /
  dynamic client registration; non-MCP HTTP; unifying the entry `type` and the library
  `transport` enum (kept as independent fields, D3).
