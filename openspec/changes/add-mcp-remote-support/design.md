## Context

Two companion issues (#16 config-parse, #17 live-transport) reported that a remote
MCP server — `type: "http"`/`"sse"` + `url` + auth `headers`, no local binary — is
untestable via `MCPLibrary`. Root causes confirmed against source:

- `_config.py::_validate_entry` (L135-200) unconditionally requires `command`
  (L137-143) before examining any other field, then returns `dict(entry)` as a raw
  passthrough (L200). There is **no** `ServerConfig` dataclass — unknown keys
  (`type`, `url`, `headers`) already survive the round-trip untouched; the only
  blocker is the L137 gate. There is no secret/`${VAR}` handling anywhere in
  `_config.py`.
- `_transport.py` ships `open_stdio_session` (L59) and `open_in_memory_session`
  (L85); the `Transport` alias (L43) lists `streamable_http` but nothing constructs
  it. `_lifecycle.py::_validate_for_connect` (L179-186) rejects `streamable_http`
  (L181-182); `_open_session` (L189-197) has no http/sse branch; `start_server`'s
  `else` branch (L165-168) rejects any unknown transport.
- **`MCP.Start Server` never spawns anything** — `start_server` (L147-176) only builds
  an `MCPServerHandle`. The subprocess spawn is inside `stdio_client` in
  `open_stdio_session`, invoked lazily by the warm-session actor (`_actor`, L393-413)
  on connect/first-op. So the entire lifecycle — `WarmSession`, timeouts, `atexit`
  teardown, `_is_connection_lost`, and the cold one-shot fallback — is already
  transport-agnostic; a remote transport is a new opener + dispatch, not a new
  lifecycle.

## Goals / Non-Goals

**Goals:**

- Tier-1 parsing accepts remote `http`/`sse` entries (no `command`).
- Live keywords connect over Streamable HTTP and SSE, reusing the existing lifecycle.
- Auth-header secrets are env-sourced at connect, never logged/returned/stored-resolved.
- No new runtime dependency; use the SDK's non-deprecated client entry points.

**Non-Goals:**

- OAuth / dynamic-client-registration / interactive auth — only static header auth via
  `${VAR}` placeholders.
- A config→handle auto-bridge (D3) or a new `Start Server From Config` keyword.
- `MCP.Get Tool Discoverability` — not a live-session keyword (see D5), not made remote.
- Unifying the entry `type` field and the library `transport` enum.

## Decisions

### D1 — Remote-entry parsing + one exact type→transport mapping (#16)

`_validate_entry` classifies an entry as **remote** when `entry["type"] in {"http",
"sse"}` (primary, Claude Code's documented shape) or when a `url` is present with no
`command` (lenient fallback). The accepted `type` set is exactly `{http, sse, stdio}`;
any other `type` value raises `InvalidConfigError` with `field=".../type"` (distinct
from the existing `transport`-enum error at L173-181). For a remote entry: require a
non-empty string `url` (else raise, `field=".../url"`); do not require `command`;
accept optional `headers` as a `dict[str, str]` (raise, `field=".../headers"`, if not
a string-map) without inspecting values. A default/`stdio` entry keeps the current
`command`-required + non-empty-string checks (L137-151) verbatim, so
`test_get_server_config_missing_command_points_at_field` stays green.

The `.mcp.json` entry `type` and the library `transport` enum stay **independent
fields**, joined by one total mapping applied where a handle is built:
`type: http → transport: streamable_http`, `type: sse → transport: sse`,
`type: stdio`/absent-local `→ transport: stdio`. **Ambiguity resolutions (closing
OQ1/OQ2):** a remote entry that also carries `command` is treated as remote and the
`command` is ignored (documented); an unrecognized `type` fails as above; a stray
`transport: stdio` on a `type: http` entry is a config error surfaced by the same
`type`/`transport` validation (the two fields must be consistent).

### D2 — Session openers use the SDK's non-deprecated entry points (#17)

In the pinned `mcp==1.27.1`, `streamablehttp_client` (no underscore) is
`@deprecated("Use streamable_http_client instead.")`, and its `headers`/`timeout`/
`auth` kwargs are themselves deprecated ("Configure these on the httpx.AsyncClient").
So:

- `open_http_session(*, url, headers=None)` builds `httpx.AsyncClient(headers=resolved
  or None)` and enters `async with streamable_http_client(url, http_client=client) as
  (read_stream, write_stream, _get_session_id):` — a **3-tuple** async context manager
  (stdio yields a 2-tuple; discard the session-id callback). Returns
  `TransportSession(session, stack, transport="streamable_http")`. Routing headers
  onto the httpx client (rather than an SDK kwarg) also keeps them off the SDK's
  logging path.
- `open_sse_session(*, url, headers=None)` enters `async with sse_client(url,
  headers=resolved) as (read_stream, write_stream):` (SSE client, 2-tuple). Returns
  `transport="sse"`. `Transport` gains `"sse"`.

Both leave the session uninitialized (the caller runs `initialize()`), matching the
stdio opener, and close their `AsyncExitStack` on the failure path. A pin-drift test
asserts the `streamable_http_client` signature so a future SDK bump fails a test, not
a user run.

### D3 — Direct keyword args are the honest path; no auto-bridge

There is no config→handle bridge in the codebase: `MCPServerHandle(` is constructed
exactly once, inside `start_server` (`_lifecycle.py:169`); parsed config is a plain
mapping the user reads via `MCP.Get Server Config`. So the honest path is: `MCP.Start
Server` gains `url=`/`headers=` args and builds a remote handle directly. This change
does **not** add a `Start Server From Config`/auto-selection path (net-new API beyond
the two issues) — a user maps a parsed entry's `url`/`headers` onto `Start Server`
themselves, and the type→transport mapping (D1) is applied inside `start_server`. A
convenience bridge is a clean follow-up.

### D4 — Auth headers are opaque secrets, env-sourced at connect, never logged

Header values are treated as potentially-secret and opaque throughout:

- **Parse time:** `MCP.Get Server Config` returns `headers` with `${VAR}` placeholders
  **unexpanded** — no resolution, so a token never reaches `log.html` via the Tier-1
  reader.
- **Connect time:** the library expands `${VAR}` from `os.environ` inside `_lifecycle`
  and passes the resolved dict only to the transport's `httpx.AsyncClient`; a missing
  env var fails loud with the variable name (not its value). The resolved value is
  never returned to RF, never stored resolved on the frozen handle, and never logged.
- **Repr/logging:** `MCPServerHandle` overrides `__repr__` to redact header values
  (`headers={'Authorization': '***'}`), and connection errors are raised without the
  header contents, so no exception/traceback carries a token.

A design recommendation (not a hard gate): warn when an auth-named header
(`Authorization`, `*-Api-Key`, `*-Token`, `Cookie`) carries a literal (non-`${VAR}`)
value in `.mcp.json`, since a literal secret in a config file is itself a smell. The
hard guarantee is redaction + connect-time expansion, which needs no header-name
classification.

### D5 — Discoverability is not a live-session keyword (removed from scope)

`MCP.Get Tool Discoverability` (`library.py:423-450`) deliberately discards its
`mcp_server` string arg (`L450: _ = mcp_server`) and `run_discoverability`
(`_discoverability.py:247-275`) constructs an agent adapter and calls
`adapter.run(task.prompt)` — it never lists, injects, or calls tools from an MCP
handle. HTTP/SSE openers therefore cannot make a "remote discoverability" scenario
true, so discoverability is removed from the affected-keyword list and the transport
SHALL text. Making discoverability actually drive a (remote or local) MCP server is a
separate, larger design change, out of scope here.

### D6 — Warm session over HTTP: prefer the cold path

The cold one-shot path (`list_tools`/`call_tool` without a prior `Connect To Server`)
opens-inits-tears-down per op and is the safer default for a remote server (a warm
HTTP session could idle past the SDK's `sse_read_timeout`). The warm path stays
supported; `_is_connection_lost` is extended to classify `StreamableHTTPError` and
`httpx` connection errors so a dropped remote connection surfaces as a clean `MCPError`.

## Risks / Trade-offs

- **Backward-compat (config):** default/`stdio` entries keep the exact `command`
  checks + error pointers; the missing-command test is the regression guard.
- **Secret leakage** (D4). Mitigation: redact + connect-time-expand + tests over the
  RF log, handle repr, returns, and missing-var failure — not a happy-path log check.
- **SDK deprecation** (D2). Mitigation: use `streamable_http_client` now + a pin-drift
  signature test; SSE is a thin second opener with a docstring noting the legacy target.
- **`type` vs `transport` confusion.** Mitigation: independent fields + one total
  mapping (D1), documented in the `Get Server Config` / `Start Server` docstrings.

## Migration Plan

Purely additive. Existing stdio/in_memory configs, sessions, error pointers, and
keyword signatures are unchanged (new keyword args default to `None`;
`parse_mcp_servers` still returns `dict[str, dict[str, Any]]`). No new dependency.
Rollback is a revert. #16's parser change can ship first — independently useful, tests
independent of the transport code.

## Open Questions

- **OQ-A:** Should the literal-auth-header **warning** (D4 recommendation) be a hard
  rejection instead? Leaning warning, to stay lenient on genuinely-non-secret headers.
- **OQ-B:** Is `sse_client(url, headers=…)` itself deprecated in a later SDK line (as
  the streamable one is)? Not in 1.27.1; the pin-drift test covers it.
