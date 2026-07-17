# Recipe 7: End-to-end agent metrics through a CLI adapter

**I want to** drive a real prompt through an installed coding-agent CLI, read
back the ground-truth metrics of that run — tool calls, tokens, cost — and
export them to JSON so a budget gate or a dashboard can consume them.

This is a **Tier 3** recipe: it runs a real agent. The metrics you read afterward
are all **Tier 1** — deterministic readers over the recorded run, never model
self-report. Every number comes from the CLI's own machine-readable output (or,
where the CLI does not report it, is honestly left at zero).

## The adapters, and what each can honestly report

`get_adapter(slug)` builds one adapter per installed CLI. Fidelity is **uneven
across vendors** and is labeled per adapter, because a JSON schema a vendor never
documented cannot be parsed as if it were complete. Read this table before you
pick a slug — it is the difference between a real budget gate and a fake-green
one.

| Slug | CLI | Fidelity | Tool calls | Tokens | Cost |
|------|-----|----------|-----------|--------|------|
| `claude-code` | `claude` | **FULL** | yes | yes (native) | **native USD** |
| `gemini` | `gemini` | **FULL** | counts | yes (native) | derived from tokens |
| `codex` | `codex` | PARTIAL | yes | run-level only | derived from tokens |
| `opencode` | `opencode` | PARTIAL | yes | per-step | native per-step |
| `kilo` | `kilo` | **DEGRADED** | best-effort | only if transcript exposes | **often none** |
| `copilot` | `copilot` | **DEGRADED** | best-effort | best-effort | **never USD** |

- **FULL** (`claude-code`, `gemini`) — tool-call and token metrics are read
  natively from the CLI's structured output. `claude-code` additionally reports
  native USD cost; `gemini` derives cost from tokens and a price table.
- **PARTIAL** (`codex`, `opencode`) — tool calls are captured, but some fields
  (per-tool token attribution, native cost, or latency) are not reported by the
  CLI and stay `0`.
- **DEGRADED** (`kilo`, `copilot`) — the event schema is undocumented or the CLI
  reports no dollar cost at all. These adapters parse what they can and leave the
  rest at zero. **Never** wire a DEGRADED adapter into a `Cost Should Be Below`
  gate — a zero cost there is a missing metric, not a cheap run.

Every adapter carries a one-line `validation_ceiling` naming exactly what it
cannot report. Print it before you trust the numbers — see
[Honesty: read the ceiling](#honesty-read-the-ceiling) below.

## Prerequisites

```bash
pip install 'robotframework-agenteval[llm]'
```

Plus the CLI itself on your `PATH` and its credentials in the environment. If
the binary is missing, the adapter fails loud, naming the binary and its install
hint — it never silently no-ops.

## 1. A helper that runs the adapter

Robot Framework needs an `AgentRunResult` object to feed the `Metric.*` keywords.
A four-line helper library runs the adapter once and hands the result back. Save
this as `agent_runner.py` — secrets are read from the environment by the child
process, never passed on the command line:

```python
from robot.api.deco import library, keyword
from AgentEval._core import get_adapter


@library(scope="GLOBAL")
class agent_runner:
    @keyword("Run Prompt Through Adapter")
    def run_prompt_through_adapter(self, slug, prompt, timeout=300):
        adapter = get_adapter(slug)
        return adapter.run(prompt, timeout=float(timeout))

    @keyword("Get Adapter Fidelity")
    def get_adapter_fidelity(self, slug):
        adapter = get_adapter(slug)
        return {"fidelity": adapter.fidelity, "ceiling": adapter.validation_ceiling}
```

## 2. The suite

Save this as `agent_metrics.robot`. It runs one prompt through the `claude-code`
adapter, asserts on the tool calls and token usage, holds the run to a cost
budget, and exports the normalized metrics to JSON:

```robotframework
*** Settings ***
Library    MetricsLibrary
Library    agent_runner.py

*** Variables ***
${SLUG}      claude-code
${PROMPT}    List the files in the current directory using your tools, then say how many there are.

*** Test Cases ***
Agent Run Reports Ground-Truth Metrics
    ${result}=    Run Prompt Through Adapter    ${SLUG}    ${PROMPT}

    # Tool calls — read straight off the recorded trace.
    ${tools}=    Metric.Get Tool Call Metrics    ${result}
    Should Be True    ${tools}[per_task][count] >= 1
    ...    msg=Expected the agent to call at least one tool

    # Token usage — input, output, cached.
    ${usage}=    Metric.Get Token Usage    ${result}
    Log    input=${usage}[input] output=${usage}[output] cached=${usage}[cached]

    # Cost — a FULL adapter reports native USD; hold the run to a budget.
    ${cost}=    Metric.Get Cost USD    ${result}
    Log    run cost: $${cost}
    Metric.Cost Should Be Below    ${result}    1.00

Export The Run Metrics To JSON
    ${result}=    Run Prompt Through Adapter    ${SLUG}    ${PROMPT}

    # Declare what the run was supposed to do, then compute the record.
    ${expected}=    Evaluate    [{'tool': 'Bash', 'min_calls': 1}]
    ${metrics}=    Metric.Get Run Metrics    ${result}    ${expected}
    Log    tool hit rate: ${metrics.tool_hit_rate}

    Metric.Export Run Metrics    ${metrics}    ${OUTPUT_DIR}/run-metrics.json
```

## 3. Run it

```bash
robot agent_metrics.robot
```

The exported `run-metrics.json` is ground-truth from the recorded run — nothing
in it is model self-report:

```json
{
  "total_tool_calls": 1,
  "tool_hit_rate": 1.0,
  "expected_met": 1,
  "expected_total": 1,
  "usage": {
    "input_tokens": 4,
    "output_tokens": 866,
    "cached_input_tokens": 53386
  },
  "cost_usd": 0.22816,
  "errors": [],
  "tool_calls": [
    {"name": "Bash", "error": null, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
  ]
}
```

> The exact token and cost numbers vary run to run — the shape does not. These
> values are from one real `claude-code` run (`claude` 2.1.212): one `Bash` tool
> call, native cost `$0.228`, `metric_source=native`. Per-tool token/cost stay
> `0` because the CLI does not break usage out per tool — that gap is this
> adapter's `validation_ceiling`, not a bug.

## Honesty: read the ceiling

Before you trust a number, ask the adapter what it cannot report. A DEGRADED
adapter answers honestly rather than fabricating a metric:

```robotframework
*** Settings ***
Library    agent_runner.py

*** Test Cases ***
Know What A Degraded Adapter Cannot Report
    ${info}=    Get Adapter Fidelity    copilot
    Should Be Equal    ${info}[fidelity]    DEGRADED
    Log    ${info}[ceiling]
```

That prints, for `copilot`:

> copilot reports no USD cost (only a premiumRequests counter, which is NOT
> dollars), so cost_usd is always 0 and metric_source=none. […] Do not treat
> copilot runs as a complete metric source.

Two rules fall out of this:

1. **Check `metric_source` before gating on cost.** A `result.metadata.metric_source`
   of `none` means the cost is absent, not zero — a `Cost Should Be Below` gate
   would pass vacuously. Gate on cost only for `native`/`derived` sources
   (`claude-code`, `gemini`, `codex`, `opencode`).
2. **Match the assertion to the fidelity.** Assert tool-call counts on any
   adapter; assert per-tool token attribution on none of them (no shipped CLI
   reports it); assert native USD cost only on `claude-code`.

A DEGRADED adapter is still useful — it drives the agent and captures the
tool-call trace — but it is an honest partial, and the `validation_ceiling` is
how it tells you so.

## What just happened

- `Run Prompt Through Adapter` resolved the CLI by slug through `get_adapter`,
  ran it as a subprocess (secrets from the environment, never on argv), and
  normalized the output into an `AgentRunResult`.
- `Metric.Get Tool Call Metrics`, `Metric.Get Token Usage`, and
  `Metric.Get Cost USD` read that recorded result — all Tier 1, all
  deterministic.
- `Metric.Cost Should Be Below` is a budget assertion: it raises
  `BudgetExceededError` naming the actual cost when the run is too expensive.
- `Metric.Get Run Metrics` folded in a declarative expected-tool contract and
  computed a `tool_hit_rate`; `Metric.Export Run Metrics` wrote the whole
  normalized record to JSON.

## See also

- [Recipe 5](./10-subagent-config-drift-and-routing.md) — projecting delegations
  out of an `AgentRunResult` (the same result object, a different reader).
- [Recipe 6](./08-ci-integration.md) — wiring a Tier-3 gate into CI on a schedule.
- [`MetricsLibrary` keyword reference](../keywords/MetricsLibrary.html) — every
  `Metric.*` keyword.
- [Stability surface contract](../contracts/stability-surface.md) — which
  surfaces are `stable` / `provisional` / `experimental`.
