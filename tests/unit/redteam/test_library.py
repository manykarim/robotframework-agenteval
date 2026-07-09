# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `RedTeamLibrary` keywords (add-red-team-probes tasks 5 + 7.3-7.5)."""

from __future__ import annotations

import pytest

from AgentEval._kernel import guardrails
from AgentEval.errors import CostExceededError
from AgentEval.redteam.library import RedTeamLibrary
from AgentEval.redteam.schema import AttackSuccessRate, ProbeResult

# --------------------------------------------------------------------------- #
# Run Probe — single (Tier-2 shape) + fan-out (Tier-3 shape)
# --------------------------------------------------------------------------- #


def test_run_probe_single_returns_one_structured_result(rt: RedTeamLibrary) -> None:
    result = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="pi-001")
    assert isinstance(result, ProbeResult)
    assert result.probe_id == "pi-001"
    assert result.category == "prompt_injection"
    assert result.severity
    assert result.adapter == "refusing-mock"
    assert result.refused is True
    assert result.refusal_strategy == "pattern"
    assert result.result.response_text == result.response_text


def test_run_probe_all_returns_list_for_category(rt: RedTeamLibrary) -> None:
    results = rt.run_probe(adapter="refusing-mock", category="jailbreak", probe="all")
    assert isinstance(results, list)
    assert len(results) == 6
    assert {r.category for r in results} == {"jailbreak"}


def test_run_probe_compliant_agent_records_non_refusal(rt: RedTeamLibrary) -> None:
    result = rt.run_probe(adapter="compliant-mock", category="prompt_injection", probe="pi-001")
    assert isinstance(result, ProbeResult)
    assert result.refused is False
    assert result.complied is True


def test_run_probe_unknown_category_raises(rt: RedTeamLibrary) -> None:
    with pytest.raises(ValueError, match="category"):
        rt.run_probe(adapter="refusing-mock", category="nope", probe="all")


def test_run_probe_unknown_probe_id_raises(rt: RedTeamLibrary) -> None:
    with pytest.raises(ValueError, match="unknown probe id"):
        rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="does-not-exist")


def test_run_probe_id_category_mismatch_raises(rt: RedTeamLibrary) -> None:
    # pi-001 is a prompt_injection probe, not jailbreak.
    with pytest.raises(ValueError, match="belongs to category"):
        rt.run_probe(adapter="refusing-mock", category="jailbreak", probe="pi-001")


def test_run_probe_unknown_adapter_raises(rt: RedTeamLibrary) -> None:
    from AgentEval.errors import AdapterDiscoveryError

    with pytest.raises(AdapterDiscoveryError):
        rt.run_probe(adapter="no_such_adapter", category="prompt_injection", probe="pi-001")


def test_run_probe_fanout_budget_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `probe=all` fan-out over budget is halted by the existing guardrail."""
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 5.0)
    rt = RedTeamLibrary()
    with pytest.raises(CostExceededError):
        rt.run_probe(
            adapter="refusing-mock",
            category="prompt_injection",
            probe="all",
            __agenteval_test_budget__=(0.01, None),
        )


def test_run_probe_within_budget_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock provider cost is 0.0 → a generous budget does not trip the meter."""
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 0.0)
    rt = RedTeamLibrary(max_cost_usd=5.0)
    results = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="all")
    assert len(results) == 6


def test_run_probe_enforces_max_cost_from_adapter_result_costs() -> None:
    """HIGH fix: an adapter reporting cost_usd=10/call must trip max_cost_usd=0.01.

    codex repro (NO_BUDGET_ERROR calls=6 total=60.0): the `@guarded_fanout`
    cost meter reads a 0.0 Phase-1 stub, so budget enforcement must accumulate
    the real `run_result.cost_usd` and raise `CostExceededError` explicitly.
    """
    rt = RedTeamLibrary(max_cost_usd=0.01)
    with pytest.raises(CostExceededError) as exc:
        rt.run_probe(adapter="costly-refusing-mock", category="prompt_injection", probe="all")
    # Breaches on the FIRST probe (10.0 > 0.01) — not after silently spending 60.0.
    assert "max_cost_usd" in str(exc.value)


def test_run_probe_no_budget_configured_does_not_enforce() -> None:
    """With max_cost_usd=None the explicit meter is inert (backwards-compatible)."""
    rt = RedTeamLibrary()  # no budget
    results = rt.run_probe(adapter="costly-refusing-mock", category="prompt_injection", probe="all")
    assert len(results) == 6


# --------------------------------------------------------------------------- #
# HIGH fix — mixed refusal-plus-compliance scored as compliance end-to-end
# --------------------------------------------------------------------------- #


def test_mixed_refusal_plus_marker_run_probe_is_compliance(rt: RedTeamLibrary) -> None:
    """pi-001 marker=PWNED: 'I can't help… PWNED' is compliance, not a refusal."""
    result = rt.run_probe(adapter="mixed-marker-mock", category="prompt_injection", probe="pi-001")
    assert isinstance(result, ProbeResult)
    assert result.refused is False
    assert result.complied is True
    # ...and it COUNTS toward ASR (attack success), not against it.
    asr = rt.get_attack_success_rate(result)
    assert asr.asr == 1.0
    assert asr.compliance_count == 1
    # Should Refuse must FAIL on this partial/contradictory compliance.
    with pytest.raises(AssertionError, match="COMPLIANCE"):
        rt.should_refuse(result)


# --------------------------------------------------------------------------- #
# Should Refuse
# --------------------------------------------------------------------------- #


def test_should_refuse_passes_on_refusal(rt: RedTeamLibrary) -> None:
    result = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="pi-001")
    rt.should_refuse(result)  # no raise


def test_should_refuse_fails_on_compliance(rt: RedTeamLibrary) -> None:
    result = rt.run_probe(adapter="compliant-mock", category="prompt_injection", probe="pi-001")
    with pytest.raises(AssertionError, match="COMPLIANCE"):
        rt.should_refuse(result)


def test_should_refuse_rejects_list_input(rt: RedTeamLibrary) -> None:
    results = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="all")
    with pytest.raises(ValueError, match="single ProbeResult"):
        rt.should_refuse(results)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Get Attack Success Rate — polarity (task 7.4)
# --------------------------------------------------------------------------- #


def test_asr_fully_refusing_agent_is_zero(rt: RedTeamLibrary) -> None:
    results = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="all")
    asr = rt.get_attack_success_rate(results)
    assert isinstance(asr, AttackSuccessRate)
    assert asr.asr == 0.0
    assert asr.compliance_count == 0
    assert asr.refusal_count == asr.n
    assert 0.0 <= asr.ci_lower <= asr.ci_upper <= 1.0


def test_asr_fully_complying_agent_is_one(rt: RedTeamLibrary) -> None:
    results = rt.run_probe(adapter="compliant-mock", category="prompt_injection", probe="all")
    asr = rt.get_attack_success_rate(results)
    assert asr.asr == 1.0
    assert asr.compliance_count == asr.n
    assert asr.ci_lower > 0.0  # CI populated + shifted toward 1.0


def test_asr_single_result_accepted(rt: RedTeamLibrary) -> None:
    result = rt.run_probe(adapter="compliant-mock", category="prompt_injection", probe="pi-001")
    asr = rt.get_attack_success_rate(result)
    assert asr.n == 1
    assert asr.asr == 1.0


def test_asr_empty_raises(rt: RedTeamLibrary) -> None:
    with pytest.raises(ValueError, match="zero probe results"):
        rt.get_attack_success_rate([])


# --------------------------------------------------------------------------- #
# Attack Success Rate Should Be Below (task 7.5)
# --------------------------------------------------------------------------- #


def test_asr_below_threshold_passes(rt: RedTeamLibrary) -> None:
    results = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="all")
    rt.attack_success_rate_should_be_below(results, threshold=0.05)  # ASR=0.0 < 0.05


def test_asr_at_or_above_threshold_fails_with_detail(rt: RedTeamLibrary) -> None:
    results = rt.run_probe(adapter="compliant-mock", category="prompt_injection", probe="all")
    with pytest.raises(AssertionError) as exc:
        rt.attack_success_rate_should_be_below(results, threshold=0.05)
    msg = str(exc.value)
    assert "1.0000" in msg  # observed ASR
    assert "0.0500" in msg  # threshold
    assert "CI" in msg  # confidence interval reported


def test_asr_strict_comparison_zero_threshold(rt: RedTeamLibrary) -> None:
    """threshold=0.0 demands a perfectly-refusing agent (strict `<`)."""
    results = rt.run_probe(adapter="refusing-mock", category="prompt_injection", probe="all")
    with pytest.raises(AssertionError):
        rt.attack_success_rate_should_be_below(results, threshold=0.0)
