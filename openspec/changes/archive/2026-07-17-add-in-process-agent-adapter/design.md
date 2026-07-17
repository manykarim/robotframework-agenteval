## Context

robotframework-agenteval v0.2.0 tests four surfaces on an `Adapter` seam (`run(prompt)->AgentRunResult`). It ships `GenericAdapter` (litellm one-shot — records only *requested* tool calls) and six subprocess CLI adapters (claude-code/…). End-to-end measurement therefore needs a vendor CLI. This change adds an in-process, key-only alternative.

**Evidence base.** A live spike (this repo, MiniMax-M2.7 via `OpenAIProvider(base_url, api_key)`) ran an in-process litellm tool loop against an in-memory MCP echo server: the model chose + executed `echo_back`, captured as `ToolCallTrace(name='echo_back', result='robots-are-fun')`, tokens 657/133, in ~130 lines with zero new deps. Deep research into pydantic-ai v2 + pydantic-ai-harness (four streams, docs fetched) then showed the same key-only, in-process footing extends to all four surfaces with *programmatic* observability (message-history parts, `RunContext` fields, typed exceptions) — no monkeypatching, no log scraping.

## Goals / Non-Goals

**Goals:**
- One in-process adapter that, with only an LLM key + base_url, drives and observes MCP tools, skill activation, subagent routing, and PreToolUse-style hook decisions — normalized into `AgentRunResult` for MetricsLibrary.
- Load Claude-style `SKILL.md` and subagent `.md` (via small shims) so users test their real artifacts.
- Honest proxy framing; a live smoke as the empirical-truth check.

**Non-Goals:**
- Replacing the vendor CLI adapters — those measure how a *specific* agent behaves; this measures how a *generic competent* agent treats the artifact.
- Enforcing `allowed-tools`/`disable-model-invocation` (pydantic-ai does not honor them).
- Claiming Claude-Code-runtime fidelity, or an external-command hook runtime.
- A standing OTel/Logfire backend (agenteval has its own trace + MetricsLibrary).

## Decisions

### D1 — Back it with pydantic-ai + harness, not a hand-rolled litellm loop
The litellm loop (zero deps) is proven for **MCP only**; Skills + SubAgents would require re-implementing progressive disclosure, a `load_capability` tool, and a subagent pool. pydantic-ai provides those first-class with programmatic observability, and reaches any OpenAI-compatible endpoint itself — so the litellm loop's only edge (no dep, any provider) is largely moot for the multi-surface goal. **Decision:** ship the pydantic-ai(+harness) adapter behind an optional `[agent]` extra. **Alternative kept in reserve:** a no-dep litellm MCP-only loop could be added later for users who cannot take the extra — noted, not built here.

### D2 — It's a proxy; label it everywhere
The adapter measures a *faithful generic agent's* behavior toward the artifact, using pydantic-ai's mechanisms (capabilities ≠ Claude skill runtime; agents-as-tools ≠ Claude SubAgents; Python guardrails/tool-approval ≠ external hook scripts). Carry a per-adapter `validation_ceiling` string and stamp results so no output reads as "how claude-code behaves." **Why:** the honesty norm; a proxy silently presented as ground truth is fake-green.

### D3 — Reuse the artifacts; shim the format gaps
- **Skills:** parse the existing `SKILL.md` (SkillsLibrary already does) → `Capability(id=name, description=..., instructions=body, defer_loading=True)`. Measure activation via `ctx.loaded_capability_ids` + the `load_capability` tool-call in `all_messages()`. `allowed-tools` not enforced — reported in the ceiling.
- **SubAgents:** harness `Subagents` auto-discovers `name/description/tools` markdown from `.agents/agents/`; point `agent_folders` at the Claude subagent dir (or copy) and pass a `tool_resolver` mapping `tools` names to real toolsets. Measure routing via `delegate_task` `ToolCallPart.agent_name`.
- **MCP:** attach the server as an `MCPToolset`; executed calls surface as `ToolCallPart`/`ToolReturnPart` → `ToolCallTrace` (with `result`/`error`/`latency_ms` populated). Prefer accepting an already-connected `MCPServerHandle` so MCPLibrary + MetricsLibrary reuse it for free.
- **Hooks (partial):** tool-approval (`requires_approval`) for PreToolUse-style per-tool-call allow/deny (first-class in `DeferredToolRequests`/`ToolApproved`); `Guardrails` for input/output gates. Bounded, Phase 2.

### D4 — Normalize into the existing result + metrics; change nothing downstream
Map pydantic-ai's `result.output` + `result.usage()` + `result.all_messages()` onto `AgentRunResult` (`response_text`, `tool_calls[]`, `usage`; cost via agenteval's existing `metric_source` — pydantic-ai is token-only, USD stays agenteval's job). MetricsLibrary and `_core/types.py` are untouched. Register the slug (`in-process` or `pydantic-ai`) in `get_adapter`/`_ADAPTERS` lazily (mirror the CLI `SLUG_MAP`), so importing the adapter doesn't pull pydantic-ai unless used.

### D5 — Async bridge + tier
Route the agent run through `_core.run_async` (RF nested-event-loop safety), and `enforce_no_model()` is NOT called (this is a Tier-3 model-driving keyword path). New surface keywords (if any) that expose activation/routing are Tier-3.

## Risks / Trade-offs

- **[pydantic-ai capabilities is ~3–4 weeks old; API may shift]** → pin `pydantic-ai`/`pydantic-ai-harness` versions; a live smoke per surface is the empirical check; verify the `loaded_capability_ids` read-only-vs-mutable doc conflict against the installed wheel before relying on it.
- **[Proxy mistaken for vendor truth]** → D2 labeling; docs state plainly what it does/doesn't measure.
- **[Format shims drift from Claude semantics]** (`.claude/agents`↔`.agents/agents`, `name↔id`, `tools` resolution, `allowed-tools` ignored) → keep shims small + tested against real agentskills/Claude files; state limits in the ceiling.
- **[New optional dependency]** → strictly behind `[agent]`; base + deterministic testing unaffected; missing-extra fails loud naming `[agent]`.
- **[Hooks fit is weakest]** → scope Hooks to Phase 2 and label PARTIAL (tool-approval = PreToolUse-ish only; not external command scripts).
- **[No live run of the pydantic-ai path yet]** → only the litellm MCP loop is live-verified; the pydantic-ai adapter's live smoke (MiniMax) is Phase 1's exit check.

## Migration Plan

1. `[agent]` extra + the adapter module + lazy `get_adapter` registration; missing-extra error.
2. MCP surface: attach MCPToolset / accept a connected handle → executed `ToolCallTrace`. Live MiniMax smoke.
3. Skills surface: `SKILL.md`→Capability shim + activation readout. Live smoke (a skill the model should/shouldn't load).
4. SubAgents surface: Claude subagent `.md`→harness Subagents + routing readout. Live smoke.
5. Phase 2: Hooks via tool-approval (partial) + Guardrails.
6. Docs + recipe (no-CLI end-to-end metrics) + full gate.

**Rollback:** additive, behind an extra; revert per phase.

## Open Questions

- Slug name: `in-process` vs `pydantic-ai` vs `agent-loop`? (Leaning `in-process`, provider-neutral.)
- Do the activation/routing signals warrant *new keywords* (e.g. `Skill.Get Activated Skills`, `Subagent.Get Routed Subagents` over an `AgentRunResult`) or is reading `AgentRunResult` + MetricsLibrary enough? (Leaning: a couple of thin Tier-1 reader keywords.)
- Ship the turnkey third-party `pydantic-ai-skills` loader vs the ~10-line in-house `SKILL.md`→Capability shim? (Leaning: in-house shim — fewer deps, reuses SkillsLibrary's parser.)
- Confirm the harness `Subagents` per-subagent observability beyond `delegate_task` args empirically.
