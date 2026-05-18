"""Unit tests for src/AgentEval/errors.py (AC-1b.2.6)."""

from __future__ import annotations

import pytest

from AgentEval.errors import AgentEvalError, AgentEvalIntegrityError, IncompleteTraceError


def test_agenteval_error_is_exception_base() -> None:
    """AgentEvalError is the common base for all agenteval-raised errors."""
    assert issubclass(AgentEvalError, Exception)
    # Empty default error_code on the base — leaves MUST override.
    assert AgentEvalError.error_code == ""


def test_agenteval_integrity_error_is_subclass_of_base() -> None:
    """Per ADR-014's 4-sub-base scheme; integrity is one of the 4."""
    assert issubclass(AgentEvalIntegrityError, AgentEvalError)


def test_incomplete_trace_error_class_hierarchy() -> None:
    """IncompleteTraceError inherits AgentEvalIntegrityError inherits AgentEvalError."""
    assert issubclass(IncompleteTraceError, AgentEvalIntegrityError)
    assert issubclass(IncompleteTraceError, AgentEvalError)
    assert issubclass(IncompleteTraceError, Exception)


def test_incomplete_trace_error_code_is_class_attribute() -> None:
    """`error_code` is a ClassVar (not instance attribute)."""
    assert IncompleteTraceError.error_code == "INCOMPLETE_TRACE"
    instance = IncompleteTraceError("test")
    assert instance.error_code == "INCOMPLETE_TRACE"


def test_incomplete_trace_error_str_format_per_h_r7() -> None:
    """H_R7 fix (Story 1b.2 code review): __str__ renders 'error_code: message'
    so FR49 JUnit XML emission + FR50 exit-code mapping can pull the prefix
    from str(exc) directly.
    """
    e = IncompleteTraceError("specific message")
    assert str(e) == "INCOMPLETE_TRACE: specific message"


def test_agenteval_error_base_str_no_prefix() -> None:
    """Bare AgentEvalError (no error_code) returns bare message — no prefix."""
    e = AgentEvalError("raw message")
    assert str(e) == "raw message"


def test_no_leaf_inherits_directly_from_agenteval_error() -> None:
    """Per ADR-014's sub-base scheme: leaves go through a sub-base, never the bare base.

    This convention test catches refactor regressions where a future story
    might accidentally hang a new leaf directly off AgentEvalError instead
    of one of the 4 sub-bases.
    """
    # IncompleteTraceError's direct parent is AgentEvalIntegrityError (NOT
    # AgentEvalError). __mro__[1] is the direct parent.
    assert IncompleteTraceError.__mro__[1] is AgentEvalIntegrityError


def test_catching_base_class_catches_leaf() -> None:
    """Consumers can `try / except AgentEvalError` to catch all agenteval errors."""
    with pytest.raises(AgentEvalError):
        raise IncompleteTraceError("test")
    with pytest.raises(AgentEvalIntegrityError):
        raise IncompleteTraceError("test")


# ---- H_R4 fix: DegradedTraceWarning class ------------------------------ #


def test_degraded_trace_warning_inherits_user_warning() -> None:
    """DegradedTraceWarning is a Python Warning (NOT an AgentEvalError) per architecture L997."""
    from AgentEval.errors import DegradedTraceWarning

    assert issubclass(DegradedTraceWarning, UserWarning)
    assert issubclass(DegradedTraceWarning, Warning)
    # Distinct from the AgentEvalError hierarchy.
    assert not issubclass(DegradedTraceWarning, AgentEvalError)


def test_degraded_trace_warning_emits_via_warnings_warn() -> None:
    """DegradedTraceWarning integrates with the Python warnings module."""
    import warnings

    from AgentEval.errors import DegradedTraceWarning

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn("test", DegradedTraceWarning, stacklevel=2)
    assert len(caught) == 1
    assert issubclass(caught[0].category, DegradedTraceWarning)
