---
name: researcher-subagent
description: A subagent fixture that explicitly declares skills + a narrow tools allowlist (add-subagent-delegation-testing config-drift integration test).
tools:
  - Read
  - Grep
skills:
  - pdf-tools
  - web-search
---

# Researcher Sub-Agent

Explicitly preloads `pdf-tools` + `web-search` because subagents do not
inherit the parent agent's skills.
