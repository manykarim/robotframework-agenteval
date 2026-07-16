# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Errors for the four surfaces and the spine.

One base, ``AgentEvalError``, so callers can ``except AgentEvalError`` and catch
everything the library throws. Every leaf carries a stable ``error_code`` that
prefixes its string form and maps to a CLI exit code via ``EXIT_CODES``.

Keep this list short. The whole point of the spine is that twelve well-chosen
leaves cover every surface; resist adding a leaf per keyword.
"""

from __future__ import annotations

from typing import ClassVar

__all__ = [
    "AgentEvalError",
    "InvalidConfigError",
    "InvalidRubricError",
    "JudgeOutputParseError",
    "MissingExtraError",
    "AdapterError",
    "TierViolationError",
    "IncompleteTraceError",
    "BudgetExceededError",
    "HookExecutionError",
    "SkillDidNotActivateError",
    "SubagentDelegationError",
    "MCPError",
    "EXIT_CODES",
    "EXIT_CODE_FALLBACK",
    "error_code_to_exit_code",
]


class AgentEvalError(Exception):
    """Base class for every error the library raises.

    Leaves set ``error_code`` to a stable ``UPPER_SNAKE`` string. When present,
    it prefixes ``str(exc)`` so logs and the CLI exit-code mapper can read the
    code straight off the message.
    """

    error_code: ClassVar[str] = ""

    def __str__(self) -> str:
        message = super().__str__()
        if self.error_code:
            return f"{self.error_code}: {message}"
        return message


class InvalidConfigError(AgentEvalError):
    """A config file (hooks, MCP, skill, subagent, scenario) failed to parse or validate.

    Optional ``file_path`` / ``field`` / ``fix`` context is stored for callers
    that want to point the user at the exact problem.
    """

    error_code: ClassVar[str] = "INVALID_CONFIG"

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        field: str | None = None,
        fix: str | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.field = field
        self.fix = fix


class InvalidRubricError(AgentEvalError):
    """A judge rubric could not be parsed (missing section, bad bullet, bad threshold)."""

    error_code: ClassVar[str] = "INVALID_RUBRIC"

    def __init__(
        self,
        message: str,
        *,
        source: str | None = None,
        field: str | None = None,
        fix: str | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.field = field
        self.fix = fix


class JudgeOutputParseError(AgentEvalError):
    """The judge LLM returned something that is not a valid score object."""

    error_code: ClassVar[str] = "JUDGE_OUTPUT_PARSE"

    def __init__(self, message: str, *, raw_response: str = "", fix: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.fix = fix


class MissingExtraError(AgentEvalError):
    """A keyword needs an optional dependency that is not installed.

    ``extra`` names the pip extra to install (e.g. ``llm`` or ``mcp``).
    """

    error_code: ClassVar[str] = "MISSING_EXTRA"

    def __init__(self, message: str, *, extra: str) -> None:
        super().__init__(message)
        self.extra = extra


class AdapterError(AgentEvalError):
    """No adapter could be resolved, or a resolved adapter misbehaved."""

    error_code: ClassVar[str] = "ADAPTER_ERROR"


class TierViolationError(AgentEvalError):
    """A Tier-1 keyword tried to do something stochastic (call a model or agent)."""

    error_code: ClassVar[str] = "TIER_VIOLATION"


class IncompleteTraceError(AgentEvalError):
    """A run's trace coverage is too thin to make a reliable assertion."""

    error_code: ClassVar[str] = "INCOMPLETE_TRACE"


class BudgetExceededError(AgentEvalError):
    """A run blew past its configured cost or runtime budget."""

    error_code: ClassVar[str] = "BUDGET_EXCEEDED"


class HookExecutionError(AgentEvalError):
    """A hook keyword was misused, or an event matched zero configured hooks."""

    error_code: ClassVar[str] = "HOOK_EXECUTION"


class SkillDidNotActivateError(AgentEvalError):
    """A skill was expected to activate for a prompt but did not."""

    error_code: ClassVar[str] = "SKILL_DID_NOT_ACTIVATE"


class SubagentDelegationError(AgentEvalError):
    """A subagent delegation assertion failed (wrong target, or none at all)."""

    error_code: ClassVar[str] = "SUBAGENT_DELEGATION"


class MCPError(AgentEvalError):
    """A live MCP server operation failed (bad handshake, lost connection)."""

    error_code: ClassVar[str] = "MCP_ERROR"


# --------------------------------------------------------------------------- #
# CLI exit-code table - one entry per leaf, kept in sync by test.              #
# --------------------------------------------------------------------------- #

# Sysexits-style fallback (EX_SOFTWARE) for unknown / empty codes.
EXIT_CODE_FALLBACK = 70

# Every leaf's error_code maps to a process exit code. The unit test asserts
# this dict has exactly the set of leaf error codes - so a new leaf that
# forgets its exit code fails CI rather than silently mapping to the fallback.
EXIT_CODES: dict[str, int] = {
    "INVALID_CONFIG": 65,  # EX_DATAERR
    "INVALID_RUBRIC": 65,  # EX_DATAERR
    "JUDGE_OUTPUT_PARSE": 65,  # EX_DATAERR
    "HOOK_EXECUTION": 65,  # EX_DATAERR
    "MISSING_EXTRA": 78,  # EX_CONFIG
    "ADAPTER_ERROR": 78,  # EX_CONFIG
    "TIER_VIOLATION": 70,  # EX_SOFTWARE
    "SKILL_DID_NOT_ACTIVATE": 70,  # EX_SOFTWARE
    "SUBAGENT_DELEGATION": 70,  # EX_SOFTWARE
    "INCOMPLETE_TRACE": 67,  # trace-integrity
    "BUDGET_EXCEEDED": 66,  # budget breach
    "MCP_ERROR": 69,  # transport failure
}


def error_code_to_exit_code(error_code: str | None) -> int:
    """Map a leaf ``error_code`` to a CLI exit code; fallback for unknown/None."""
    if not error_code:
        return EXIT_CODE_FALLBACK
    return EXIT_CODES.get(error_code, EXIT_CODE_FALLBACK)
