# robotframework-agenteval — documentation

Test the agentic stack — MCP servers, Agent Skills, SubAgents, and Hooks —
with Robot Framework. Deterministically, with an LLM judge, or by driving a
real coding agent. You already know how to write Robot tests; now you can point
them at the things your agents actually depend on.

**64 keywords across 6 libraries.** Import only what you test.

## The four libraries

Each library is imported on its own and namespaces its keywords, so there is no
`WITH NAME` bookkeeping and no giant catch-all import to reason about.

```robotframework
*** Settings ***
Library    HooksLibrary
```

| Library | Keywords | Prefix | What it tests |
| --- | --- | --- | --- |
| [`MCPLibrary`](./keywords/MCPLibrary.html) | 17 | `MCP.` | MCP server config, tool schemas, live server lifecycle, and tool-call coverage |
| [`SkillsLibrary`](./keywords/SkillsLibrary.html) | 10 | `Skill.` | Skill `.md` frontmatter, and whether a skill actually activates |
| [`SubagentsLibrary`](./keywords/SubagentsLibrary.html) | 9 | `Subagent.` | SubAgent config drift and delegation routing |
| [`HooksLibrary`](./keywords/HooksLibrary.html) | 8 | `Hook.` | Claude Code hook config, matcher rules, and real block/allow decisions |

Want them all in one line? There is an optional composite:

```robotframework
*** Settings ***
Library    AgentEval
```

Prefer importing the one surface you test. Reach for `AgentEval` only when a
suite genuinely exercises several at once.

## The three tiers — one honest label per keyword

Every keyword declares how it runs. No surprises about what costs money.

| Tier | Mode | Needs |
| --- | --- | --- |
| **Tier 1** | Deterministic — parse files, project traces, assert. No model in the loop. | Base install |
| **Tier 2** | LLM judge — ask a model whether the output really did the thing. | `[llm]` extra |
| **Tier 3** | Coding agent — drive a real agent and read back what it did. | `[llm]` extra |

Some surfaces are Tier-1 all the way down. **Hooks are deterministic
programs**, so `HooksLibrary` is **Tier-1 only** — it fires your hook scripts
and checks their exit codes and decisions, no LLM, no API keys. We do not
pretend a deterministic script needs a judge.

## Install

The base install covers deterministic (Tier-1) testing for all four libraries:

```bash
pip install robotframework-agenteval
```

Add extras when you need live servers or a model:

| Extra | Adds | Unlocks |
| --- | --- | --- |
| `[mcp]` | the MCP SDK | live MCP server testing — start, connect, list, call |
| `[llm]` | LiteLLM | Tier-2 judge mode + Tier-3 agent mode |
| `[all]` | both | everything |

```bash
pip install 'robotframework-agenteval[all]'
```

The base dependencies are Robot Framework, robotlibcore, PyYAML, and
jsonschema — nothing heavier until you ask for it.

## Recipes

Worked examples, one per surface plus CI wiring. Start with the five-minute
one. See [`recipes/`](./recipes/) for the full gallery.

## Architecture decisions

The decision records cover the adapter seam, tier rules, MCP observation, and
the error hierarchy. See [`adr/`](./adr/).

## Doc contracts

Stable contracts governing the public surfaces. See [`contracts/`](./contracts/).

## License

[Apache 2.0](https://github.com/manykarim/robotframework-agenteval/blob/main/LICENSE).
Built in the open — issues and pull requests welcome on
[GitHub](https://github.com/manykarim/robotframework-agenteval).
