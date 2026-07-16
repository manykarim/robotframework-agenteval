# Running against a real model

Tier-1 keywords are deterministic — they parse, inspect, and assert, and never
touch a model. You can test MCP schemas, skill frontmatter, subagent config, and
hook decisions with no API key at all.

The LLM-judge (Tier-2) and coding-agent (Tier-3) keywords are different: they
call a real model. Here's the switch.

## 1. Install the `[llm]` extra

The base install stays deterministic. The judge and agent modes ride LiteLLM,
which lives behind an extra:

```bash
pip install 'robotframework-agenteval[llm]'
```

## 2. Point it at a model

The generic adapter reads the model string from `AGENTEVAL_MODEL`, or from a
per-keyword `model=` argument (the keyword argument wins). Model strings are
LiteLLM's `<provider>/<model>`:

| Model string | Talks to |
| --- | --- |
| `anthropic/claude-sonnet-4-6` | Anthropic Claude |
| `openai/gpt-4o` | OpenAI GPT-4o |

```bash
export AGENTEVAL_MODEL=anthropic/claude-sonnet-4-6
```

## 3. Provide the API key

LiteLLM reads the provider key from your environment. Each provider has its own
variable — set it in your shell or a `.env` file, and never commit real keys:

| Provider | Environment variable |
| --- | --- |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 4. Run it

```robotframework
*** Settings ***
Library    SkillsLibrary

*** Test Cases ***
Skill Activates On A Real Model
    Skill.Should Activate For
    ...    ${CURDIR}/skills/web-search.md
    ...    Find the latest news about Robot Framework
    ...    model=anthropic/claude-sonnet-4-6
```

Leave `model=` off and the keyword falls back to `AGENTEVAL_MODEL`. Without the
`[llm]` extra installed, Tier-2/Tier-3 keywords fail loudly and tell you which
extra to add.

## 5. Keep costs bounded

Real models cost money, and Tier-3 fan-out multiplies the calls. Start small:
run a handful of trials while you calibrate, and scale up once the numbers look
stable. Keep the expensive, stochastic runs on a schedule — not on every push.

## See also

- [`.env.example`](../.env.example) — where to put your API keys.
- [First eval in five minutes](./recipes/01-first-eval-in-five-minutes.md) — the
  keyless Tier-1 starting point.
