"""Unit tests for _kernel/guardrails.py (AC-1b.3.3, AC-1b.3.4, AC-1b.3.5, AC-1b.3.6)."""

from __future__ import annotations

import asyncio
import threading
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


def test_l3_wall_clock_meter_raises_after_budget_polling_tick() -> None:
    """Layer 3 raises on the NEXT polling tick after the budget is exceeded.

    Story 1b.3 code-review fix (D2): the pre-edit name + comment claimed
    'EXACTLY the budget' which is unachievable with a polling loop. The
    breach surfaces within `[budget, budget + meter_interval_seconds]`. This
    test asserts the numeric breach time is in that window rather than
    substring-matching `'0.1s'` (which also matches `'0.0s'`, `'0.11s'`, etc.).
    """

    @guarded_fanout(estimator=None, meter_interval_seconds=0.02)
    def slow_run(self: Any) -> str:
        time.sleep(0.3)  # exceed the 0.1s budget
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0, max_runtime_seconds=0.1)
    start = time.monotonic()
    with pytest.raises(RuntimeBudgetExceededError) as exc_info:
        slow_run(agent)
    end = time.monotonic()
    assert "Mid-run wall-clock" in str(exc_info.value)
    # Numeric bound: breach was raised AFTER budget (0.1s) but within polling-interval slack.
    # Test runtime should be roughly [0.1, 0.1 + meter_interval + body-tail].
    total_elapsed = end - start
    assert total_elapsed >= 0.1, f"Layer 3 breach raised before the budget threshold (elapsed={total_elapsed:.3f}s)"
    # Upper bound: meter polls every 0.02s, so worst-case breach detection within ~0.12s
    # of start. Then body's sleep(0.3) finishes + meter cleanup. Generous CI bound: 0.5s.
    assert total_elapsed < 0.5, (
        f"Layer 3 breach took unreasonably long (elapsed={total_elapsed:.3f}s); "
        "should be ~0.1-0.12s detection + body cleanup"
    )


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

    Story 1b.3 code-review fix (P9): assert IDENTITY propagation, not just
    'an event was bound'. Two unrelated events would satisfy `is not None`.
    """
    observed: list[threading.Event | None] = []
    outer_event_capture: list[threading.Event | None] = []

    async def inner_coro() -> None:
        observed.append(current_cancel_event())

    @guarded_fanout(estimator=None, meter_interval_seconds=10.0)
    def run(self: Any) -> str:
        outer_event_capture.append(current_cancel_event())

        # Trigger _run_async's nested-loop fallback by calling from inside a running loop.
        async def outer() -> None:
            _run_async(inner_coro())

        asyncio.run(outer())
        return "ok"

    agent = _FakeAgent()
    run(agent)
    # Inside the worker-thread coroutine, the SAME Event instance MUST be visible.
    assert outer_event_capture[0] is not None
    assert observed[0] is outer_event_capture[0], (
        "ContextVar propagation should preserve identity through _run_async's "
        "worker-thread fallback (Story 1b.1 H6 fix)."
    )


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
# Test-only sentinel-private __agenteval_test_budget__ kwarg   #
# ============================================================ #


def test_test_budget_sentinel_kwarg_override_for_test_fixtures() -> None:
    """Tests override the instance budget via the sentinel-private
    `__agenteval_test_budget__` kwarg. Story 1b.3 code-review fix (D6): the
    pre-edit single-underscore `_budget` was a production backdoor; the new
    double-underscore name signals 'test-only sentinel' and cannot collide
    with legitimate keyword parameters.
    """

    @guarded_fanout(estimator=lambda kwargs: (1.0, 0.1))
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    # Override with a tighter budget: 0.5 < 1.0 → expect CostExceededError.
    with pytest.raises(CostExceededError):
        run(agent, __agenteval_test_budget__=(0.5, 1.0))
    # Override with looser budget that the estimator can satisfy.
    assert run(agent, __agenteval_test_budget__=(2.0, 1.0)) == "ok"


def test_test_budget_kwarg_rejects_wrong_shape() -> None:
    """The sentinel kwarg must be a 2-tuple."""

    @guarded_fanout(estimator=None)
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent()
    with pytest.raises(TypeError, match="2-tuple"):
        run(agent, __agenteval_test_budget__=(1.0,))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="2-tuple"):
        run(agent, __agenteval_test_budget__="invalid")  # type: ignore[arg-type]


# ============================================================ #
# meter_interval_seconds parameter                            #
# ============================================================ #


def test_meter_interval_seconds_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A long meter_interval means the meter doesn't fire during a short body.

    Story 1b.3 code-review fix (P14): use pytest monkeypatch fixture instead
    of raw module-attribute swap so rollback survives test-collection errors.

    Note: After the P10 fix (initial t=0 check before wait loop), the meter
    polls EXACTLY ONCE at t=0 even if the meter_interval is large — that one
    initial poll is part of the contract (fast-breach enforcement).
    """
    poll_count = [0]

    def counting_cost() -> float:
        poll_count[0] += 1
        return 0.0

    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", counting_cost)

    @guarded_fanout(estimator=None, meter_interval_seconds=10.0)
    def quick(self: Any) -> str:
        time.sleep(0.02)
        return "ok"

    agent = _FakeAgent()
    assert quick(agent) == "ok"
    # With a 10s meter interval + initial t=0 check + 0.02s body, the meter
    # polls exactly once (the initial check) before stop_meter is set.
    assert poll_count[0] == 1


# ============================================================ #
# Story 1b.3 code-review patches: estimator validation + cost-source resilience + body-raise chain #
# ============================================================ #


def test_estimator_callable_raise_is_wrapped_as_cost_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    """P4: User-supplied estimator that raises is wrapped in CostExceededError
    with a typed diagnostic instead of leaking the raw exception.
    """

    def bad_estimator(_kwargs: dict) -> tuple[float, float]:
        raise RuntimeError("estimator crashed")

    @guarded_fanout(estimator=bad_estimator)
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent()
    with pytest.raises(CostExceededError) as exc_info:
        run(agent)
    assert "Pre-flight estimator callable raised" in str(exc_info.value)
    assert "RuntimeError" in str(exc_info.value)


def test_estimator_returns_wrong_shape_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """P5: Estimator returning wrong-shape result is wrapped in CostExceededError."""

    @guarded_fanout(estimator=lambda _: "not a tuple")  # type: ignore[arg-type,return-value]
    def run(self: Any) -> str:
        return "ok"

    agent = _FakeAgent()
    with pytest.raises(CostExceededError, match="invalid shape"):
        run(agent)


def test_max_cost_usd_none_skips_layer_1_and_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """P6: `_max_cost_usd = None` honored — Layer 1 + 2 cost checks skipped.
    Previously the code did `cost_est > None` which raised TypeError.
    """
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 999.0)

    @guarded_fanout(estimator=lambda _: (999.0, 0.0), meter_interval_seconds=0.01)
    def run(self: Any) -> str:
        time.sleep(0.02)
        return "ok"

    agent = _FakeAgent(max_cost_usd=None, max_runtime_seconds=None)  # type: ignore[arg-type]
    # Body runs to completion despite cost_est = 999 + meter returning 999.
    assert run(agent) == "ok"


def test_cost_source_exception_triggers_fail_closed_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    """P2: If `_current_cost_usd_for_run()` raises, the meter logs + sets a
    fail-closed breach with `cause='cost_source_failure'` so enforcement
    continues — the meter thread NEVER dies silently.
    """

    def raising_cost() -> float:
        raise RuntimeError("cost source crashed")

    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", raising_cost)

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def run(self: Any) -> str:
        time.sleep(0.05)
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    with pytest.raises(CostExceededError) as exc_info:
        run(agent)
    assert "cost-source provider raised" in str(exc_info.value)


def test_body_raise_with_breach_chains_via_from(monkeypatch: pytest.MonkeyPatch) -> None:
    """D5: When the body raises AND a mid-run breach was recorded, the typed
    BudgetError is raised chained from the body's exception (so both signals
    reach the caller). Pre-edit code silently dropped the breach.
    """
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 100.0)

    class BodyError(Exception):
        pass

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def run(self: Any) -> str:
        # Sleep so the meter thread has a chance to record the breach.
        time.sleep(0.05)
        raise BodyError("body's own fault")

    agent = _FakeAgent(max_cost_usd=5.0)
    with pytest.raises(CostExceededError) as exc_info:
        run(agent)
    # The breach error wins; the body's exception is chained via __cause__.
    assert isinstance(exc_info.value.__cause__, BodyError)


def test_initial_t_zero_meter_check_catches_fast_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    """P10: With the initial t=0 check before the wait loop, a fast cost
    breach is detected even if the body returns before the first wait-tick.
    """
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 50.0)

    @guarded_fanout(estimator=None, meter_interval_seconds=10.0)
    def quick_burst(self: Any) -> str:
        # Body finishes much faster than the 10s meter interval.
        time.sleep(0.05)
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    with pytest.raises(CostExceededError) as exc_info:
        quick_burst(agent)
    assert "Mid-run cost" in str(exc_info.value)


def test_layer_2_cumulative_increasing_values_detects_crossover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P18: A closure that returns increasing values verifies the meter polls
    repeatedly + detects the crossover point (not just a constant >budget).
    """
    values = [0.0, 2.0, 4.0, 6.0]  # crosses 5.0 budget at index 3
    index = [0]

    def increasing_cost() -> float:
        v = values[min(index[0], len(values) - 1)]
        index[0] += 1
        return v

    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", increasing_cost)

    @guarded_fanout(estimator=None, meter_interval_seconds=0.01)
    def slow_run(self: Any) -> str:
        time.sleep(0.1)  # give meter ~10 polls
        return "ok"

    agent = _FakeAgent(max_cost_usd=5.0)
    with pytest.raises(CostExceededError) as exc_info:
        slow_run(agent)
    # The breach reports the crossover value (6.0), not the constant.
    assert "6.00 USD" in str(exc_info.value)


def test_meter_interval_seconds_must_be_positive() -> None:
    """Defensive: 0 or negative meter_interval_seconds is rejected at decoration time."""
    with pytest.raises(ValueError, match="must be > 0"):

        @guarded_fanout(estimator=None, meter_interval_seconds=0.0)
        def run(self: Any) -> str:
            return "ok"

    with pytest.raises(ValueError, match="must be > 0"):

        @guarded_fanout(estimator=None, meter_interval_seconds=-1.0)
        def run2(self: Any) -> str:
            return "ok"
