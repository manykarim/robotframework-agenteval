"""Conventions test: every `errors.py` `__all__` export inherits from `AgentEvalError`.

Story 1b.6 AC-1b.6.3 per ADR-014 4-sub-base scheme + architecture L997
DegradedTraceWarning exemption. End-of-Epic-1b verifies all currently-
implemented sub-bases + leaves conform; future stories adding new error
classes must place them under one of the 4 sub-bases (`AgentEvalIntegrityError`,
`AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalSafetyError`).
"""

from __future__ import annotations

import AgentEval.errors as errors_mod
from AgentEval.errors import AgentEvalError, DegradedTraceWarning


def test_every_errors_all_export_inherits_from_agenteval_error() -> None:
    """`__all__` exports MUST inherit from `AgentEvalError`, except known warnings."""
    # Per architecture L997: DegradedTraceWarning is a UserWarning, NOT an
    # AgentEvalError; it's a Python `warnings.warn`-emitting class for
    # recoverable-but-incomplete traces (Story 1b.2 H_R4 fix).
    warning_exceptions = {"DegradedTraceWarning"}

    violations: list[str] = []
    for name in errors_mod.__all__:
        if name in warning_exceptions:
            # Known-non-Error: verify it is in fact a Warning subclass.
            cls = getattr(errors_mod, name)
            assert issubclass(cls, Warning), f"Known-non-Error {name!r} expected to be a Warning subclass; got {cls!r}"
            continue
        cls = getattr(errors_mod, name)
        if not (isinstance(cls, type) and issubclass(cls, AgentEvalError)):
            violations.append(name)
    assert not violations, (
        f"Errors module __all__ entries that do NOT inherit AgentEvalError "
        f"(per ADR-014 4-sub-base scheme): {violations!r}. "
        f"Excludes known warning class: {warning_exceptions!r}."
    )


def test_no_leaf_inherits_directly_from_base() -> None:
    """Per ADR-014: leaves go through one of the 4 sub-bases, never the bare base."""
    # The 4 ratified sub-bases per ADR-014. Story 1b.2 ships Integrity;
    # Story 1b.3 adds Budget + Compat; Safety lands in a future story.
    sub_base_names = {
        "AgentEvalIntegrityError",
        "AgentEvalBudgetError",
        "AgentEvalCompatError",
        "AgentEvalSafetyError",
    }
    base = AgentEvalError
    violations: list[str] = []
    for name in errors_mod.__all__:
        if name == "AgentEvalError":
            continue
        if name in sub_base_names:
            continue
        if name == DegradedTraceWarning.__name__:
            continue
        cls = getattr(errors_mod, name)
        if not (isinstance(cls, type) and issubclass(cls, AgentEvalError)):
            continue
        # Walk MRO; the FIRST AgentEvalError-subclass ancestor MUST be a sub-base.
        for parent in cls.__mro__[1:]:
            if parent is base:
                violations.append(f"{name!r} inherits directly from AgentEvalError; must go through a sub-base")
                break
            if parent.__name__ in sub_base_names:
                break
            if parent is object:
                break
    assert not violations, "\n".join(violations)
