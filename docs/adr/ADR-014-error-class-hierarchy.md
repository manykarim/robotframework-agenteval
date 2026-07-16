# ADR-014: Error-Class Hierarchy

**Status:** accepted
**Date:** 2026-05-17

> Superseded by the four-surface refocus (2026-07) where the shape drifted. The
> decision — one base class, one file, a stable `error_code` on every leaf that
> maps to an exit code — is exactly what agenteval ships. What changed: the four
> speculative sub-bases (Safety / Budget / Compat / Integrity) never earned their
> keep, so the live hierarchy is flat, and the leaf set now names real surfaces
> (hooks, skills, subagents, MCP, judge) instead of the retired sandbox, adapter,
> and polling machinery. The leaf table below has been updated to match
> `src/AgentEval/errors.py`.

## Context

agenteval raises a dozen distinct error classes across its surface. CI integration
needs structured error information: emitting a meaningful failure type into the
report, and mapping a raised error to a documented process exit code. Without a
common base class and a stable code on each leaf, every surface invents its own
convention, programmatic catch (`except AgentEvalError:`) stops working, and the
exit-code mapping turns brittle.

## Decision

agenteval publishes a single, flat error hierarchy at `src/AgentEval/errors.py`:

- **Base:** `AgentEvalError(Exception)` — every agenteval-raised error inherits from
  it. Carries a `error_code: ClassVar[str]` (empty on the base; set on each leaf).
  When present, the message is prefixed with the code (`"INCOMPLETE_TRACE: ..."`).

- **Leaves inherit directly from the base** — no intermediate sub-bases. Each sets
  its own stable `UPPER_SNAKE` `error_code`:

  | Leaf | `error_code` | Raised by |
  | --- | --- | --- |
  | `InvalidConfigError` | `INVALID_CONFIG` | config loading (any surface) |
  | `InvalidRubricError` | `INVALID_RUBRIC` | judge rubric parsing |
  | `JudgeOutputParseError` | `JUDGE_OUTPUT_PARSE` | judge (Tier-2) |
  | `MissingExtraError` | `MISSING_EXTRA` | a keyword needing `[mcp]`/`[llm]`/`[all]` |
  | `AdapterError` | `ADAPTER_ERROR` | the coding-agent driver (Tier-3) |
  | `TierViolationError` | `TIER_VIOLATION` | tier ACL gate |
  | `IncompleteTraceError` | `INCOMPLETE_TRACE` | MCP coverage gate |
  | `BudgetExceededError` | `BUDGET_EXCEEDED` | cost / runtime budgets |
  | `HookExecutionError` | `HOOK_EXECUTION` | HooksLibrary |
  | `SkillDidNotActivateError` | `SKILL_DID_NOT_ACTIVATE` | SkillsLibrary |
  | `SubagentDelegationError` | `SUBAGENT_DELEGATION` | SubagentsLibrary |
  | `MCPError` | `MCP_ERROR` | MCPLibrary |

- **Single import path:** `from AgentEval.errors import AgentEvalError, MCPError, ...`.

- **`error_code_to_exit_code(code)`** maps each leaf's code to a process exit code,
  with a documented fallback for unknown/`None`. Adding a leaf means adding its code
  and its exit-code mapping in the same file.

## Consequences

- `src/AgentEval/errors.py` is one file; the whole hierarchy lives in one place for
  grep-ability and documentation-ability.
- A documentation contract `docs/contracts/error-class-hierarchy.md` publishes the
  full error surface so contributors and consumers see it in one place.
- Programmatic catch is consistent: `try/except AgentEvalError` catches everything
  agenteval raises; catch a specific leaf when you want to react to just that case.

## Alternatives

- **Semantic sub-bases (Safety / Budget / Compat / Integrity family classes)** —
  proposed early, rejected in practice. The families never carried behavior, and a
  flat set of leaves off one base is simpler to read, catch, and map to exit codes.
- **Inherit from `RobotError`** — rejected. Couples agenteval to RF internals; breaks
  for plain-Python use of the four libraries outside a Robot run.
- **Per-library base classes (`MCPError`, `SkillError`, ...)** — rejected. More bases
  at the library boundary with no user-facing value; cross-cutting errors become
  awkward.
- **No structured `error_code` (just the class name)** — rejected. Class-name-as-type
  couples consumers to internal naming and breaks the failure-type surface every time
  a class is renamed.

## References

- `src/AgentEval/errors.py` — the one file this ADR governs.
- `docs/contracts/error-class-hierarchy.md` — the consumer-facing contract.
- ADR-008 (MCP Spec Version Validation) — raises `MCPError`.
- ADR-016 (MCP Coverage Detection) — raises `IncompleteTraceError`.
