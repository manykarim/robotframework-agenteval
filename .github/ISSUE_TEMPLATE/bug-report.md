---
name: Bug Report
about: Report incorrect or unexpected behavior in robotframework-agenteval
title: "bug: <one-line summary>"
labels: [bug]
assignees: ""
---

> **Before filing:**
> - For **security issues**, do NOT file here — use the private channels in [SECURITY.md](../../SECURITY.md).
> - For **triage expectations**, see [SUPPORT.md](../../SUPPORT.md) (best-effort 5 business days).
> - For **architectural questions**, browse [docs/adr/](../../docs/adr/README.md) first.

## What happened

<!-- A clear, concise description of the bug. -->

## Minimal reproducer

<!-- Smallest .robot file or Python snippet that reproduces the issue.
     Strip user-specific credentials + paths. Use the in-memory transport where possible. -->

```robot
*** Settings ***
Library  AgentEval

*** Test Cases ***
Minimal Reproducer
    # ...
```

OR

```python
from AgentEval import AgentEval

agent = AgentEval(...)
# ...
```

## Expected behavior

<!-- What you expected to happen. -->

## Actual behavior

<!-- What actually happened. Include the full error message + stack trace if any.
     Sanitize any credentials before pasting. -->

```
<paste error / traceback here>
```

## Environment

| Component | Version |
| --- | --- |
| agenteval | <e.g., `0.0.1` or commit `abc1234`> |
| Robot Framework | <e.g., `7.4.2`> |
| Python | <e.g., `3.12.3`> |
| OS | <e.g., `Ubuntu 24.04`, `Debian 12`> |
| MCP SDK | <e.g., `mcp==1.27.1`> |
| Vendor CLI (if applicable) | <e.g., `claude 1.x`, `copilot 1.0.9`> |

## Additional context

<!-- Logs, screenshots, related issues, anything else that helps triage.
     Cite ADRs by number if your bug relates to a specific decision. -->
