# Running against a real model

The scaffolded examples and every recipe run on the **mock provider** by
default, so they need no API keys. When you are ready to evaluate a real model,
switch the provider and supply an API key. This page shows the full switch.

## 1. Pick a provider

agenteval sends prompts through a *provider*. The default is `litellm`, which
talks to 100+ hosted models (Anthropic, OpenAI, and more) behind one interface.
The `mock` provider returns canned responses for keyless, deterministic tests.

Choose the provider in one of two ways:

- **Per call** — pass `provider=` to the keyword:
  `Send Prompt    provider=litellm    ...`
- **Project-wide default** — set the `AGENTEVAL_PROVIDER` environment variable
  (or `provider:` in `agenteval.yaml`). A per-call `provider=` always wins.

## 2. Choose a model string

With the `litellm` provider, a model string is `<provider>/<model>`:

| Model string | Talks to |
| --- | --- |
| `anthropic/claude-sonnet-4-6` | Anthropic Claude |
| `openai/gpt-4o` | OpenAI GPT-4o |

Pass it with `model=`.

## 3. Provide the API key

`litellm` reads the API key from your environment. Each model provider has its
own variable:

| Model provider | Environment variable |
| --- | --- |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |

Set the variable in your shell or in a `.env` file (see `.env.example`). Never
commit real keys.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 4. Run it

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Agent Answers On A Real Model
    ${result}=    Send Prompt
    ...    adapter=generic
    ...    provider=litellm
    ...    model=anthropic/claude-sonnet-4-6
    ...    prompt=Say hello in one word.
    Should Not Be Empty    ${result.response_text}
    Should Be True    ${result.cost_usd} > 0
```

The same test on the mock provider reports `cost_usd == 0`; on a real model it
reports the actual spend.

## 5. Keep costs bounded

Real models cost money. Stochastic fan-out keywords (Tier 3) enforce a cost
budget: set `max_cost_usd` in `agenteval.yaml` (or via `AGENTEVAL_MAX_COST_USD`
/ a keyword argument), and the run stops before a test exceeds it. Start with a
small budget while you calibrate.

## See also

- [`.env.example`](../.env.example) — where to put your API keys.
- [Recipe #1: First eval in 5 minutes](./recipes/01-first-eval-in-five-minutes.md)
  — the mock-provider starting point you switch from.
