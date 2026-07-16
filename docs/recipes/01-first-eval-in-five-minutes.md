# Recipe 1: First eval in five minutes

**I want to** write my first agent test and see it pass — no API keys, no
model, no ceremony.

**Time budget:** five minutes.
**Prerequisites:** Python 3.11+ and `pip` (or `uv`).

The fastest way in is a Tier-1 test: deterministic, keyless, instant. We will
validate a Skill's `.md` frontmatter — a real check you would run in CI to catch
a broken skill before it ships.

## 1. Install

```bash
pip install robotframework-agenteval
```

The base install is enough for every Tier-1 keyword across all four libraries.
No extras needed yet.

## 2. Write a skill to test

Save this as `skills/web-search.md`:

```markdown
---
name: web-search
description: Search the web for current information and cite the sources.
allowed-tools: [WebSearch, WebFetch]
disable-model-invocation: false
---

# Web Search

Use this skill when the user asks about current events or anything you need to
look up. Always cite your sources.
```

## 3. Write the suite

Save this as `skill_validation.robot`:

```robotframework
*** Settings ***
Library    SkillsLibrary

*** Test Cases ***
Web Search Skill Has Valid Frontmatter
    ${fm}=    Skill.Get Frontmatter    ${CURDIR}/skills/web-search.md
    Skill.Should Be Valid Frontmatter    ${fm}

Web Search Skill Declares The Right Tools
    ${tools}=    Skill.Get Allowed Tools    ${CURDIR}/skills/web-search.md
    Should Contain    ${tools}    WebSearch
    Should Contain    ${tools}    WebFetch

Web Search Skill Stays Model-Invokable
    ${disabled}=    Skill.Get Disable Model Invocation    ${CURDIR}/skills/web-search.md
    Should Be Equal    ${disabled}    ${False}
```

## 4. Run it

```bash
robot skill_validation.robot
```

```
==============================================================================
Skill Validation
==============================================================================
Web Search Skill Has Valid Frontmatter                                | PASS |
Web Search Skill Declares The Right Tools                             | PASS |
Web Search Skill Stays Model-Invokable                                | PASS |
------------------------------------------------------------------------------
Skill Validation                                                      | PASS |
3 tests, 3 passed, 0 failed
==============================================================================
```

That is a real eval. No model was called, nothing left your machine, and the
whole thing ran in well under a second — exactly what you want gating a pull
request.

## What just happened

- `Skill.Get Frontmatter` parsed the YAML at the head of the `.md` file.
- `Skill.Should Be Valid Frontmatter` enforced the four-field contract:
  `name`, `description`, `allowed-tools`, and `disable-model-invocation`, with
  the right types. Break any of them and the test fails, naming the culprit.
- The typed getters (`Skill.Get Allowed Tools`, `Skill.Get Disable Model
  Invocation`) let you assert on the details that matter to your project.

Every keyword here is **Tier 1** — deterministic, keyless, fast.

## Next steps

- **Test an MCP server's config** — [Recipe 2](./07-first-mcp-server-test-tier-1.md).
- **Ask a judge whether the skill actually fired** — [Recipe 3](./04-skill-author-stacked-validation.md) climbs into Tier 2 and Tier 3.
- **Check your Claude Code hooks** — [Recipe 4](./09-testing-claude-code-hooks.md).
- **Test SubAgent routing** — [Recipe 5](./10-subagent-config-drift-and-routing.md).
- **Wire it into CI** — [Recipe 6](./08-ci-integration.md).

Going live? Tier-2 and Tier-3 keywords need the `[llm]` extra and a model —
see the install matrix on the [docs home](../index.md).
