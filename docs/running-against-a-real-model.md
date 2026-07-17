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

## The other path: a coding-agent CLI

Steps 1–4 above are the **LiteLLM path** — AgentEval talks to a hosted model
through its built-in generic adapter. The second way to run against something
real is the **coding-agent-CLI path**: instead of a hosted chat model, AgentEval
shells out to a real agent binary you've installed, lets it run its own tool
loop, and normalizes the result into the same `AgentRunResult` the LiteLLM path
produces. Same metric keywords, same result shape — the difference is where the
work happens.

Two things change on this path:

- **You install the binary yourself.** The CLIs are not packaged with AgentEval
  (no vendor SDKs, no extra to add). The adapter fails loud with install
  guidance if the binary isn't on `PATH`.
- **Credentials stay with the CLI.** Each agent already has its own login or
  API-key mechanism. AgentEval reads whatever that CLI reads — nothing passes
  through a Robot Framework variable, so nothing lands in `log.html`.

### Pick a CLI by its adapter slug

You name a CLI by its **adapter slug**. Each slug has its own install command,
its own credential location, and — importantly — its own **fidelity tier** that
tells you how much of the tool-call / token / cost picture that CLI actually
reports.

| CLI | Adapter slug | Fidelity | What the numbers mean |
| --- | --- | --- | --- |
| Claude Code | `claude-code` | **FULL** | Native tool calls, tokens (with cache), and cost, straight from the run |
| Gemini CLI | `gemini` | **FULL** | Native tool calls and tokens; cost derived from token counts |
| Codex CLI | `codex` | **PARTIAL** | Native tool calls and tokens; cost derived |
| opencode | `opencode` | **PARTIAL** | Native tool calls, tokens, and cost |
| Kilo | `kilo` | **DEGRADED** | Best-effort: tool calls probed, tokens/cost estimated |
| Copilot CLI | `copilot` | **DEGRADED** | Best-effort: metrics reconstructed from the session log |

**FULL / PARTIAL / DEGRADED is not decoration — read it before you trust a
number.** FULL adapters report tool calls, tokens, and cost natively. PARTIAL
adapters capture tool calls and tokens natively but *derive* cost from the token
counts (there's no native cost field to read). DEGRADED adapters — `kilo` and
`copilot` — reconstruct their metrics best-effort from a `--version`-gated probe
or from the newest on-disk session transcript, so their tool-call, token, and
cost numbers are **lower-fidelity than the FULL/PARTIAL adapters and must not be
read as ground-truth**. Any derived (non-native) cost or token figure is flagged
in the run metadata (`metric_source`) so a report can distinguish measured from
estimated.

### Install and authenticate each CLI

Install only the ones you plan to drive. The commands below install the binary;
follow each with its own login step.

```bash
# Claude Code  (slug: claude-code)  — FULL
npm install -g @anthropic-ai/claude-code
claude login                 # or: export ANTHROPIC_API_KEY=sk-ant-...
#   config + session transcripts under ~/.claude/

# Gemini CLI  (slug: gemini)  — FULL
npm install -g @google/gemini-cli
gemini                       # first run walks OAuth; or: export GEMINI_API_KEY=...
#   config under ~/.gemini/

# Codex CLI  (slug: codex)  — PARTIAL
npm install -g @openai/codex
codex login                  # or: export OPENAI_API_KEY=sk-...
#   session rollouts under ~/.codex/sessions/

# opencode  (slug: opencode)  — PARTIAL
npm install -g opencode-ai   # see https://opencode.ai for other installers
opencode auth login          # stores the provider key opencode reads

# Kilo  (slug: kilo)  — DEGRADED
#   install per https://kilocode.ai ; authenticate with the provider/router
#   key in the Kilo config the CLI reads

# GitHub Copilot CLI  (slug: copilot)  — DEGRADED
npm install -g @github/copilot
gh auth login                # or: export GITHUB_TOKEN=...
```

Every one of these reads its credentials from its own login store or an
environment variable — the same rule as the LiteLLM path applies: keep real keys
out of committed files and out of Robot Framework variables. A `.env` you don't
commit is the safe home for any `*_API_KEY` or `GITHUB_TOKEN` you export.

### The same keywords, whichever path you're on

Because every adapter — LiteLLM or CLI — normalizes into the same
`AgentRunResult`, the metric keywords don't care which path produced the run.
You read token usage, tool-call counts, cost, and latency the same way, and the
budget assertions fail the same way, whether the numbers came from a hosted
model or a coding-agent CLI. When you drive a DEGRADED adapter, cross-check the
`metric_source` metadata before you quote its cost or token totals.

For a full worked run that produces tool-call, token, and cost numbers end to
end, see the end-to-end metrics recipe under [`recipes/`](./recipes/).

## See also

- [`.env.example`](../.env.example) — where to put your API keys.
- [First eval in five minutes](./recipes/01-first-eval-in-five-minutes.md) — the
  keyless Tier-1 starting point.
