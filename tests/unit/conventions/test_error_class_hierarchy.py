"""Conventions test: every `errors.py` `__all__` export inherits from `AgentEvalError`.

Story 1b.6 AC-1b.6.3 per ADR-014 4-sub-base scheme + architecture L997
DegradedTraceWarning exemption. End-of-Epic-1b verifies all currently-
implemented sub-bases + leaves conform; future stories adding new error
classes must place them under one of the 4 sub-bases (`AgentEvalIntegrityError`,
`AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalSafetyError`).
"""

from __future__ import annotations

import AgentEval.errors as errors_mod
from AgentEval.errors import AgentEvalError


def test_every_errors_all_export_inherits_from_agenteval_error() -> None:
    """`__all__` exports MUST inherit from `AgentEvalError`, except `Warning` subclasses.

    Story 1b.6 code-review Codex MED + Edge fix: dynamically detect Warning
    subclasses instead of hardcoding `{"DegradedTraceWarning"}` — per
    `docs/contracts/error-class-hierarchy.md` L83 `AdapterVersionDriftWarning`
    is the already-ratified second warning class that future stories will
    export, and other future warnings (e.g., recovery-warning patterns from
    Epic 5) should not require a hardcoded allowlist update.
    """
    violations: list[str] = []
    for name in errors_mod.__all__:
        cls = getattr(errors_mod, name, None)
        if cls is None:
            violations.append(f"{name!r} in __all__ but not defined on the module")
            continue
        if not isinstance(cls, type):
            violations.append(f"{name!r} in __all__ is not a class: {cls!r}")
            continue
        # Dynamic Warning-detection: Warning subclasses are exempt from the
        # AgentEvalError requirement (per architecture L997 DegradedTraceWarning
        # precedent; extends to AdapterVersionDriftWarning per contract L83).
        if issubclass(cls, Warning):
            continue
        if not issubclass(cls, AgentEvalError):
            violations.append(name)
    assert not violations, (
        f"Errors module __all__ entries that do NOT inherit AgentEvalError "
        f"(per ADR-014 4-sub-base scheme; Warning subclasses are exempt): {violations!r}."
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
        cls_probe = getattr(errors_mod, name, None)
        if cls_probe is not None and isinstance(cls_probe, type) and issubclass(cls_probe, Warning):
            # Dynamic Warning-detection per Codex MED fix; future Warning
            # subclasses (e.g., AdapterVersionDriftWarning per contract L83)
            # are exempt without hardcoded allowlist updates.
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
