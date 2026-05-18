"""Unit tests for _kernel/guardrails.py (AC-1b.3.3, AC-1b.3.4, AC-1b.3.5, AC-1b.3.6)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from AgentEval._kernel import guardrails
from AgentEval._kernel.guardrails import current_cancel_event, guarded_fanout
from AgentEval._kernel.run_async import _run_async
from AgentEval.errors import CostExceededError, RuntimeBudgetExceededError


class _FakeAgent:
    """Minimal stand-in for AgentEval instance — exposes the budget attrs the decorator reads."""

    def __init__(self, max_cost_usd: float = 5.0, max_runtime_seconds: float | None = None) -> None:
        self._max_cost_usd = max_cost_usd
        self._max_runtime_seconds = max_runtime_seconds


# ============================================================ #
# AC-1b.3.3: Layer 1 pre-flight estimation                    #
# ============================================================ #


def test_l1_pre_flight_cost_estimate_raises() -> None:
    """Pre-flight cost > budget → CostExceededError, body never runs."""
    body_ran = []

    @guarded_fanout(estimator=lambda kwargs: (10.0, 0.1))
    def run(self: Any) -> str:
        body_ran.append(True)
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    with pytest.raises(CostExceededError) as exc_info:
        run(agent)
    assert body_ran == []
    assert "10.00 USD" in str(exc_info.value)
    assert "5.00 USD" in str(exc_info.value)
    assert exc_info.value.error_code == "COST_EXCEEDED"


def test_l1_pre_flight_runtime_estimate_raises() -> None:
    """Pre-flight runtime > budget → RuntimeBudgetExceededError, body never runs."""

    @guarded_fanout(estimator=lambda kwargs: (0.1, 120.0))
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0, max_runtime_seconds=60.0)
    with pytest.raises(RuntimeBudgetExceededError) as exc_info:
        run(agent)
    assert "120.0s" in str(exc_info.value)
    assert "60.0s" in str(exc_info.value)


def test_l1_pre_flight_runtime_with_none_budget_skips() -> None:
    """max_runtime_seconds=None → Layer 1 runtime check skipped (per FR11b default)."""

    @guarded_fanout(estimator=lambda kwargs: (0.1, 9999.0))
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0, max_runtime_seconds=None)
    assert run(agent) == "ok"


def test_l1_estimator_none_skips_pre_flight() -> None:
    """estimator=None → Layer 1 skipped entirely."""

    @guarded_fanout(estimator=None)
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent(max_cost_usd=0.0)  # would have failed Layer 1 if estimator provided
    assert run(agent) == "ok"


def test_l1_estimator_at_exactly_budget_does_not_raise() -> None:
    """Pre-flight estimate == budget passes (raise is on >, not >=)."""

    @guarded_fanout(estimator=lambda kwargs: (5.0, 60.0))
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0, max_runtime_seconds=60.0)
    assert run(agent) == "ok"


# ============================================================ #
# AC-1b.3.4: Layer 2 mid-run cost meter                       #
# ============================================================ #


def test_l2_mid_run_cost_meter_raises_on_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkey-patch _current_cost_usd_for_run to simulate cost accumulating
    past the budget; Layer 2 poller should fire CostExceededError.
    """
    # Cost source returns 10.0 (above the 5.0 budget) — Layer 2 detects on first poll.
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 10.0)

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def slow_run(self: Any) -> str:
        time.sleep(0.05)  # give the meter thread a chance to poll
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    with pytest.raises(CostExceededError) as exc_info:
        slow_run(agent)
    assert "Mid-run cost" in str(exc_info.value)
    assert "10.00 USD" in str(exc_info.value)
    assert exc_info.value.error_code == "COST_EXCEEDED"


def test_l2_cost_meter_silent_when_below_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase-1 stub returns 0.0 → Layer 2 never fires; keyword body completes normally."""
    # default _current_cost_usd_for_run already returns 0.0 — explicit for clarity.
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 0.0)

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def quick_run(self: Any) -> str:
        time.sleep(0.05)
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    assert quick_run(agent) == "ok"


# ============================================================ #
# AC-1b.3.5: Layer 3 mid-run wall-clock meter                 #
# ============================================================ #


def test_l3_wall_clock_meter_raises_at_exactly_budget() -> None:
    """Layer 3 raises at EXACTLY the budget (not 1.1×)."""

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def slow_run(self: Any) -> str:
        time.sleep(0.3)  # exceed the 0.1s budget
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0, max_runtime_seconds=0.1)
    with pytest.raises(RuntimeBudgetExceededError) as exc_info:
        slow_run(agent)
    assert "Mid-run wall-clock" in str(exc_info.value)
    # The breach time should be ~0.1s, NOT 0.11s (1.1×).
    assert "0.1s" in str(exc_info.value)


def test_l3_silent_when_max_runtime_is_none() -> None:
    """max_runtime_seconds=None → Layer 3 silent; even slow runs complete."""

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def slow_run(self: Any) -> str:
        time.sleep(0.05)
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0, max_runtime_seconds=None)
    assert slow_run(agent) == "ok"


# ============================================================ #
# AC-1b.3.6: Cooperative cancellation hook + _run_async       #
# ============================================================ #


def test_current_cancel_event_returns_none_outside_decorator() -> None:
    """Outside a decorated frame, accessor returns None (no crash)."""
    assert current_cancel_event() is None


def test_current_cancel_event_returns_event_inside_decorator() -> None:
    """Inside the decorated body, the accessor returns the bound Event."""
    observed = []

    @guarded_fanout(estimator=None, meter_interval_seconds=10.0)
    def run(self: Any) -> str:
        observed.append(current_cancel_event())
        return "ok"

    agent = _FakeAgent()
    run(agent)
    assert observed[0] is not None  # an Event was bound
    assert hasattr(observed[0], "is_set")


def test_cancel_event_propagates_through_run_async() -> None:
    """Story 1b.1 integration: _run_async's copy_context propagates the
    cancellation event into worker-thread coroutines.
    """
    observed = []

    async def inner_coro() -> None:
        observed.append(current_cancel_event())

    @guarded_fanout(estimator=None, meter_interval_seconds=10.0)
    def run(self: Any) -> str:
        # Trigger _run_async's nested-loop fallback by calling from inside a running loop.
        async def outer() -> None:
            _run_async(inner_coro())

        asyncio.run(outer())
        return "ok"

    agent = _FakeAgent()
    run(agent)
    # Inside the worker-thread coroutine, the cancellation event MUST still be visible.
    assert observed[0] is not None


def test_l2_cost_breach_sets_cancel_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer 2 breach → cancel_event.is_set() goes True before raise."""
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 100.0)
    observed_events = []

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def run(self: Any) -> str:
        ev = current_cancel_event()
        observed_events.append(ev)
        # Poll until cancellation fires or 200ms elapse.
        for _ in range(40):
            if ev is not None and ev.is_set():
                break
            time.sleep(0.01)
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    with pytest.raises(CostExceededError):
        run(agent)
    assert observed_events[0] is not None
    assert observed_events[0].is_set()  # cancellation fired during the body


# ============================================================ #
# Test-only _budget kwarg override                            #
# ============================================================ #


def test_budget_kwarg_override_for_test_fixtures() -> None:
    """Tests can override the instance budget via the _budget kwarg-only param."""

    @guarded_fanout(estimator=lambda kwargs: (1.0, 0.1))
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    # Override with a tighter budget: 0.5 < 1.0 → expect CostExceededError.
    with pytest.raises(CostExceededError):
        run(agent, _budget=(0.5, 1.0))
    # Override with looser budget that the estimator can satisfy.
    assert run(agent, _budget=(2.0, 1.0)) == "ok"


# ============================================================ #
# meter_interval_seconds parameter                            #
# ============================================================ #


def test_meter_interval_seconds_respected() -> None:
    """A long meter_interval means the meter doesn't fire during a short body."""
    monkeypatch_count = [0]

    def slow_cost() -> float:
        monkeypatch_count[0] += 1
        return 0.0

    # Patch the module attribute directly (no pytest monkeypatch fixture in this test).
    original = guardrails._current_cost_usd_for_run
    guardrails._current_cost_usd_for_run = slow_cost
    try:

        @guarded_fanout(estimator=None, meter_interval_seconds=10.0)
        def quick(self: Any) -> str:
            time.sleep(0.02)
            return "ok"

        agent = _FakeAgent()
        assert quick(agent) == "ok"
        # With a 10s meter interval and a 0.02s body, the meter thread polls 0 times.
        assert monkeypatch_count[0] == 0
    finally:
        guardrails._current_cost_usd_for_run = original
