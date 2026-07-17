## Why

`robotframework-agenteval` can test the four surfaces deterministically and (in principle) drive a coding agent, but it cannot yet produce **real-world usage numbers** from real agent runs. Two concrete gaps make that impossible today:

1. The only agent adapter (`GenericAdapter`, LiteLLM) does a one-shot chat and **hard-codes `tool_calls=[]`** (`_core/adapter.py:163`) — so a real-model run records *zero* tool calls, and `cached_input_tokens` is never populated. Nothing downstream (coverage, metrics) works over an agent run.
2. There are **no keywords** exposing the metrics the data model already carries (`Usage` tokens, `cost_usd`, `latency_seconds`, `ToolCallTrace`), no per-tool token/cost attribution, no CLI coding-agent adapters, and `stats` (`run_n`/`pass_at_k`/`wilson`) is not even a Library — its own docstring example (`Stat.Run N Times`) references a keyword that does not exist and cannot run.

Research into the rf-mcp end-to-end harness (declarative expected-tool contracts + one normalized result schema + ground-truth tool-call capture, emitted identically by an in-process loop and a CLI subprocess) and into the coding-agent CLIs and eval frameworks (DeepEval, RAGAS, promptfoo, Inspect AI) shows a lean path: **expose the metrics that already exist, fix the adapter, and add a single thin CLI-agent seam** so scenarios can run through real coding agents and gather tool-call + token + cost + pass/fail numbers.

## What Changes

- **P0 — fix `GenericAdapter`**: parse `response.choices[0].message.tool_calls` into `ToolCallTrace` records and populate `cached_input_tokens`, so any real-model run captures its tool calls + full token usage (record whether cost is native or LiteLLM-derived).
- **Agent-run metric keywords** (Tier-1, deterministic — thin readers over existing `AgentRunResult` fields): `Get Token Usage`, `Get Cost USD`, `Get Latency Seconds`, `Get Tool Call Metrics` (per-task **and** per-tool rollup: count, passed [`error is None`], failed, tokens, cost, latency), and budget assertions `Tokens Used Should Be Below` / `Cost Should Be Below`.
- **Per-tool attribution**: add `input_tokens` / `output_tokens` / `cost_usd` to `ToolCallTrace` (a home for per-tool numbers), populated by adapters that can supply them.
- **A real `StatLibrary`** surfacing `Stat.Run N Times` / `Stat.Get Pass At K` / `Stat.Wilson Interval` over the existing `stats.py` — fixing the phantom-keyword example.
- **Normalized run-metrics record + JSON export** (rf-mcp `ScenarioResult` shape): declarative expected-tool contract (`{tool, min_calls, max_calls, required_args}`) with a hit-rate, and a keyword to write the per-run metrics to JSON for real-world-number collection.
- **Coding-agent CLI adapters**: a `SubprocessCLIAdapter` base (`build_argv` → subprocess with timeout + env-sourced secrets → `parse_output`), with adapters for **claude-code, gemini, codex, opencode** (FULL/PARTIAL tool-call + token fidelity) and best-effort **kilo, copilot** (DEGRADED, session-file fallback), each carrying a **VALIDATION-CEILING** honesty marker + a `--version` probe wired to `AdapterVersionDriftWarning` and a live E2E smoke.
- **Keyword-example coverage**: add runnable examples to the four `SkillsLibrary` keywords that lack them (`Get Description`, `Get Allowed Tools`, `Get Disable Model Invocation`, `Get Activation Decision`) and a gate that runs every doc example.
- **Docs**: a README CLI-agent setup section (install/configure each CLI, adapter slug, where keys go) and an end-to-end metrics recipe, in the Robot Framework voice.

Trajectory (order/argument) matching, Tool-Call F1, and a trajectory-aware Task-Completion judge are **noted as future (P3)**, out of this change.

## Capabilities

### New Capabilities
- `agent-run-metrics`: Deterministic keywords + result-object fields exposing per-run and per-tool metrics — tool-call counts, passed/failed tool calls, token usage (per task and per tool), cost, latency, and pass@k/Wilson via a `StatLibrary` — plus a declarative expected-tool contract with hit-rate and a JSON metrics export. Includes the P0 `GenericAdapter` tool-call + token fix.
- `coding-agent-cli-adapters`: A lean `SubprocessCLIAdapter` seam and per-agent adapters (claude-code, gemini, codex, opencode FULL/PARTIAL; kilo, copilot DEGRADED) that run a prompt end-to-end through a real coding-agent CLI and normalize its tool calls + token/cost usage into `AgentRunResult`, with version-drift detection and per-adapter VALIDATION-CEILING markers.
- `keyword-example-coverage`: Every shipped keyword's documentation carries a runnable usage example, enforced by a gate that executes every doc example.
- `llm-agent-setup-docs`: README + real-model docs explain LLM and coding-agent-CLI setup so users can configure a live run easily, plus an end-to-end metrics recipe — all examples runnable.

### Modified Capabilities
<!-- evaluation-core owns the adapter/tier design and mcp-testing owns the MCP coverage keywords; this change adds new metric/adapter/doc capabilities rather than restating their requirements. The GenericAdapter fix is an implementation correction captured under agent-run-metrics. -->

## Impact

- **Files**: `src/AgentEval/_core/{adapter.py,types.py,stats.py}` (adapter fix, ToolCallTrace fields), a new metrics keyword surface + `StatLibrary`, new `src/AgentEval/_core/cli_adapter.py` + per-agent adapters, `SkillsLibrary` docstrings, a new example-smoke + doc-example gate, `README.md` + `docs/running-against-a-real-model.md` + a new recipe.
- **Dependencies**: no new base deps; CLI adapters shell out to externally-installed agent binaries (documented, not packaged). Live metrics still ride the `[llm]` extra for the LiteLLM path.
- **Behavior**: additive — existing keywords unchanged; the `GenericAdapter` fix makes previously-empty `tool_calls` populated (a correctness improvement).
- **Honesty**: DEGRADED adapters and any derived (non-native) cost/token numbers are marked so real-world numbers are never overstated.
