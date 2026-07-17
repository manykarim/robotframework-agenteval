# robotframework-agenteval

**Test the agentic stack with Robot Framework.** MCP servers, Agent Skills, SubAgents, and Hooks — checked deterministically, judged by an LLM, or driven through a real coding agent. Same readable `.robot` syntax you already use for everything else.

The agentic parts of your product deserve tests too. A skill that never activates, an MCP tool the agent can't find, a hook that blocks the wrong thing, a subagent that swallows the task — these fail quietly and cost you later. This library gives you the keyword vocabulary to catch them, from a plain config-file check with no API key all the way up to a live agent run.

## Install

Four libraries, one package. The base install is enough to test all four surfaces deterministically — no model, no keys, no network. Reach for an extra only when you want the live modes.

```bash
pip install robotframework-agenteval          # base — deterministic mode, all four surfaces
pip install robotframework-agenteval[mcp]     # + live MCP server testing (spawn + handshake)
pip install robotframework-agenteval[llm]     # + LLM-judge and coding-agent modes
pip install robotframework-agenteval[all]     # everything
```

| Install | Pulls in | Unlocks |
|---|---|---|
| **base** | robotframework, robotlibcore, pyyaml, jsonschema | Deterministic (Tier-1) keywords for Hooks, MCP, Skills, SubAgents |
| **`[mcp]`** | + the MCP SDK | Connecting to and calling a real MCP server |
| **`[llm]`** | + litellm | The LLM judge (Tier-2) and driving a real coding agent (Tier-3) |
| **`[all]`** | `[mcp]` and `[llm]` together | The full stack |

HooksLibrary is deterministic through and through, so it never needs the `[mcp]` or `[llm]` extras — the base install covers it completely.

## The four libraries

Each library imports on its own. Test only what you touch — no need to pull in the MCP machinery to check a hook config.

```robotframework
*** Settings ***
Library    HooksLibrary
```

Prefer to grab them all at once? There's an optional composite that bundles every keyword under a single import:

```robotframework
*** Settings ***
Library    AgentEval
```

Either way you get **44 keywords across 4 libraries** — the tables below list every one, with its test mode and what it does.

## Keyword documentation

Full, always-current keyword docs (arguments, tiers, examples) are published to GitHub Pages:

- 📖 [HooksLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html)
- 📖 [MCPLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html)
- 📖 [SkillsLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html)
- 📖 [SubagentsLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html)
- 📖 [AgentEval](https://manykarim.github.io/robotframework-agenteval/keywords/AgentEval.html) (the composite of all four)

### HooksLibrary — 8 keywords

📖 [HooksLibrary keyword docs](https://manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html)

Hooks are deterministic programs: matchers, commands, exit codes, decisions. So everything here is Tier-1 — it runs without a model and gives the same answer every time.

| Keyword | Tier | What it does |
|---|---|---|
| **Hook.Get Config** | 1 | Parse a Claude Code `settings.json` hook configuration |
| **Hook.Fire Hook Event** | 1 | Fire a synthetic hook event and execute every matching command hook |
| **Hook.Decision Should Be** | 1 | Assert a fired hook's normalized block/allow/ask/none decision |
| **Hook.Exit Code Should Be** | 1 | Assert a fired hook's raw subprocess exit code |
| **Hook.Output Field Should Be** | 1 | Assert a dotted field in a fired hook's parsed stdout JSON |
| **Hook.Get Hooks For Event** | 1 | Report which hooks would fire — statically, no execution |
| **Hook.Validate Matcher Syntax** | 1 | Check a matcher compiles, optionally whether it matches a subject |
| **Hook.Command Should Exist** | 1 | Assert each hook command resolves to an executable on disk |

### MCPLibrary — 17 keywords

📖 [MCPLibrary keyword docs](https://manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html)

Parse and validate a `.mcp.json` config with no server running, or spawn the real thing and call its tools. Tool discoverability drives a live agent to see whether it actually reaches for the right tools.

| Keyword | Tier | What it does |
|---|---|---|
| **MCP.Get Server Config** | 1 | Parse a `.mcp.json` file into a `{server: entry}` dict |
| **MCP.Get Tool Schema** | 1 | Return a declared tool's input JSON Schema from the config |
| **MCP.Validate Tool Schema** | 1 | Check a tool's schema against JSON Schema Draft 2020-12 |
| **MCP.Start Server** | 1 | Build a server handle for a later connect/list/call/stop |
| **MCP.Connect To Server** | 1 | Open a session, run the handshake, check the protocol version |
| **MCP.List Tools** | 1 | List the tools a server advertises |
| **MCP.Call Tool** | 1 | Call a tool by name and return its result |
| **MCP.Stop Server** | 1 | Release the resources for a server handle |
| **MCP.Get Recorded Tool Calls** | 1 | Return the trace list recorded from live `MCP.Call Tool` calls |
| **MCP.Clear Recorded Tool Calls** | 1 | Drop all recorded `MCP.Call Tool` traces to reset between tests |
| **MCP.Get Tool Call Count** | 1 | Count tool calls in a run, a list of runs, or a trace |
| **MCP.Get Tool Call Names** | 1 | Tool-call names in order, duplicates preserved |
| **MCP.Get Tool Hit Rate** | 1 | Fraction of expected tools that were actually called |
| **MCP.Get Tool Success Rate** | 1 | Fraction of tool calls that returned without an error |
| **MCP.Get Unnecessary Call Rate** | 1 | Fraction of tool calls that were not expected |
| **MCP.Was Tool Called** | 1 | Whether a tool was called, optionally with matching arguments |
| **MCP.Get Tool Discoverability** | 3 | Drive an agent over a task set and score whether it picks the right tools |

### SkillsLibrary — 10 keywords

📖 [SkillsLibrary keyword docs](https://manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html)

Static frontmatter checks need no model. Move up a tier to ask the judge whether a response actually applied a skill's guidance, or up another to drive an agent and measure whether the skill surfaces at all.

| Keyword | Tier | What it does |
|---|---|---|
| **Skill.Get Frontmatter** | 1 | Parse a skill `.md` file's YAML frontmatter into a dict |
| **Skill.Get Description** | 1 | Return the `description` field |
| **Skill.Get Allowed Tools** | 1 | Return the `allowed-tools` list |
| **Skill.Get Disable Model Invocation** | 1 | Return the `disable-model-invocation` bool |
| **Skill.Should Be Valid Frontmatter** | 1 | Assert `name` + `description` are present (optional fields type-checked if set) |
| **Skill.Get Judge Activation Decision** | 2 | Ask the judge whether a response actually applied the skill's guidance |
| **Skill.Get Activation Decision** | 3 | Drive an agent with a prompt and report whether the skill activated |
| **Skill.Should Activate For** | 3 | Assert the skill activates for a prompt; fail if it doesn't |
| **Skill.Get Discoverability** | 3 | Score how well a skill's description surfaces it across a task set |
| **Skill.Get Activation Pass At K** | 1 | Estimate activation pass@k over trials, with a Wilson confidence band |

### SubagentsLibrary — 9 keywords

📖 [SubagentsLibrary keyword docs](https://manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html)

Read the delegation trail straight out of a run result — that's deterministic. Or drive a live orchestrator and check where it actually routed the work.

| Keyword | Tier | What it does |
|---|---|---|
| **Subagent.Get Frontmatter** | 1 | Parse the YAML frontmatter at the head of a subagent `.md` file |
| **Subagent.Get Delegations** | 1 | Extract orchestrator-to-subagent delegations from a run result |
| **Subagent.Should Have Delegated To** | 1 | Assert the run delegated to the named subagent at least once |
| **Subagent.Should Not Have Delegated** | 1 | Assert the run did not delegate (optionally to a specific subagent) |
| **Subagent.Should Declare Skills** | 1 | Assert the frontmatter explicitly declares every named skill |
| **Subagent.Tools Should Be Subset Of** | 1 | Assert the declared tools all fall within an allowlist |
| **Subagent.Should Delegate To** | 3 | Run a prompt once and assert the orchestrator delegated to the subagent |
| **Subagent.Get Delegation Decision** | 3 | Run a prompt once and return a routing decision (fan-out composable) |
| **Subagent.Get Routing Accuracy** | 3 | Run a routing-task cohort and report the fraction routed correctly |

## Three ways to test

Every keyword carries a **tier** that tells you how it runs:

- **Tier 1 — deterministic.** No model, no key, no flake. Parse a config, validate a schema, read a delegation trail. Runs the same every time.
- **Tier 2 — LLM judge.** One model call scores a response against your criteria — for the judgement calls a regex can't make.
- **Tier 3 — coding agent.** Drive a real agent end to end and measure what it actually did.

Not every mode fits every surface. Hooks are deterministic programs, so there's nothing for a judge or an agent to add — HooksLibrary is Tier-1, full stop. Here's the honest picture:

| Surface | Tier 1 · deterministic | Tier 2 · LLM judge | Tier 3 · coding agent |
|---|---|---|---|
| **Hooks** | ✅ | — | — |
| **MCP** | ✅ | — | ✅ |
| **Skills** | ✅ | ✅ | ✅ |
| **SubAgents** | ✅ | — | ✅ |

A single suite can climb the tiers as your confidence budget allows:

```robotframework
*** Settings ***
Library    SkillsLibrary

*** Test Cases ***
Skill Frontmatter Is Valid
    # Tier 1 — deterministic, no API key needed
    ${frontmatter}=    Skill.Get Frontmatter    ${CURDIR}/SKILL.md
    Skill.Should Be Valid Frontmatter    ${frontmatter}

Skill Activates When It Should
    # Tier 3 — drives a real coding agent
    Skill.Should Activate For    ${CURDIR}/SKILL.md
    ...    prompt=Please refactor this module for readability
```

## Documentation

- **Recipes** — worked, runnable examples: [`docs/recipes/`](./docs/recipes/)
- **Keyword reference** — full libdoc HTML for all four libraries: [`docs/keywords/`](./docs/keywords/)

## License

[Apache 2.0](./LICENSE).
