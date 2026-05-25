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

"""Unit tests for FR54 terminal run summary (Story 8b.2 AC-8b.2.8)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from AgentEval.telemetry import listener as listener_module
from AgentEval.telemetry._terminal_summary import render_summary
from AgentEval.telemetry.listener import Listener


def test_render_summary_with_metadata() -> None:
    """Basic shape: total / cost / latency p95 / warnings count + top errors."""
    metadata = {
        "Suite.T1": {
            "cost_usd": 0.10,
            "latency_seconds": 1.5,
            "warnings": "[DegradedTraceWarning] missing longname",
        },
        "Suite.T2": {
            "cost_usd": 0.05,
            "latency_seconds": 2.0,
            "warnings": None,
        },
    }
    summary = render_summary(completed_run_metadata=metadata)
    assert "Tests:" in summary
    assert "2 total" in summary
    assert "$0.15" in summary
    assert "p95" in summary
    assert "Warnings: 1" in summary
    assert "DegradedTraceWarning" in summary


def test_end_suite_writes_summary_when_env_var_set(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8b.2.8 #1: `end_suite` writes summary to stdout when AGENTEVAL_TERMINAL_SUMMARY=1."""
    monkeypatch.setenv("AGENTEVAL_TERMINAL_SUMMARY", "1")
    listener_module._active_listeners.clear()
    listener = Listener()
    listener._completed_run_metadata["Suite.T1"] = {
        "cost_usd": 0.20,
        "latency_seconds": 1.0,
    }
    # Top-level suite (no parent) triggers the summary.
    data = SimpleNamespace(parent=None, full_name="Suite")
    listener.end_suite(data, SimpleNamespace(passed=True))
    captured = capsys.readouterr()
    assert "agenteval run summary" in captured.out
    assert "$0.20" in captured.out


def test_end_suite_silent_when_env_var_unset(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8b.2.8 #2: no summary written when env var unset."""
    monkeypatch.delenv("AGENTEVAL_TERMINAL_SUMMARY", raising=False)
    listener_module._active_listeners.clear()
    listener = Listener()
    listener._completed_run_metadata["Suite.T1"] = {"cost_usd": 0.20}
    data = SimpleNamespace(parent=None, full_name="Suite")
    listener.end_suite(data, SimpleNamespace(passed=True))
    assert "agenteval run summary" not in capsys.readouterr().out


def test_end_suite_failure_logged_not_raised(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-8b.2.8 #3: failure during summary computation is logged at WARN + does NOT raise."""
    import logging

    monkeypatch.setenv("AGENTEVAL_TERMINAL_SUMMARY", "1")

    def _boom(**kwargs: Any) -> str:
        raise RuntimeError("simulated render failure")

    monkeypatch.setattr("AgentEval.telemetry._terminal_summary.render_summary", _boom)
    listener_module._active_listeners.clear()
    listener = Listener()
    data = SimpleNamespace(parent=None, full_name="Suite")
    with caplog.at_level(logging.WARNING, logger="AgentEval.telemetry.listener"):
        listener.end_suite(data, SimpleNamespace(passed=True))
    assert any("terminal summary render failed" in record.message for record in caplog.records)


def test_nested_suite_does_not_emit_summary(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bonus: nested suites (data.parent is not None) do NOT trigger the summary."""
    monkeypatch.setenv("AGENTEVAL_TERMINAL_SUMMARY", "1")
    listener_module._active_listeners.clear()
    listener = Listener()
    listener._completed_run_metadata["Outer.Inner.T1"] = {"cost_usd": 0.10}
    nested_data = SimpleNamespace(parent=SimpleNamespace(full_name="Outer"), full_name="Outer.Inner")
    listener.end_suite(nested_data, SimpleNamespace(passed=True))
    assert "agenteval run summary" not in capsys.readouterr().out
