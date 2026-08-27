## 1. Accept remote entries in Tier-1 config parsing (#16)

- [ ] 1.1 In `src/MCPLibrary/_config.py::_validate_entry`, replace the unconditional `command` gate (L137-143) with type-aware classification: read `entry.get("type")`; classify **remote** when `type in {"http","sse"}` OR (`url` present AND no `command`). Keep default/`stdio` on the existing `command`-required + non-empty-string checks (L137-151) verbatim.
- [ ] 1.2 Validate the accepted `type` set `{http, sse, stdio}`: an unrecognized `type` raises `InvalidConfigError` with `field="{entry_pointer}/type"` (distinct from the `transport`-enum error at L173-181); a `type`/`transport` inconsistency (e.g. `type: http` + `transport: stdio`) fails the same way.
- [ ] 1.3 For a remote entry, require a non-empty string `url` (raise, `field="{entry_pointer}/url"`); accept optional `headers` as `dict[str,str]` (raise, `field="{entry_pointer}/headers"`, if not a string-map) **without inspecting values** — `${VAR}` passes through unexpanded. A remote entry that also carries `command` is accepted with `command` ignored (documented).
- [ ] 1.4 Confirm `url`/`type`/`headers` survive the `dict(entry)` passthrough (L200) unchanged; keep `args`/`env`/`transport`/`tools` validation (L153-199) intact. No new dataclass.
- [ ] 1.5 Update the `MCP.Get Server Config` / `parse_mcp_servers` docstrings to document `type`/`url`/`headers`, the `type`-vs-`transport` distinction, and that `${VAR}` header placeholders are returned unexpanded.

## 2. Add HTTP + SSE session openers over the non-deprecated SDK clients (#17)

- [ ] 2.1 In `src/MCPLibrary/_transport.py`, add `open_http_session(*, url, headers=None)`: build `httpx.AsyncClient(headers=headers or None)`, enter `async with streamable_http_client(url, http_client=client) as (read, write, _get_session_id):`, open an uninitialized `ClientSession`, return `TransportSession(..., transport="streamable_http")`; close the stack on the failure path. **Use `streamable_http_client` (non-deprecated), NOT `streamablehttp_client`.**
- [ ] 2.2 Add `open_sse_session(*, url, headers=None)` over `async with sse_client(url, headers=headers) as (read, write):`, returning `TransportSession(..., transport="sse")`.
- [ ] 2.3 Extend the `Transport` alias to include `"sse"`; export both openers in `__all__`.
- [ ] 2.4 Add a pin-drift test asserting `streamable_http_client`'s signature (url + `http_client` kwarg, 3-tuple) so a future SDK bump fails a test, not a user run.

## 3. Wire transports into the lifecycle end-to-end (#17)

- [ ] 3.1 Add `url: str | None = None` and `headers: dict[str,str] | None = None` to `MCPServerHandle` (`_lifecycle.py:85`), and override `__repr__` to redact header values.
- [ ] 3.2 Add explicit `streamable_http` and `sse` branches to `start_server` (`_lifecycle.py:147-176`), each requiring `url` (replacing reliance on the `else`-reject at L165-168); apply the D1 `type`→`transport` mapping where a handle is built from a parsed entry's fields.
- [ ] 3.3 Add `streamable_http` → `open_http_session` and `sse` → `open_sse_session` branches to `_open_session` (L189-197). Do NOT introduce a separate `http` transport value — `streamable_http` is the canonical handle transport.
- [ ] 3.4 Replace the `streamable_http` rejection in `_validate_for_connect` (L181-182) with "remote (`streamable_http`/`sse`) transport requires `url` on the handle".
- [ ] 3.5 Extend `_is_connection_lost` (L255) to classify `StreamableHTTPError` and `httpx` connection errors so a dropped remote connection surfaces as `MCPError`.

## 4. Keyword surface + env-sourced header secrets (#16/#17)

- [ ] 4.1 Add `url=`/`headers=` params to the `MCP.Start Server` keyword (`library.py:133`) and thread them into `backend.start_server(...)`; update the docstring/example with a remote server.
- [ ] 4.2 Expand `${VAR}` placeholders in `headers` from `os.environ` **at connect time** inside `_lifecycle`, passing the resolved dict only to the transport's `httpx.AsyncClient`; a missing env var fails loud naming the variable (never its value). The resolved value is never returned, stored resolved, or logged.
- [ ] 4.3 (Design recommendation, optional) warn when an auth-named header (`Authorization`, `*-Api-Key`, `*-Token`, `Cookie`) carries a literal (non-`${VAR}`) value in `.mcp.json`.

## 5. Tests

- [ ] 5.1 `tests/surfaces/mcp/test_config.py`: (a) `type: http` entry with `url`+`headers`, no `command`, parses and round-trips `type`/`url`/`headers`; (b) `type: sse` parses; (c) http missing `url` → `field="/mcpServers/<name>/url"`; (d) unknown `type` (e.g. `websocket`) → `field=".../type"`; (e) `headers` with a `${VAR}` value returned **unexpanded**; (f) regression: `{transport: stdio}` with no `command` still errors on `command`.
- [ ] 5.2 Transport/lifecycle tests mirroring the stdio session-mock pattern: `open_http_session`/`open_sse_session` return an uninitialized session; `Connect To Server` + `List Tools`/`Call Tool` drive a mocked http/sse session; `streamable_http` is no longer rejected.
- [ ] 5.3 **Secret-leak tests:** a `${VAR}`-sourced auth header's resolved value is absent from the RF log capture, the `MCPServerHandle` repr, and every keyword return; a missing env var fails at connect naming the variable, not its value.
- [ ] 5.4 (Optional, env/binary-gated) live smoke against a reachable remote MCP endpoint if CI creds provide one; skips cleanly otherwise.

## 6. Docs + close out

- [ ] 6.1 Add a remote-server example to the MCP recipe / README (`type: http` `.mcp.json` with a `${VAR}` auth header + `MCP.Start Server ... url= headers=`); note the additive capability in `CHANGELOG.md`.
- [ ] 6.2 Full local gate (ruff / ruff format / mypy / license / contract-sections / doc-count / doc-render / keyword-examples / pytest / robot).
- [ ] 6.3 `openspec validate add-mcp-remote-support --strict`; archive after implementation lands + gates green.
