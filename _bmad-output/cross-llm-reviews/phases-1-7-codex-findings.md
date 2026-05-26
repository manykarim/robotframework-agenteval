# Phases 1-7 Codex Retro Review Findings

## HIGH

- `src/AgentEval/mcp/library.py:296` — `Connect To Server`'s example dereferences `MCPSession.server_info` as `${session.server_info.name}`, but `MCPSession.server_info` is a `dict[str, Any]` in `src/AgentEval/mcp/lifecycle.py`. This is the same hidden-attribute-error class as the Phase 7 `${result.text_content}` bug. Concrete fix: change the example to `${session.server_info}[name]`, or return a typed object instead of a dict.

- `src/AgentEval/mcp/library.py:494-498` — `Get Tool Discoverability`'s example is semantically wrong in two ways. First, it passes `provider=mock`, but `MockProvider` returns `tool_calls=[]`, zero usage, and zero cost, so it cannot demonstrate successful tool discoverability. Second, it asserts `${result.summary.activation_accuracy}`, but `DiscoverabilitySummary` only defines `overall_pass_rate`, `total_cost_usd`, and `total_runtime_seconds` in `src/AgentEval/discoverability/schema.py`. Concrete fix: switch the example to a real/scripted adapter and assert `${result.summary.overall_pass_rate}`, or keep `provider=mock` and rewrite it as a zero-discoverability example that matches mock semantics.

- `src/AgentEval/telemetry/library.py:85` — `Get Last Warnings` returns `list[dict[str, Any]]` via `warning_record_to_dict()` in `src/AgentEval/_kernel/warnings.py`, but the example logs `${w.timestamp}`, `${w.warning_type}`, and `${w.message}` as if each warning were an object. That will fail at runtime. Concrete fix: change the example to `${w}[timestamp]`, `${w}[warning_type]`, and `${w}[message]`.

- `src/AgentEval/orchestration/library.py:348-350` — `Load Scenario`'s example asserts `${scenario.name}` and `${scenario.tags}`, but the `Scenario` dataclass in `src/AgentEval/scenarios/schema.py` only has `evals`, `model`, `provider`, `agent`, and `mcp_servers`. Copying this example will raise attribute errors unrelated to the keyword. Concrete fix: assert real fields from the current schema, such as `${scenario.agent}`, `${scenario.model}`, `${scenario.mcp_servers}`, or properties of `${scenario.evals}`.

- `src/AgentEval/_assertions/library.py:114-118` and `src/AgentEval/_assertions/library.py:188-191` — both tool-call assertion examples are tagged "assumes a real adapter" but still call `Send Prompt ... provider=mock`. Mock-provider runs have `tool_calls=[]`, so these examples can never satisfy `Trajectory Should Match` or `Tool Call Should Have Occurred`. Concrete fix: remove `provider=mock` and point the examples at a real/scripted adapter, or replace them with response-text assertions that match mock echo behavior.

- `src/AgentEval/metrics/library.py:106-108`, `147-150`, `198-200`, `240-242`, `291-293`, `338-342` — the metrics docstrings repeat the same mock-provider contradiction. `MockProvider` returns no tool calls and `Usage(input_tokens=0, output_tokens=0)`, but these examples assert `count == 3`, names containing `web_search`, hit/success rates above zero, non-empty observed-call behavior, and token counts `> 0`. Dry-run won't catch this, but the examples are semantically false. Concrete fix: either switch these examples to a real/scripted adapter, or rewrite mock-only examples to assert the documented mock surface (`tool_calls=[]`, zero usage, zero cost).

## MED

- No confirmed MED findings.

## LOW

- No confirmed LOW findings.
