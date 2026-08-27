## 1. Accept remote entries in Tier-1 config parsing (#16)

- [x] 1.1 `_validate_entry` classifies remote (`type in {http,sse}` OR url-without-command); default/`stdio` keeps the `command`-required checks verbatim.
- [x] 1.2 Accepted `type` set `{http, sse, stdio}` validated (unknown → field `.../type`); a remote `type` with a local `transport` → field `.../transport`.
- [x] 1.3 Remote requires non-empty `url` (field `.../url`); optional `headers` validated as `dict[str,str]` without inspecting values (`${VAR}` passes through unexpanded).
- [x] 1.4 `url`/`type`/`headers` survive the `dict(entry)` passthrough; `args`/`env`/`transport`/`tools` validation intact. No new dataclass.
- [x] 1.5 `MCP.Get Server Config` / `parse_mcp_servers` docstrings document `type`/`url`/`headers`, the `type`-vs-`transport` distinction, and `${VAR}`-unexpanded returns.

## 2. Add HTTP + SSE session openers over the non-deprecated SDK clients (#17)

- [x] 2.1 `open_http_session` over `streamable_http_client(url, http_client=httpx.AsyncClient(headers=…))`; unpacks the 3-tuple; returns `TransportSession(transport="streamable_http")`. Uses the non-deprecated client.
- [x] 2.2 `open_sse_session` over `sse_client(url, headers=…)` (2-tuple); returns `TransportSession(transport="sse")`.
- [x] 2.3 `Transport` alias gains `"sse"`; both openers exported in `__all__`.
- [x] 2.4 Pin-drift covered implicitly by the smoke import; `streamable_http_client` signature confirmed against `mcp==1.27.1`.

## 3. Wire transports into the lifecycle end-to-end (#17)

- [x] 3.1 `MCPServerHandle` gains `url`/`headers` + a `__repr__` that redacts header values.
- [x] 3.2 `start_server` gains explicit `streamable_http`/`sse` branches, each requiring `url`.
- [x] 3.3 `_open_session` gains `streamable_http`/`sse` branches (resolving `${VAR}` headers at connect); no separate `http` transport value.
- [x] 3.4 `_validate_for_connect` requires `url` for a remote transport (replacing the reject).
- [x] 3.5 `_is_connection_lost` classifies `StreamableHTTPError` + `httpx.HTTPError`.

## 4. Keyword surface + env-sourced header secrets (#16/#17)

- [x] 4.1 `MCP.Start Server` gains `url=`/`headers=`, threaded into `backend.start_server(...)`; docstring + remote example.
- [x] 4.2 `_resolve_headers` expands `${VAR}` from `os.environ` at connect time; a missing var fails loud naming the variable (never its value); resolved values reach only the transport client.
- [ ] 4.3 (Deferred, optional) literal-auth-header warning — the hard guarantee (redaction + connect-time expansion) is implemented; the literal-value warning is left as a follow-up (design OQ-A).

## 5. Tests

- [x] 5.1 `test_config.py`: remote http (round-trips type/url/headers), sse, missing-url pointer, unknown-type pointer, `${VAR}` unexpanded, url-only-is-remote, stdio-still-requires-command regression.
- [x] 5.2 Lifecycle: `start_server` remote url-required; `_open_session` dispatches to `open_http_session` with resolved headers (stubbed); `streamable_http` no longer rejected (obsolete reject test replaced).
- [x] 5.3 Secret-leak: handle repr redacts header values (no `Bearer`/`${VAR}`); `_resolve_headers` expands from env and a missing var fails naming only the variable.
- [ ] 5.4 (Deferred) live env/binary-gated smoke against a reachable remote MCP endpoint — no such endpoint available in this environment; add when CI provides one.

## 6. Docs + close out

- [x] 6.1 Remote-server example in the `MCP.Start Server` docstring; `CHANGELOG.md` additive capability entry. (README recipe example deferred with the live smoke.)
- [x] 6.2 Full local gate (ruff / ruff format / mypy / license / contract-sections / doc-count / doc-render / keyword-examples / pytest). Robot dogfood is a separate live-LLM smoke.
- [x] 6.3 `openspec validate add-mcp-remote-support --strict`; archive after implementation lands + gates green.
