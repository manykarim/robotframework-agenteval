"""Unit tests for _kernel/coverage.py (AC-1b.2.7)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from AgentEval._kernel.coverage import _check_mcp_coverage
from AgentEval.errors import AgentEvalError, AgentEvalIntegrityError, IncompleteTraceError

# ---- Story 1b.4 forward-reference fakes -------------------------------- #
# Story 1b.4 will land the real AgentRunResult in src/AgentEval/types.py.
# Until then, tests use these tiny SimpleNamespace / @dataclass stand-ins
# that match the `.metadata.mcp_coverage` attribute shape the kernel reads.


@dataclass
class _FakeMetadata:
    mcp_coverage: str
    observed_paths: tuple[str, ...] = ()


@dataclass
class _FakeRun:
    metadata: _FakeMetadata


# ---- AC-1b.2.7: 6-cell behavior matrix --------------------------------- #


def test_hosted_in_process_returns_none_default() -> None:
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="hosted_in_process"))
    assert _check_mcp_coverage(run) is None


def test_hosted_in_process_returns_none_with_allow_blind_true() -> None:
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="hosted_in_process"))
    assert _check_mcp_coverage(run, allow_external_mcp_blind=True) is None


def test_subprocess_with_observer_returns_none_default() -> None:
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="subprocess_with_observer"))
    assert _check_mcp_coverage(run) is None


def test_subprocess_with_observer_returns_none_with_allow_blind_true() -> None:
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="subprocess_with_observer"))
    assert _check_mcp_coverage(run, allow_external_mcp_blind=True) is None


def test_external_mixed_raises_incomplete_trace_error_default() -> None:
    """Per FR37 + ADR-016 L44: default-deny is the loud-refusal posture."""
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="external_mixed"))
    with pytest.raises(IncompleteTraceError) as exc_info:
        _check_mcp_coverage(run)
    # error_code attribute is on the class (and instance).
    assert exc_info.value.error_code == "INCOMPLETE_TRACE"
    # Message mentions the remediation path.
    assert "allow_external_mcp_blind=True" in str(exc_info.value)
    assert "mcp-coverage-detection.md" in str(exc_info.value)


def test_external_mixed_returns_none_with_allow_blind_true() -> None:
    """Opt-in blind run per ADR-016 §Decision L44."""
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="external_mixed"))
    assert _check_mcp_coverage(run, allow_external_mcp_blind=True) is None


# ---- AC-1b.2.7: trust-floor case (adapter populates resolved value) ---- #


def test_kernel_accepts_hosted_in_process_when_observed_paths_shows_both() -> None:
    """ADR-016 L17-28 trust-floor: when both paths fire, adapter populates
    `hosted_in_process` (stronger path wins). The kernel just reads the
    resolved value; it does NOT second-guess by inspecting observed_paths.
    """
    run = _FakeRun(
        metadata=_FakeMetadata(
            mcp_coverage="hosted_in_process",
            observed_paths=("hosted_in_process", "subprocess_with_observer"),
        )
    )
    # Kernel must NOT raise — accept the adapter's resolved value verbatim.
    assert _check_mcp_coverage(run) is None


# ---- AC-1b.2.7: duck-typed input (SimpleNamespace works too) ----------- #


def test_simplenamespace_input_works() -> None:
    """Phase-1 duck-typed runtime: any object with .metadata.mcp_coverage works."""
    run = SimpleNamespace(metadata=SimpleNamespace(mcp_coverage="external_mixed"))
    with pytest.raises(IncompleteTraceError):
        _check_mcp_coverage(run)


def test_raised_error_caught_via_base_class() -> None:
    """Consumers can catch via the broader AgentEvalError or AgentEvalIntegrityError."""
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="external_mixed"))
    with pytest.raises(AgentEvalIntegrityError):
        _check_mcp_coverage(run)
    with pytest.raises(AgentEvalError):
        _check_mcp_coverage(run)


# ---- Story 1b.2 code-review M_R1: unknown coverage values ---- #


def test_m_r1_unknown_coverage_value_raises_incomplete_trace_error() -> None:
    """M_R1: unknown mcp_coverage strings raise IncompleteTraceError (loud refusal)."""
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="bogus_value"))
    with pytest.raises(IncompleteTraceError) as exc_info:
        _check_mcp_coverage(run)
    assert "unknown mcp_coverage" in str(exc_info.value)
    assert "'bogus_value'" in str(exc_info.value)


def test_m_r1_unknown_coverage_value_raises_even_with_allow_blind() -> None:
    """M_R1: allow_external_mcp_blind=True does NOT bypass the unknown-value gate
    (that opt-out specifically targets the documented 'external_mixed' case).
    """
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage="typo_value"))
    with pytest.raises(IncompleteTraceError):
        _check_mcp_coverage(run, allow_external_mcp_blind=True)


def test_m_r1_empty_string_coverage_raises() -> None:
    """Empty string is not in the ratified 3-state set."""
    run = _FakeRun(metadata=_FakeMetadata(mcp_coverage=""))
    with pytest.raises(IncompleteTraceError, match="unknown mcp_coverage"):
        _check_mcp_coverage(run)
