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

"""Cost + runtime guardrails for Tier-3 fan-out keywords (ADR-015 / was ADR-A5).

`@guarded_fanout(estimator=callable)` decorator that wraps fan-out keywords
(`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`, …) with
the 3-layer enforcement per ADR-015 §Decision L25-29:

- **Layer 1 — Pre-flight estimation.** When `estimator` is provided, calls
  `estimator(kwargs) -> (cost_estimate_usd, runtime_estimate_seconds)` BEFORE
  entering the keyword body. Either estimate exceeding the configured budget
  raises `CostExceededError` or `RuntimeBudgetExceededError` without entering
  the body. When `estimator=None`, Layer 1 is skipped. Estimator-side
  exceptions (the user's callable raising or returning the wrong shape) are
  re-raised wrapped in a typed `CostExceededError` so the failure path stays
  on the typed-budget-error contract.

- **Layer 2 — Mid-run cost meter (Phase-1 stub).** Background poller checks
  cumulative cost every `meter_interval_seconds` (default 5.0s) AND once
  immediately at t=0 before entering the wait loop, so fast breaches that
  complete in less than one polling interval still trigger enforcement.
  Cost source is `_current_cost_usd_for_run()` which returns 0.0 in Phase-1;
  **Story 4.1 (Generic LiteLLM adapter)** wires the real cost tracker. The
  cost source is module-level + single-fanout-at-a-time scoped in Phase-1;
  per-run scoping (run id / context key / provider handle) is deferred to
  Story 4.1 — see the `_current_cost_usd_for_run` docstring for the contract.

  On breach:
    - sets the `_cancel_event` ContextVar so cooperative-cancellation-aware
      keyword bodies can exit early;
    - records the breach in `_BreachState`;
    - after the keyword body returns (OR raises — the breach error is chained
      via `raise BudgetError(...) from body_exc` so both signals reach the
      caller), the wrapper raises `CostExceededError` with the cumulative-
      cost-at-breach surfaced in the message.

  If the cost source itself raises (e.g., Story 4.1's real provider client
  throws on transient network error), the meter logs at WARNING + sets a
  fail-closed breach with `cause="cost_source_failure"` so enforcement
  continues — the meter thread never dies silently.

- **Layer 3 — Mid-run wall-clock meter.** Same background poller tracks
  elapsed wall-clock. On `elapsed > max_runtime_seconds` (when not None):
  raises `RuntimeBudgetExceededError` on the NEXT polling tick after the
  budget is exceeded — i.e., the breach is observed at most
  `meter_interval_seconds` after the actual threshold (the pre-Story-1b.3-
  code-review wording "EXACTLY the budget" was retracted at review; with a
  polling loop, exactness is not achievable without a deadline timer, which
  was deemed over-engineering for Phase-1).

Cooperative cancellation hook (ADR-015 L42 — code-review amendment):
    The ADR L42 wording mentioned "asyncio.CancelledError thrown by the
    meter" pre-Story-1b.3-code-review; Codex's cross-LLM citation re-derivation
    caught that the shipped mechanism is a `threading.Event` bound via
    `_cancel_event_var` ContextVar (which integrates correctly with both
    sync-frame and `_run_async`-fallback worker-thread frames thanks to
    Story 1b.1's `copy_context()` propagation). The ADR was amended to
    ratify the threading.Event mechanism; asyncio-task cancellation
    integration remains a Story 4.1 deliverable (when provider clients are
    actual asyncio Tasks the meter can target).

The decorator reads `max_cost_usd` + `max_runtime_seconds` from the bound
`AgentEval` instance (Story 1a.6 wiring + Story 1b.1's `resolve_config` per
FR41). `max_cost_usd = None` is honored (Layer 1+2 cost checks skipped) as
well as `max_runtime_seconds = None` (Layer 1+3 runtime checks skipped) —
useful for tests + diagnostic runs.

Test fixtures override the bound-instance budget via the sentinel-private
kwarg-only `__agenteval_test_budget__=(cost, runtime)` parameter (renamed
from the pre-edit `_budget` after Story 1b.3 code review flagged the
production-backdoor risk of a single-underscore name colliding with
legitimate keyword parameters). The double-underscore prefix conveys
"test-only sentinel"; production callers cannot pass this kwarg by accident.

References:
    - ADR-015 (was ADR-A5): `docs/adr/ADR-015-cost-runtime-guardrail-decorator.md`
    - PRD §FR11 — `max_cost_usd` budget on Tier-3 fan-out keywords
    - PRD §FR11b — `max_runtime_seconds` budget
    - PRD §FR42 — `max_cost_usd=5.0` + `max_runtime_seconds=None` Library defaults (Story 1a.6)
    - architecture L380 — `@guarded_fanout(estimator=callable)` decoration pattern
    - architecture L1196 — `_kernel/guardrails.py` location
    - architecture L1521 — Tier-3 fan-out keywords only (selective decoration)
    - Story 1b.1 `_kernel/run_async.py` — ContextVar propagation via `copy_context`
    - Story 1b.2 `src/AgentEval/errors.py` — CostExceededError / RuntimeBudgetExceededError
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, TypeVar

from AgentEval.errors import CostExceededError, RuntimeBudgetExceededError

F = TypeVar("F", bound=Callable[..., Any])

__all__ = [
    "guarded_fanout",
    "current_cancel_event",
    "_current_cost_usd_for_run",
]


_log = logging.getLogger(__name__)


# Cooperative cancellation hook (per ADR-015 §Decision L27 cancellation).
# Bound by `@guarded_fanout`'s wrapper at decorated-function entry; propagated
# through Story 1b.1's `_run_async` via `contextvars.copy_context()` (H6 fix).
_cancel_event_var: ContextVar[threading.Event | None] = ContextVar(
    "agenteval_guarded_fanout_cancel_event", default=None
)


# Sentinel-private kwarg name for test-fixture budget override. Story 1b.3
# code-review feedback (Codex + Blind + Edge 3-way): the pre-edit name
# `_budget` was a production backdoor because the wrapper unconditionally
# popped it from kwargs on every call. The double-underscore form conveys
# "test-only private sentinel"; production callers cannot pass this kwarg
# by accident or collision.
_TEST_BUDGET_KWARG = "__agenteval_test_budget__"


def _current_cost_usd_for_run() -> float:
    """Phase-1 stub — Layer 2's cost source.

    Returns 0.0 until Story 4.1 (Generic LiteLLM adapter) wires the real
    LiteLLM cost-tracking API. Story 1b.3 ships the polling loop + breach
    detection + cooperative-cancellation hook; the cost source is the stub.

    Phase-1 single-fanout-at-a-time scoping limitation (Story 1b.3 code-review
    Codex catch): this function is module-level and takes no run id / context
    key / provider handle. Concurrent `@guarded_fanout`-decorated calls
    therefore share the same cost source. Story 4.1 wires the real provider's
    cost-tracking API and threads a per-run token (likely via ContextVar) so
    concurrent fan-outs see independent cost accumulators. Until then, only
    one `@guarded_fanout` keyword should be in-flight per process.

    Tests monkey-patch this function via `monkeypatch.setattr(
    AgentEval._kernel.guardrails, '_current_cost_usd_for_run', fake_fn)` to
    verify the Layer 2 breach path.

    If a production override of this function ever raises (Story 4.1's real
    cost source on transient network error), the meter loop catches the
    exception + sets a fail-closed breach so enforcement continues — the
    meter thread never dies silently.
    """
    return 0.0


def current_cancel_event() -> threading.Event | None:
    """Return the cancellation event bound to the current `@guarded_fanout` frame.

    Async-aware fan-out keyword bodies invoked through Story 1b.1's `_run_async`
    inherit the event via `contextvars.copy_context()` propagation (H6 fix).
    Keyword bodies poll via `current_cancel_event().is_set()` and exit early.

    Returns None outside a decorated frame (so consumers don't crash; just
    skip the cancellation check).
    """
    return _cancel_event_var.get()


@dataclass
class _BreachState:
    """Records a mid-run meter breach so the wrapper can raise after body returns."""

    breached: bool = False
    cost_at_breach: float = 0.0
    elapsed_at_breach: float = 0.0
    # Possible values: "cost" | "runtime" | "cost_source_failure".
    cause: str = ""


def _validate_estimator_result(result: Any) -> tuple[float, float]:
    """Best-effort validation of the user-supplied estimator's return value.

    The estimator contract is `(kwargs: dict) -> tuple[float, float]`. If a
    user-supplied estimator returns the wrong shape or non-numeric values, we
    raise `CostExceededError` with a typed diagnostic rather than letting a
    bare TypeError leak through tuple-unpacking or numeric-comparison.
    """
    try:
        if not isinstance(result, tuple) or len(result) != 2:
            raise TypeError(f"estimator must return a 2-tuple (got {result!r})")
        cost_est = float(result[0])
        runtime_est = float(result[1])
    except (TypeError, ValueError) as exc:
        raise CostExceededError(
            f"Pre-flight estimator returned an invalid shape or non-numeric values "
            f"({result!r}); refusing to enter keyword body. Estimator contract: "
            f"`(kwargs: dict) -> (cost_estimate_usd: float, runtime_estimate_seconds: float)`."
        ) from exc
    return cost_est, runtime_est


def guarded_fanout(
    estimator: Callable[[dict[str, Any]], tuple[float, float]] | None = None,
    *,
    meter_interval_seconds: float = 5.0,
) -> Callable[[F], F]:
    """Decorator factory wrapping a Tier-3 fan-out keyword with 3-layer enforcement.

    Args:
        estimator: Optional callable `(kwargs: dict) -> (cost_est_usd, runtime_est_s)`
            invoked at Layer 1. When None, pre-flight estimation is skipped.
            Estimator-side exceptions (raise OR wrong-shape return) are
            wrapped in a typed `CostExceededError` so the failure path stays
            on the typed-budget-error contract.
        meter_interval_seconds: Poll cadence for Layer 2 + Layer 3 meters.
            Default 5.0s per ADR-015 reference. Configurable for unit tests
            (use very small values like 0.01s) and for low-budget runs. Must
            be > 0.

    Returns:
        A decorator that wraps the keyword function.

    Notes:
        Decorated function MUST be a method on a class that exposes
        `_max_cost_usd: float | None` and `_max_runtime_seconds: float | None`
        attributes (per Story 1a.6's `AgentEval.__init__` wiring + Story
        1b.1's `resolve_config`). Tests can use a minimal `SimpleNamespace`
        or `@dataclass` stand-in matching that contract. `None` for either
        budget skips the corresponding layer's checks (Layer 1+2 for cost,
        Layer 1+3 for runtime).

        Test-only override: pass `__agenteval_test_budget__=(max_cost_usd,
        max_runtime_seconds)` as a kwarg-only argument to override the
        bound-instance budget for that single invocation. Production code
        cannot accidentally collide with this sentinel-private kwarg name.
    """
    if meter_interval_seconds <= 0:
        raise ValueError(f"meter_interval_seconds must be > 0 (got {meter_interval_seconds!r})")

    def _decorate(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Resolve budget: sentinel-private kwarg override (test-only) > instance attributes.
            budget_override = kwargs.pop(_TEST_BUDGET_KWARG, None)
            if budget_override is not None:
                if not isinstance(budget_override, tuple) or len(budget_override) != 2:
                    raise TypeError(
                        f"{_TEST_BUDGET_KWARG} must be a 2-tuple of "
                        f"(max_cost_usd, max_runtime_seconds); got {budget_override!r}"
                    )
                max_cost_usd, max_runtime_seconds = budget_override
            else:
                max_cost_usd = getattr(self, "_max_cost_usd", None)
                max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)

            # Layer 1: pre-flight estimation.
            if estimator is not None:
                try:
                    estimator_result = estimator(kwargs)
                except Exception as exc:
                    raise CostExceededError(
                        f"Pre-flight estimator callable raised {type(exc).__name__}: "
                        f"{exc}; refusing to enter keyword body."
                    ) from exc
                cost_est, runtime_est = _validate_estimator_result(estimator_result)
                if max_cost_usd is not None and cost_est > max_cost_usd:
                    raise CostExceededError(
                        f"Pre-flight cost estimate {cost_est:.2f} USD > "
                        f"budget {max_cost_usd:.2f} USD; refusing to enter "
                        f"keyword body."
                    )
                if max_runtime_seconds is not None and runtime_est > max_runtime_seconds:
                    raise RuntimeBudgetExceededError(
                        f"Pre-flight runtime estimate {runtime_est:.1f}s > "
                        f"budget {max_runtime_seconds:.1f}s; refusing to enter "
                        f"keyword body."
                    )

            # Bind cancellation event + start mid-run meter thread.
            cancel_event = threading.Event()
            token = _cancel_event_var.set(cancel_event)
            breach = _BreachState()
            stop_meter = threading.Event()
            start_monotonic = time.monotonic()

            def _check_meters_once() -> bool:
                """Run one pass of Layer 2 + Layer 3 checks. Returns True iff a breach was recorded."""
                try:
                    current_cost = _current_cost_usd_for_run()
                except Exception as exc:
                    # Fail-closed: meter thread NEVER dies silently. If the
                    # cost source raises, log + record a breach with a typed
                    # `cause` so the wrapper surfaces the failure to caller.
                    _log.warning(
                        "Cost source `_current_cost_usd_for_run` raised %s: %s; treating as fail-closed budget breach.",
                        type(exc).__name__,
                        exc,
                    )
                    breach.breached = True
                    breach.cost_at_breach = 0.0
                    breach.elapsed_at_breach = time.monotonic() - start_monotonic
                    breach.cause = "cost_source_failure"
                    cancel_event.set()
                    return True
                elapsed = time.monotonic() - start_monotonic
                # Layer 2: cumulative cost meter (when budget is configured).
                if max_cost_usd is not None and current_cost > max_cost_usd:
                    breach.breached = True
                    breach.cost_at_breach = current_cost
                    breach.elapsed_at_breach = elapsed
                    breach.cause = "cost"
                    cancel_event.set()
                    return True
                # Layer 3: wall-clock meter on next polling tick after budget.
                if max_runtime_seconds is not None and elapsed > max_runtime_seconds:
                    breach.breached = True
                    breach.cost_at_breach = current_cost
                    breach.elapsed_at_breach = elapsed
                    breach.cause = "runtime"
                    cancel_event.set()
                    return True
                return False

            def _meter_loop() -> None:
                """Background poller for Layer 2 (cost) + Layer 3 (runtime)."""
                # Initial t=0 check before entering the wait loop, so fast
                # breaches that complete in less than one polling interval
                # still trigger enforcement.
                if _check_meters_once():
                    return
                while not stop_meter.wait(timeout=meter_interval_seconds):
                    if _check_meters_once():
                        return

            meter_thread = threading.Thread(
                target=_meter_loop,
                name="agenteval-guarded-fanout-meter",
                daemon=False,  # explicit per AC-1b.3.4; Story 1b.1's threading-pattern convention.
            )
            meter_thread.start()

            body_exc: BaseException | None = None
            result: Any = None
            try:
                result = func(self, *args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 — we re-raise (possibly chained)
                body_exc = exc
            finally:
                stop_meter.set()
                meter_thread.join(timeout=meter_interval_seconds + 1.0)
                if meter_thread.is_alive():
                    _log.warning(
                        "Meter thread did not terminate within %.1fs after stop signal; "
                        "leaking thread but proceeding with body result.",
                        meter_interval_seconds + 1.0,
                    )
                # Note: ContextVar reset is deferred until AFTER any post-body
                # raise so cleanup handlers between the raise + outer except
                # can still read `current_cancel_event()`.

            try:
                if breach.breached:
                    if breach.cause == "cost":
                        breach_exc: Exception = CostExceededError(
                            f"Mid-run cost {breach.cost_at_breach:.2f} USD breached "
                            f"budget {max_cost_usd:.2f} USD after {breach.elapsed_at_breach:.1f}s; "
                            f"cumulative cost surfaced here."
                        )
                    elif breach.cause == "runtime":
                        breach_exc = RuntimeBudgetExceededError(
                            f"Mid-run wall-clock {breach.elapsed_at_breach:.1f}s breached "
                            f"budget {max_runtime_seconds:.1f}s (next polling tick after "
                            f"budget; cumulative cost at breach: "
                            f"{breach.cost_at_breach:.2f} USD)."
                        )
                    else:
                        # breach.cause == "cost_source_failure"
                        breach_exc = CostExceededError(
                            f"Mid-run cost-source provider raised an exception; treating "
                            f"as fail-closed budget breach after "
                            f"{breach.elapsed_at_breach:.1f}s. See log for the underlying "
                            "cost-source error."
                        )
                    # If the body raised too, chain via `from body_exc` so both
                    # signals reach the caller (typed budget contract is the
                    # primary; body's exception is the cleanup-shadow chain).
                    if body_exc is not None:
                        raise breach_exc from body_exc
                    raise breach_exc
                if body_exc is not None:
                    raise body_exc
                return result
            finally:
                _cancel_event_var.reset(token)

        return wrapper  # type: ignore[return-value]

    return _decorate
