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


def test_incomplete_trace_error_message_round_trip() -> None:
    """Standard Exception message round-trip works."""
    e = IncompleteTraceError("specific message")
    assert str(e) == "specific message"


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
