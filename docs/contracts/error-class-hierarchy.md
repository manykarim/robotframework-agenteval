# Error Class Hierarchy

**Status:** accepted.
**Related ADRs:** ADR-014 (Error-Class Hierarchy).

> Superseded by the four-surface refocus (2026-07). The earlier version of this
> contract described four semantic sub-bases and twenty-some leaves — a design that
> never fully shipped and that the refocus retired. The live hierarchy is flat: one
> base, a dozen leaves, one stable code each. This document has been rewritten to
> match `src/AgentEval/_core/errors.py` exactly.

## Purpose

Documents agenteval's **unified error hierarchy** as a consumer-facing contract.
Every error agenteval raises inherits from `AgentEvalError` and carries a stable
`error_code`. That code is what you catch on, what CI surfaces as a failure type,
and what maps to the process exit code. If you write `except AgentEvalError:` you
catch everything agenteval throws; if you want to react to one case, catch its leaf.

## Scope

### In-scope

- The `AgentEvalError(Exception)` base and its `error_code` class attribute.
- Every leaf class, its `error_code`, its exit code, and which library raises it.
- The mapping from `error_code` to a process exit code via `error_code_to_exit_code`.

### Out-of-scope

- Generic Python exceptions (`ValueError`, `KeyError`, …) — these are caught and
  re-wrapped into an `AgentEvalError` leaf at the public-keyword boundary; consumers
  should not catch the raw Python exceptions for agenteval-owned operations.
- RF-internal errors (`RobotError` subclasses) — agenteval errors do NOT inherit from
  RF internals, so the four libraries stay usable from plain Python too.

## Contract

### Base class

```python
class AgentEvalError(Exception):
    """Base class for every error the library raises.

    Leaves set ``error_code`` to a stable ``UPPER_SNAKE`` string. When present,
    the message is prefixed with the code.
    """
    error_code: ClassVar[str] = ""  # empty on the base; leaves override
```

Every leaf inherits directly from `AgentEvalError` — there are no intermediate
sub-bases. Import them from `AgentEval._core.errors`.

### Leaf inventory

| Leaf | `error_code` | Exit code | Raised by |
| --- | --- | --- | --- |
| `InvalidConfigError` | `INVALID_CONFIG` | 65 (EX_DATAERR) | config loading, any library |
| `InvalidRubricError` | `INVALID_RUBRIC` | 65 (EX_DATAERR) | LLM-judge rubric parsing |
| `JudgeOutputParseError` | `JUDGE_OUTPUT_PARSE` | 65 (EX_DATAERR) | LLM judge (Tier-2) |
| `HookExecutionError` | `HOOK_EXECUTION` | 65 (EX_DATAERR) | HooksLibrary |
| `MissingExtraError` | `MISSING_EXTRA` | 78 (EX_CONFIG) | a keyword needing an uninstalled extra (`[mcp]`/`[llm]`/`[all]`) |
| `AdapterError` | `ADAPTER_ERROR` | 78 (EX_CONFIG) | the coding-agent driver (Tier-3) |
| `TierViolationError` | `TIER_VIOLATION` | 70 (EX_SOFTWARE) | the tier ACL gate |
| `SkillDidNotActivateError` | `SKILL_DID_NOT_ACTIVATE` | 70 (EX_SOFTWARE) | SkillsLibrary |
| `SubagentDelegationError` | `SUBAGENT_DELEGATION` | 70 (EX_SOFTWARE) | SubagentsLibrary |
| `IncompleteTraceError` | `INCOMPLETE_TRACE` | 67 | MCP coverage gate |
| `BudgetExceededError` | `BUDGET_EXCEEDED` | 66 | cost / runtime budgets |
| `MCPError` | `MCP_ERROR` | 69 | MCPLibrary (transport / spec-version failures) |

### Exit-code mapping

`error_code_to_exit_code(code)` looks the code up in the `EXIT_CODES` table above.
An unknown or empty code falls back to `70` (EX_SOFTWARE). A unit test asserts the
table's keys are exactly the set of leaf codes, so a new leaf that forgets its exit
code fails CI rather than silently mapping to the fallback.

### Adding a leaf

A new leaf class, its `error_code`, and its `EXIT_CODES` entry all land in the same
file (`src/AgentEval/_core/errors.py`) in the same change. Keep the surface
grep-able: one base, one file, one code per leaf.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The
base class and the set of `error_code` values are `stable` — renaming a leaf or its
code, or changing an exit-code mapping, breaks consumers and requires a major-version
bump. Adding a new leaf (with its own code and exit code) is minor-version-bump safe.

## References

- `src/AgentEval/_core/errors.py` — the one file this contract governs.
- ADR-014 (Error-Class Hierarchy) — the design rationale.
- [`coding-conventions.md`](coding-conventions.md) — error-message wording conventions.
