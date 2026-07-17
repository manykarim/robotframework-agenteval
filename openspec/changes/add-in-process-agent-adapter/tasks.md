## 1. Foundation — the [agent] extra + adapter shell

- [x] 1.1 Branch off `main`. Add the `[agent]` extra to `pyproject.toml` with pinned `pydantic-ai` (v2) + `pydantic-ai-harness`; keep base + deterministic install unchanged.
- [x] 1.2 New `src/AgentEval/_core/agent_adapter.py`: an `InProcessAgentAdapter` on the `Adapter` seam, model + `base_url` + api_key via `OpenAIProvider` (and `AGENTEVAL_MODEL`); lazy pydantic-ai import with a loud `MissingExtraError` naming `[agent]`; a `validation_ceiling` string; run routed through `_core.run_async`.
- [x] 1.3 Register the `in-process` slug in `get_adapter`/`_ADAPTERS` (lazy, mirroring the CLI `SLUG_MAP` so importing doesn't pull pydantic-ai).
- [x] 1.4 Map pydantic-ai `result.output` / `result.usage()` / `result.all_messages()` → `AgentRunResult` (executed `ToolCallTrace` with result/error/latency; token usage; `metric_source`). Unit tests with a pydantic-ai stub/test model (no live call).

## 2. MCP surface

- [x] 2.1 Attach an MCP server as an `MCPToolset`; prefer accepting an already-connected `MCPServerHandle` so MCPLibrary + MetricsLibrary reuse it. Executed calls → `ToolCallTrace` from message-history `ToolCallPart`/`ToolReturnPart`. (Shape B: native `MCPServerStdio` is NOT importable in pydantic-ai 2.12; instead `MCP.As Agent Toolset` / `_agent_bridge.build_agent_toolset` lists the connected server's tools and wraps each as `Tool.from_schema` over a closure that runs the tool through `MCP.Call Tool` on the shared handle — one path feeds both pydantic-ai history and MCPLibrary's recorder. Bridge lives in MCPLibrary, not `_core`, honoring surface→`_core` dependency direction.)
- [x] 2.2 Live MiniMax smoke (gated on creds): run a prompt that should call a tool; assert `AgentRunResult.tool_calls` is populated with the executed call + result; MetricsLibrary reads it. (`tests/surfaces/mcp/test_agent_bridge.py::test_live_in_process_agent_drives_mcp_tool_through_the_handle`; live MiniMax-M2.7 run executed `echo_back(text='mcp-works')`→`'mcp-works'`, recorder + `Metric.Get Tool Call Metrics` both saw count=1/passed=1.)

## 3. Skills surface — real activation

- [ ] 3.1 `SKILL.md` → deferred `Capability` shim (reuse SkillsLibrary's frontmatter parser; `name→id`, body→instructions, `defer_loading=True`). Verify `loaded_capability_ids` mutability/read-only against the installed wheel before relying on it.
- [ ] 3.2 A reader that reports activated skill ids for a run (from `ctx.loaded_capability_ids` + the activation tool-call). Consider a thin Tier-1/Tier-3 keyword (e.g. `Skill.Get Activated Skills` over an `AgentRunResult`).
- [ ] 3.3 Live smoke: a matching prompt activates the skill; an unrelated prompt does not.

## 4. SubAgents surface — real routing

- [ ] 4.1 Load Claude-style subagent `.md` into the harness `Subagents` capability (point `agent_folders` at / copy from the Claude dir; a `tool_resolver` for the `tools` frontmatter names; tolerate extra Claude fields).
- [ ] 4.2 A reader that reports which named subagent(s) were routed to + delegation count (`delegate_task` `ToolCallPart.agent_name`). Confirm per-subagent observability empirically.
- [ ] 4.3 Live smoke: a task routes to the expected named subagent.

## 5. Hooks surface (Phase 2, PARTIAL)

- [ ] 5.1 PreToolUse-style tool-approval gate (`requires_approval` → `ApprovalRequired`/`ToolApproved`/`ToolDenied`); report allow/deny per guarded tool call. Optionally `Guardrails` for input/output gates.
- [ ] 5.2 Document + mark PARTIAL (in-process tool gate, not external command-script hooks) in the `validation_ceiling` + docs.

## 6. Docs

- [ ] 6.1 README + `docs/running-against-a-real-model.md`: the in-process adapter path (`pip install '...[agent]'`, model + base_url + key), the `in-process` slug, and the proxy-not-vendor-runtime framing; note `allowed-tools` is not enforced.
- [ ] 6.2 An end-to-end recipe under `docs/recipes/`: measure skill activation + subagent routing + MCP tool calls with NO coding-agent CLI, RF voice, runnable.

## 7. Verification + release

- [ ] 7.1 Full local gate green: ruff, format, mypy, license, contract-sections, doc-keyword-count, doc-rendering, keyword-examples, pytest, robot smoke.
- [ ] 7.2 Live MiniMax end-to-end: one run measuring executed MCP tool calls + real skill activation + subagent routing; record honestly which surfaces were live-verified. Confirm the proxy `validation_ceiling` holds.
- [ ] 7.3 PR → CI green → merge; consider a `0.3.0` minor bump (new adapter + extra).
- [ ] 7.4 `openspec validate` passes; archive so `in-process-agent-adapter` joins the baseline.
