"""Unit tests for src/AgentEval/types.py (AC-1b.2.3)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict
from datetime import UTC, datetime

import pytest

from AgentEval.types import RunManifest, ToolCallTrace, Usage

# ---- ToolCallTrace ------------------------------------------------------ #


def test_toolcalltrace_construction_and_fields() -> None:
    tct = ToolCallTrace(
        name="bash",
        args={"command": "ls"},
        result="file1\nfile2",
        error=None,
        latency_ms=12.5,
        source="adapter",
        gen_ai_tool_call_id="call-abc",
        sequence_index=0,
    )
    assert tct.name == "bash"
    assert tct.args == {"command": "ls"}
    assert tct.result == "file1\nfile2"
    assert tct.error is None
    assert tct.latency_ms == 12.5
    assert tct.source == "adapter"
    assert tct.gen_ai_tool_call_id == "call-abc"


def test_toolcalltrace_is_frozen() -> None:
    tct = ToolCallTrace(
        name="bash",
        args={},
        result=None,
        error=None,
        latency_ms=0.0,
        source="hosted_mcp",
        gen_ai_tool_call_id="x",
        sequence_index=0,
    )
    with pytest.raises(FrozenInstanceError):
        tct.name = "modified"  # type: ignore[misc]


def test_toolcalltrace_asdict_round_trip() -> None:
    tct = ToolCallTrace(
        name="grep",
        args={"pattern": "foo", "files": ["a.py", "b.py"]},
        result={"matches": 3},
        error=None,
        latency_ms=42.0,
        source="adapter",
        gen_ai_tool_call_id="call-xyz",
        sequence_index=5,
    )
    d = asdict(tct)
    assert d["name"] == "grep"
    assert d["args"] == {"pattern": "foo", "files": ["a.py", "b.py"]}
    assert d["source"] == "adapter"


# ---- Usage -------------------------------------------------------------- #


def test_usage_construction_with_default_cached() -> None:
    u = Usage(input_tokens=100, output_tokens=50)
    assert u.input_tokens == 100
    assert u.output_tokens == 50
    assert u.cached_input_tokens == 0  # default


def test_usage_construction_with_explicit_cached() -> None:
    u = Usage(input_tokens=100, output_tokens=50, cached_input_tokens=30)
    assert u.cached_input_tokens == 30


def test_usage_is_frozen() -> None:
    u = Usage(input_tokens=0, output_tokens=0)
    with pytest.raises(FrozenInstanceError):
        u.input_tokens = 999  # type: ignore[misc]


# ---- RunManifest -------------------------------------------------------- #


def test_runmanifest_construction_and_fields() -> None:
    started = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    ended = datetime(2026, 5, 18, 12, 0, 5, tzinfo=UTC)
    rm = RunManifest(
        library_version="0.0.1",
        test_id="t1",
        suite_id="s1",
        redaction_policy_hash="abc123",
        started_at=started,
        ended_at=ended,
        agenteval_tier_breakdown={1: 5, 2: 2, 3: 1},
    )
    assert rm.library_version == "0.0.1"
    assert rm.test_id == "t1"
    assert rm.suite_id == "s1"
    assert rm.redaction_policy_hash == "abc123"
    assert rm.started_at == started
    assert rm.ended_at == ended
    assert rm.agenteval_tier_breakdown == {1: 5, 2: 2, 3: 1}


def test_runmanifest_tier_breakdown_default_empty() -> None:
    started = datetime(2026, 5, 18, tzinfo=UTC)
    rm = RunManifest(
        library_version="0.0.1",
        test_id="t",
        suite_id="s",
        redaction_policy_hash="h",
        started_at=started,
        ended_at=started,
    )
    assert dict(rm.agenteval_tier_breakdown) == {}


def test_runmanifest_is_frozen() -> None:
    started = datetime(2026, 5, 18, tzinfo=UTC)
    rm = RunManifest(
        library_version="0.0.1",
        test_id="t",
        suite_id="s",
        redaction_policy_hash="h",
        started_at=started,
        ended_at=started,
    )
    with pytest.raises(FrozenInstanceError):
        rm.library_version = "999"  # type: ignore[misc]


# ---- Story 1b.2 code-review patches: new test coverage ---------------- #


def test_toolcalltrace_sequence_index_field_h_r6() -> None:
    """H_R6 fix: sequence_index field per PRD FR35 + FR45(d) conformance."""
    tct = ToolCallTrace(
        name="bash",
        args={"cmd": "ls"},
        result="ok",
        error=None,
        latency_ms=1.0,
        source="adapter",
        gen_ai_tool_call_id="x",
        sequence_index=42,
    )
    assert tct.sequence_index == 42


def test_toolcalltrace_args_defensive_freeze_m_r6() -> None:
    """M_R6: caller mutations to the source dict must NOT leak through frozen=True."""
    source = {"command": "ls"}
    tct = ToolCallTrace(
        name="bash",
        args=source,
        result=None,
        error=None,
        latency_ms=0.0,
        source="adapter",
        gen_ai_tool_call_id="x",
        sequence_index=0,
    )
    source["command"] = "MUTATED"
    assert dict(tct.args) == {"command": "ls"}, "args leaked through Mapping view"


def test_runmanifest_tier_breakdown_defensive_freeze_m_r6() -> None:
    """M_R6: caller mutations to the source dict must NOT leak through frozen=True."""
    from datetime import UTC
    from datetime import datetime as _dt

    source: dict[int, int] = {1: 5, 2: 2}
    started = _dt(2026, 5, 18, tzinfo=UTC)
    rm = RunManifest(
        library_version="0.0.1",
        test_id="t",
        suite_id="s",
        redaction_policy_hash="h",
        started_at=started,
        ended_at=started,
        agenteval_tier_breakdown=source,
    )
    source[1] = 999
    assert dict(rm.agenteval_tier_breakdown) == {1: 5, 2: 2}, "tier_breakdown leaked"


def test_usage_rejects_negative_input_tokens_m_r11() -> None:
    """M_R11: non-negative validation per docstring contract."""
    with pytest.raises(ValueError, match="input_tokens.*non-negative"):
        Usage(input_tokens=-1, output_tokens=0)


def test_usage_rejects_negative_output_tokens_m_r11() -> None:
    with pytest.raises(ValueError, match="output_tokens.*non-negative"):
        Usage(input_tokens=0, output_tokens=-5)


def test_usage_rejects_negative_cached_tokens_m_r11() -> None:
    with pytest.raises(ValueError, match="cached_input_tokens.*non-negative"):
        Usage(input_tokens=0, output_tokens=0, cached_input_tokens=-1)
