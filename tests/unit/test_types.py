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
