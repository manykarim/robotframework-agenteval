## Why

Testing an MCP server, Skill, or SubAgent end-to-end today means installing a vendor coding-agent CLI (claude-code, codex, …) and authenticating it — a real barrier for CI and for anyone who just has an API key. The `GenericAdapter` (litellm one-shot) is the only key-only path, but it does not run an agent loop, so it records only *requested* tool calls and cannot activate a skill or route to a subagent.

Research + a live spike show a lighter path. A **live run against MiniMax-M2.7** proved an in-process agent loop (just an LLM key + `base_url`, zero new deps) executes MCP tools and captures them into an `AgentRunResult`. Deep research into **pydantic-ai v2 + `pydantic-ai-harness`** then showed it goes further: with only a key + `base_url` it can drive **and observe** all four surfaces in-process — MCP tool calls, real **skill activation** (`load_capability` + `ctx.loaded_capability_ids`), **subagent routing** (harness `delegate_task`, loading Claude-style subagent `.md`), and PreToolUse-style **hook decisions** (tool-approval) — all programmatically from the run result, no log scraping.

This change adds an **in-process agent adapter** so users can measure their agentic artifacts with just an LLM, without any coding-agent CLI. It is a *proxy* for a competent generic agent — it answers "is my skill/subagent/MCP server well-designed and discoverable?" — and complements (does not replace) the vendor CLI adapters, which remain the way to measure how a *specific* coding agent behaves.

## What Changes

- **New `in-process` adapter** on the existing `Adapter` seam, backed by **pydantic-ai v2 + pydantic-ai-harness** behind a new optional **`[agent]`** extra. It runs a prompt through an in-process agent loop against any OpenAI-compatible endpoint (`OpenAIProvider(base_url, api_key)`; `AGENTEVAL_MODEL`), and normalizes the run into `AgentRunResult` (executed tool calls with results, token usage) that MetricsLibrary reads unchanged.
- **MCP measurement**: connect the adapter to an MCP server; executed tool calls are captured from the run's message history (`ToolCallPart`/`ToolReturnPart`) — monkeypatch-free, populating `ToolCallTrace.result`/`error`/`latency_ms` (which `GenericAdapter` leaves empty).
- **Skill-activation measurement**: load a Claude `SKILL.md` as a deferred pydantic-ai `Capability` (a `name→id` shim), run a prompt, and report **which skill(s) the model actually activated** via `ctx.loaded_capability_ids` + the `load_capability` call — a deterministic activation signal, not a Tier-2 judge guess.
- **SubAgent-routing measurement**: load Claude-style subagent `.md` into the harness `Subagents` capability (folder/`tool_resolver` shim), run a prompt, and report which named subagent the model routed to (`delegate_task` tool-call args) and how many delegations occurred.
- **Hook-decision measurement (partial)**: use pydantic-ai tool-approval (`requires_approval` → `ApprovalRequired`/`ToolApproved`/`ToolDenied`) to measure PreToolUse-style allow/deny decisions in-process; harness `Guardrails` for input/output gates. Clearly bounded — it is not an external-command hook runtime.
- **Honesty**: the adapter carries a `validation_ceiling` marker and labels every result as a *proxy* (pydantic-ai's mechanism, not Claude Code's runtime). `allowed-tools`/`disable-model-invocation` are not enforced (pydantic-ai does not honor them) — surfaced, not hidden.
- **Docs**: a README/real-model section on the in-process adapter (install `[agent]`, set model + key/base_url) and an end-to-end recipe measuring skill activation + subagent routing with no CLI.

## Capabilities

### New Capabilities
- `in-process-agent-adapter`: An in-process agent-loop adapter (pydantic-ai + harness, behind the `[agent]` extra) that runs a prompt with only an LLM key + base_url and measures — programmatically and in-process — MCP tool execution, real skill activation, subagent routing, and PreToolUse-style hook decisions, normalized into `AgentRunResult` for MetricsLibrary. Explicitly a faithful *proxy* for a generic agent, not a specific vendor's runtime.

### Modified Capabilities
<!-- evaluation-core owns the Adapter seam; coding-agent-cli-adapters owns the subprocess adapters. This adds a new adapter capability alongside them rather than changing their requirements. -->

## Impact

- **New deps (optional)**: `pydantic-ai` (v2) + `pydantic-ai-harness` behind the `[agent]` extra; base install unchanged. No new *base* dependency — deterministic testing stays tiny.
- **Files**: a new `src/AgentEval/_core/agent_adapter.py` (or `cli_adapters`-style module) + registration as an `in-process`/`pydantic-ai` slug in `get_adapter`; small Claude→pydantic frontmatter/folder shims; README + real-model doc + a recipe; tests (offline with a stub model + a live smoke gated on creds).
- **No change** to `_core/types.py`, MetricsLibrary, or the CLI adapters — this is a third adapter on a structural Protocol.
- **Maturity risk**: pydantic-ai v2 "capabilities" is ~3–4 weeks old (PR #5230) and the harness is new — versions pinned, a doc mutability point verified against the installed wheel, and a live smoke as the empirical-truth check.
