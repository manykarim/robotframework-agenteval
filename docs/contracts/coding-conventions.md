# Coding Conventions

**Status:** accepted (Story 1a.5 ratification 2026-05-18).
**Owning epic:** Story 1a.5
**Related ADRs:** ADR-014 (Error-Class Hierarchy — FR59 error-format prose conventions); architecture Step-5 reference card style.
**Related references:** [`CONTRIBUTING.md`](../../CONTRIBUTING.md), `pyproject.toml` ruff + mypy configurations, `ruff.toml`, `mypy.ini`.

## Purpose

Documents agenteval's **coding conventions** as a side-by-side good / anti-pattern reference card. Per architecture Step-5, this contract is the single artifact contributors consult before opening a PR. The CI surface (`ci.yml`'s `ruff check` + `ruff format --check` + `mypy src/` steps) enforces what's machine-checkable; this doc covers the human-judgment-level conventions (naming, docstring style, comment policy, error-message wording, type-annotation idioms).

## Scope

### In-scope

- Naming conventions: modules, classes, functions, variables, constants, RF keywords.
- Type annotations: where required, which idioms preferred (e.g., `Literal[...]` for closed sets, `Protocol` for structural typing).
- Docstring style (Google) + when required + content.
- Error messages: FR59 format requirements (file path, line, field, fix suggestion) per [`error-class-hierarchy.md`](error-class-hierarchy.md).
- Comment policy: where comments are required, where they're discouraged.
- Import ordering: ruff-enforced (`isort`-compatible).
- Test-naming: `tests/<dir>/test_*.py` conventions per category (unit / acceptance / conformance).
- License headers: every `src/AgentEval/**/*.py` carries Apache 2.0 header (Story 1a.5 + `.pre-commit-config.yaml` + ci.yml enforce).

### Out-of-scope

- Ruff + mypy rule lists — those live in `ruff.toml` + `mypy.ini`. This contract covers the human-judgment dimension; the config files are the machine-enforced one.
- Per-keyword libdoc style — that's a separate per-keyword consideration governed by RF Library conventions.

## Contract

### Naming Conventions

| Element | ✅ Good | ❌ Anti-pattern | Enforcement |
| --- | --- | --- | --- |
| Module file | `coding_agent.py` (lowercase_snake) | `CodingAgent.py`, `coding-agent.py` | ruff N999 + Python import convention |
| Class | `CodingAgentAdapter` (PascalCase) | `coding_agent_adapter`, `codingAgentAdapter` | ruff N801 |
| Function / method | `get_tool_calls()` (lowercase_snake) | `getToolCalls()`, `GetToolCalls()` | ruff N802 |
| Variable | `mcp_coverage` (lowercase_snake) | `MCPCoverage`, `mcpCoverage` | ruff N806 |
| Constant | `MAX_COST_USD` (UPPER_SNAKE) | `max_cost_usd`, `MaxCostUSD` | convention; not auto-enforced |
| RF keyword (public surface) | `Get Tool Call Count` (Title Case With Spaces) | `getToolCallCount`, `get_tool_call_count` | RF Library convention |
| Underlying Python method for RF keyword | `get_tool_call_count` (lowercase_snake) | `getToolCallCount` | ruff N802 |
| Private function / variable | `_resolve_adapter()`, `_cache` (leading underscore) | `__resolve_adapter`, `private_resolve_adapter` | convention |
| Error class | `IncompleteTraceError`, `ValidateOperatorDisallowed` (PascalCase, often `*Error` suffix) | `incomplete_trace_error` | convention; ADR-014 lists ratified names |

### Type Annotations

| Use case | ✅ Good | ❌ Anti-pattern | Notes |
| --- | --- | --- | --- |
| Public function | `def get_tool_calls(adapter: CodingAgentAdapter) -> list[ToolCallTrace]:` | `def get_tool_calls(adapter):` | mypy strict requires annotation on public surface |
| Closed enum | `mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` | `mcp_coverage: str` | matches ADR-016 ratified 3-value enum |
| Optional | `prompt: str \| None = None` (3.10+ union syntax) | `prompt: Optional[str] = None` | pyproject.toml targets py3.12+; prefer modern syntax |
| Structural typing | `class CodingAgentAdapter(Protocol): ...` | abstract base class for caller-facing contract | per ADR-003; ABCs reserved for `SubprocessAdapter` internal base |
| Type alias | `type ToolCallList = list[ToolCallTrace]` (PEP 695, 3.12+) | `ToolCallList = List[ToolCallTrace]` | use modern PEP 695 since project pins py3.12+ |
| TypedDict (configs) | `class MCPConfig(TypedDict, total=False): ...` | dict-of-Any | mypy can verify `total=False` partial dicts |

### Docstring Style — Google

| Element | Required? | Example |
| --- | --- | --- |
| Module docstring | Required on every public module | `"""High-level summary of what this module exports."""` |
| Public function | Required | See below |
| Public class | Required | See below |
| Private function | Optional (`# comment` acceptable for short ones) | — |
| Property | Required if non-obvious | See below |

Function docstring example:

```python
def get_tool_calls(
    adapter: CodingAgentAdapter,
    *,
    coverage_mode: Literal["strict", "lenient"] = "strict",
) -> list[ToolCallTrace]:
    """Extract observed tool calls from the adapter's last run.

    Args:
        adapter: The adapter whose `AgentRunResult` to inspect.
        coverage_mode: Strict raises `IncompleteTraceError` on
            `mcp_coverage="external_mixed"`; lenient downgrades to a warning.

    Returns:
        Ordered list of tool calls in the order they fired. Empty list if
        the adapter produced no tool calls (NOT None).

    Raises:
        IncompleteTraceError: When `coverage_mode="strict"` and the run had
            external MCP servers in play (per ADR-007).
        AgentEvalCompatError: If the adapter is incompatible with
            agenteval's supported MCP spec range (per ADR-008).
    """
```

Class docstring example:

```python
class SubprocessAdapter(Protocol):
    """Internal base for CLI-driven coding-agent adapters.

    Per ADR-003: subclasses MUST implement `_spawn`, `_parse_event`,
    `_finalize`. The base class owns subprocess lifecycle (signal handling,
    timeout, stderr capture, truncation detection). Community CLI-adapter
    authors subclass this — it's part of the contributor-facing public API.

    Attributes:
        timeout: Maximum wall-clock seconds before the subprocess is killed.
        env: Environment variables injected into the subprocess.
    """
```

### Error Messages — FR59 format

Every **Tier-1 setup-failure error** follows the FR59 format documented in [`error-class-hierarchy.md`](error-class-hierarchy.md):

```
<ERROR_CODE>: <one-line summary>
  File: <absolute or repo-relative path>
  Line: <line number> (or N/A if not line-specific)
  Field: <YAML/config field name at fault> (or N/A)
  Fix: <one-line remediation hint> (optional but strongly preferred)
```

Implementation pattern:

```python
class SandboxRequiredError(AgentEvalSafetyError):
    error_code = "SANDBOX_REQUIRED"

    def __init__(self, *, file: str, line: int | None, field: str | None, fix: str | None = None) -> None:
        msg_parts = [
            f"{self.error_code}: Code-execution scenario requires a sandbox backend.",
            f"  File: {file}",
            f"  Line: {line if line is not None else 'N/A'}",
            f"  Field: {field or 'N/A'}",
        ]
        if fix:
            msg_parts.append(f"  Fix: {fix}")
        super().__init__("\n".join(msg_parts))
```

Tier-2 + Tier-3 errors (runtime, not setup-failure) are NOT subject to FR59 — they format per their domain (cost / runtime / MCP-coverage contexts). See [`error-class-hierarchy.md`](error-class-hierarchy.md) for the 11-leaf table + per-leaf `error_code` + sysexits-style exit codes.

### Comment Policy

| Pattern | Stance | Rationale |
| --- | --- | --- |
| Comments explaining *why* (intent, trade-offs, history) | ✅ Strongly preferred | Self-documenting code can't capture rationale. |
| Comments explaining *what* code does | ❌ Discouraged | The code itself shows what; comments rot when code changes. |
| `# TODO:` without an issue link | ❌ Banned | Untracked debt. Use `# TODO(#NNN):` with the GitHub issue number. |
| `# FIXME:` without an issue link | ❌ Banned | Same as TODO. |
| Module-level header block (above license header) | ❌ Discouraged | The module docstring is the canonical summary; redundant header blocks rot. |
| ADR cross-references in comments (`# Per ADR-014`) | ✅ Encouraged | Architectural decisions are stable; comments citing them age well. |
| Spike findings cited in comments (`# Story 0.1 spike: see ADR-004 Consequences`) | ✅ Encouraged | Empirical history is load-bearing for the implementation choice. |

### Import Ordering — ruff `isort`-compatible

Order (top to bottom; one blank line between groups):

1. `__future__` imports
2. Standard library (`import os`, `import json`)
3. Third-party (`import litellm`, `import robot`, `from mcp import ...`)
4. First-party (`from AgentEval._kernel.discovery import ...`)
5. Local relative imports (`from .errors import ...`)

Within each group, imports are alphabetical (ruff enforces). Star imports (`from X import *`) banned outside `__init__.py`. `__init__.py` star-imports allowed for explicit re-export patterns.

Example:

```python
# 1. __future__
from __future__ import annotations

# 2. Standard library
import asyncio
import json
import sys
from pathlib import Path
from typing import Literal, Protocol

# 3. Third-party
import litellm
from mcp.client.stdio import stdio_client
from robot.api import logger

# 4. First-party
from AgentEval._kernel.discovery import find_coding_agent
from AgentEval.errors import IncompleteTraceError

# 5. Local relative
from .helpers import _redact_credentials
```

### Test Naming

| Test category | File location | Function naming |
| --- | --- | --- |
| Unit | `tests/unit/<module>/test_<what>.py` | `test_<what>__<when>__<then>` (3-part separated by double underscore) |
| Convention enforcers | `tests/unit/conventions/test_<rule>.py` | same as unit |
| Acceptance smoke | `tests/acceptance/smoke/test_<scenario>.py` | `test_<scenario>` |
| Acceptance Tier-1 | `tests/acceptance/tier1/test_<ac_label>.py` | `test_<ac_label>` (matches AC label from PRD) |
| Acceptance Tier-3 | `tests/acceptance/tier3/test_<scenario>.py` (pytest mark `@pytest.mark.live`) | `test_<scenario>` |
| Conformance | `tests/conformance/test_ac_<ac_label>.py` (per ADR-017 — per-AC file + per-adapter parametrize) | `test_<assertion>` |
| Integration (live LLM) | `tests/integration/test_<scenario>.py` (pytest mark `@pytest.mark.live`) | `test_<scenario>` |

Unit-test naming example:

```python
# tests/unit/mcp/test_observer.py
def test_observer__hosted_in_process__captures_all_tool_calls():
    ...

def test_observer__external_mixed__raises_incomplete_trace_error():
    ...
```

The 3-part `__<when>__<then>` form makes pytest's test-IDs self-documenting in CI logs. Acceptance + conformance tests use simpler naming since they map 1:1 to PRD acceptance criteria.

### License Headers (Story 1a.5 enforced)

Every Python source file under `src/AgentEval/` MUST start with the canonical Apache 2.0 header (13 lines, see [`scripts/apply-license-headers.py`](../../scripts/apply-license-headers.py)). Enforcement:

- `.pre-commit-config.yaml` runs `scripts/check-license-headers.py` on every commit (local).
- `.github/workflows/ci.yml` runs the same check in CI (catches `git commit --no-verify` bypass).

Test files under `tests/` are NOT required to carry the header (they're not part of the shipped wheel per `pyproject.toml` `[tool.hatch.build.targets.wheel] packages = ["src/AgentEval"]`). Scripts under `scripts/` are not required either (they're tooling, not shipped code).

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The conventions are **`stable`** from 2026-05-18 onward — additions are minor-version-bump safe (new convention rules; existing code remains conforming). Renaming or restyling existing conventions (e.g., changing docstring style from Google to NumPy, or renaming the FR59 error-format) requires:

- An ADR amendment + cross-reference in this contract.
- A documented migration path for existing code (mechanical `ruff --fix` migration where possible; manual otherwise).
- A deprecation cycle for at least one minor version where both old + new styles are accepted.

Machine-enforced rules (in `ruff.toml` / `mypy.ini`) can tighten without an ADR amendment — but loosening an enforced rule (e.g., disabling `N999` module-naming check) requires an ADR amendment + an entry in CHANGELOG explaining what previously-blocked patterns are now allowed.

## References

- Architecture Step-5 reference card (the source for this contract's structure)
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — PR workflow + DCO sign-off requirement
- [`error-class-hierarchy.md`](error-class-hierarchy.md) — FR59 format + 11-leaf canonical names + `error_code` values
- [`ruff.toml`](../../ruff.toml) — machine-enforced subset (line length, rule selection)
- [`mypy.ini`](../../mypy.ini) — type-check rules
- `pyproject.toml` `[tool.ruff]` + `[tool.mypy]` sections (Story 1a.1 baseline)
- [`scripts/apply-license-headers.py`](../../scripts/apply-license-headers.py) — Apache 2.0 header backfill (Story 1a.5)
- [`scripts/check-license-headers.py`](../../scripts/check-license-headers.py) — header-presence verifier (pre-commit + ci.yml)
- PEP 8 (style) + PEP 484 (type annotations) + PEP 526 (variable annotations) + PEP 695 (`type` statement, 3.12+) — Python idioms agenteval inherits
- Google Python Style Guide §3.8 (Comments and Docstrings) — Google docstring convention source
