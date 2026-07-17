# Recipe 8: End-to-end agent metrics with no CLI — just an LLM key

**I want to** measure the three live surfaces — MCP tool calls, skill activation,
and subagent routing — in a single run, without installing any coding-agent CLI.
Just a model name, a `base_url`, and an API key.

This is a **Tier 3** recipe: it drives a real in-process agent loop
([pydantic-ai](https://ai.pydantic.dev/) against any OpenAI-compatible endpoint)
through the `in-process` adapter. Everything you read *afterward* is **Tier 1** —
deterministic readers over the recorded `AgentRunResult`, never model
self-report. The adapter **executes** tools (so each `ToolCallTrace` carries its
`result`), **activates** deferred skills (via the framework `load_capability`
tool), and **routes** to subagents (via `delegate_task`) — all normalized into
the same result object the metric keywords already read.

## It is a proxy — read the ceiling first

The `in-process` adapter measures a *generic competent agent's* treatment of your
artifacts. It is **not** a specific coding agent's runtime, and it says so:

```robotframework
*** Settings ***
Library    Collections

*** Test Cases ***
Know What The Adapter Cannot Promise
    ${adapter}=    Evaluate    AgentEval._core.adapter.get_adapter('in-process')
    ${ceiling}=    Evaluate    $adapter.validation_ceiling
    Log    ${ceiling}
    Should Contain    ${ceiling}    PROXY
    Should Contain    ${ceiling}    NOT enforced
```

That prints:

> PROXY: measures a generic in-process pydantic-ai agent, NOT a specific coding
> agent's runtime. Skill/subagent frontmatter maps onto pydantic-ai's model;
> `allowed-tools` / `disable-model-invocation` are NOT enforced. Cost is derived,
> not native.

So: use it to measure discoverability, routing, and tool execution on nothing but
an LLM key — never to claim "this is how Claude Code behaves." The Hooks tool
gate on the same adapter (`Hook.Get Tool Decisions`) is labeled **PARTIAL** for
the same reason — it gates in-process tool CALLS, not external `settings.json`
command scripts.

## Prerequisites

```bash
pip install 'robotframework-agenteval[agent,mcp]'   # pydantic-ai + the MCP SDK
export AGENTEVAL_MODEL=MiniMax-M2.7                    # any OpenAI-compatible chat model
export AGENTEVAL_BASE_URL=https://api.minimax.io/v1   # the endpoint's base_url
export AGENTEVAL_API_KEY=sk-...                        # read from the environment, never a RF variable
```

Keys are read straight from the process environment, never through a Robot
Framework variable (which would leak into `log.html`).

## 1. The artifacts under test

A real `SKILL.md` the model should discover, and two subagent definitions it can
route to. Save the skill as `skills/refunds.md`:

```markdown
---
name: refunds
description: Determine whether a customer order is eligible for a refund under the 30-day return policy.
---

# Refund eligibility

Check the order date, the item condition, and the 30-day window before deciding.
```

Save two subagents under `.claude/agents/` — `sql-expert.md`:

```markdown
---
name: sql-expert
description: Writes and optimizes SQL database queries and schema migrations.
---

You are a SQL specialist. Write correct, efficient queries.
```

and `poet.md`:

```markdown
---
name: poet
description: Writes poems, verse, and creative literary prose.
---

You write poetry on request.
```

## 2. A helper for the in-memory MCP server

The in-process adapter drives a *real* MCP server; an in-memory FastMCP one keeps
the recipe self-contained. Save this as `inprocess_helpers.py`:

```python
from robot.api.deco import library, keyword


def build_echo_server():
    """A zero-arg factory that builds an in-memory FastMCP echo server."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("recipe-echo")

    @server.tool(description="Echo the input text verbatim.")
    def echo_back(text: str) -> str:
        return text

    return server


@library(scope="GLOBAL")
class inprocess_helpers:
    @keyword("Echo Server Factory")
    def echo_server_factory(self):
        # MCP.Start Server calls this factory to build the server on first use.
        return build_echo_server

    @keyword("Run In-Process Agent")
    def run_in_process_agent(self, prompt, toolset, *capabilities):
        # Build the adapter with the bridged MCP toolset + the deferred skill and
        # subagent capabilities, then run one prompt. Secrets come from the env.
        from AgentEval._core import get_adapter

        adapter = get_adapter("in-process", toolsets=[toolset], capabilities=list(capabilities))
        return adapter.run(prompt)
```

## 3. The suite

Save this as `in_process_metrics.robot`. The first test drives **one** related
prompt that explicitly needs a tool call *and* a delegation, then reads both
signals off the single recorded result. The second test measures skill
activation on a skill-centric prompt — kept separate on purpose, because
activation is a *stochastic* signal: a model told to "echo, then delegate" often
answers straight from the delegation without loading an unrelated capability, so
asserting all three on one heavily-scripted prompt would be fake-green. Each
surface is asserted on the prompt shape that reliably exercises it.

```robotframework
*** Settings ***
Library    MCPLibrary
Library    SkillsLibrary
Library    SubagentsLibrary
Library    Collections
Library    inprocess_helpers.py

*** Test Cases ***
Measure MCP Tool Calls And Subagent Routing In One No-CLI Run
    # --- Wire up the real MCP server and expose it as an agent toolset. ---
    ${factory}=    Echo Server Factory
    ${handle}=    MCP.Start Server    echo    in_memory    server_factory=${factory}
    MCP.Connect To Server    ${handle}
    ${toolset}=    MCP.As Agent Toolset    ${handle}

    # --- Load the subagent dir as a deferred SubAgents capability. ---
    ${subagents}=    Subagent.As Subagents Capability    ${CURDIR}/.claude/agents

    # --- One related prompt: echo the order id, then delegate the SQL lookup. ---
    ${result}=    Run In-Process Agent
    ...    Is order #4821 eligible for a refund? Echo the order id back with the echo_back tool first, then delegate the SQL lookup to the right specialist.
    ...    ${toolset}    ${subagents}

    # --- Read both surfaces off the SAME recorded result (all Tier 1). ---
    ${tool_calls}=    MCP.Get Tool Call Count    ${result}
    Should Be True    ${tool_calls} >= 1    msg=Expected at least one executed tool call
    MCP.Was Tool Called    ${result}    echo_back

    ${routed}=    Subagent.Get Routed Subagents    ${result}
    Log    routed names=${routed.names} counts=${routed.counts} total=${routed.total}
    Should Contain    ${routed.names}    sql-expert    msg=The SQL task should route to sql-expert

    [Teardown]    MCP.Stop Server    ${handle}

Measure Real Skill Activation On A Skill-Centric Prompt
    # A prompt whose need matches the skill; an unrelated skill is loaded too.
    ${refunds}=    Skill.As Capability    ${CURDIR}/skills/refunds.md
    ${weather}=    Skill.As Capability    ${CURDIR}/skills/weather-lookup.md
    ${agent}=    Evaluate    AgentEval._core.adapter.get_adapter('in-process', capabilities=[$refunds, $weather])
    ${result}=    Evaluate    $agent.run("Is order #4821 eligible for a refund? Use the loaded skill to reason through the 30-day policy.")

    ${activated}=    Skill.Get Activated Skills    ${result}
    Should Contain    ${activated}    refunds        msg=The matching refunds skill should activate
    Should Not Contain    ${activated}    weather-lookup    msg=The unrelated skill should stay quiet
```

## 4. Run it

```bash
robot in_process_metrics.robot
```

Each reader is deterministic and reads the recorded trace, so the *shape* of the
result is stable even though the model's choices are stochastic:

- `MCP.Get Tool Call Count` counts every executed tool call the model made
  (`echo_back`, plus the `delegate_task` and `load_capability` framework calls).
- `Subagent.Get Routed Subagents` returns the named subagents the model delegated
  to, with per-name counts (`names=('sql-expert',)`, `counts={'sql-expert': 1}`).
- `Skill.Get Activated Skills` returns the skill ids the model actually activated
  (`['refunds']` for a matching prompt; empty when the model answers without it).

> Two real MiniMax-M2.7 runs on `[agent]` produced these numbers. The combined
> run: `MCP.Get Tool Call Count` → `2` (all names `['echo_back', 'delegate_task']`,
> `echo_back` executed through the handle), and the SQL task routed
> `names=('sql-expert',)`, `counts={'sql-expert': 1}`, `total=1` via a single
> `delegate_task` call. The skill-centric run: `Skill.Get Activated Skills` →
> `['refunds']` via one `load_capability` call, with the unrelated
> `weather-lookup` staying quiet. The exact numbers vary run to run — the readers
> do not. (In that same combined run the model did *not* load the refunds
> capability — it answered from the delegation — which is exactly why activation
> is asserted on its own skill-centric prompt, not folded into the scripted one.)

## 5. Feed the same result to the metric keywords

Because it is a normal `AgentRunResult`, everything in `MetricsLibrary` works
unchanged — token usage and a per-tool rollup — with one honest caveat: cost is
**derived** from tokens (pydantic-ai is token-only), so `metric_source` is
`derived`, never `native`.

```robotframework
    ${usage}=    Metric.Get Token Usage    ${result}
    Log    input=${usage}[input] output=${usage}[output]
    ${tools}=    Metric.Get Tool Call Metrics    ${result}
    Log    per-task tool count: ${tools}[per_task][count]
```

## What just happened

- `MCP.As Agent Toolset` wrapped the connected server's tools as a pydantic-ai
  toolset whose execution routes back through `MCP.Call Tool` — so the model runs
  the *real* server and every call lands in both the agent result and MCPLibrary's
  recorder.
- `Skill.As Capability` loaded the `SKILL.md` as a **deferred** capability, so the
  model advertises only its description and *activates* it by calling
  `load_capability` — a real signal, not an LLM-judge inference.
- `Subagent.As Subagents Capability` loaded the Claude subagent dir into a harness
  `SubAgents` capability whose `delegate_task` tool carries the chosen subagent.
- One `get_adapter("in-process")` run drove all three, and the Tier-1 readers
  projected each surface off the single recorded `AgentRunResult`.

## See also

- [Running against a real model](../running-against-a-real-model.md) — the
  in-process adapter is the third path (no CLI, one LLM key).
- [Recipe 7](./11-e2e-agent-metrics-cli-adapters.md) — the same metric keywords,
  driven through a vendor CLI instead.
- Keyword reference:
  [`MCPLibrary`](../keywords/MCPLibrary.html) ·
  [`SkillsLibrary`](../keywords/SkillsLibrary.html) ·
  [`SubagentsLibrary`](../keywords/SubagentsLibrary.html) ·
  [`HooksLibrary`](../keywords/HooksLibrary.html).
- [Stability surface contract](../contracts/stability-surface.md) — which
  surfaces are `stable` / `provisional` / `experimental`.
