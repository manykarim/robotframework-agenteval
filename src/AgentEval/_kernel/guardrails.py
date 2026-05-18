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
  the body. When `estimator=None`, Layer 1 is skipped.

- **Layer 2 — Mid-run cost meter (Phase-1 stub).** Background poller checks
  cumulative cost every `meter_interval_seconds` (default 5.0s). Cost source
  is `_current_cost_usd_for_run()` which returns 0.0 in Phase-1; **Story 4.1
  (Generic LiteLLM adapter)** wires the real cost tracker. On breach:
  - sets the `_cancel_event` ContextVar so cooperative-cancellation-aware
    keyword bodies can exit early;
  - records the breach in `_BreachState`;
  - after the keyword body returns, the wrapper raises `CostExceededError`
    with the cumulative-cost-at-breach surfaced in the message.

- **Layer 3 — Mid-run wall-clock meter.** Same background poller tracks
  elapsed wall-clock. On `elapsed > max_runtime_seconds` (when not None):
  raises `RuntimeBudgetExceededError` at EXACTLY the budget (not 1.1×; the
  1.1× wording in the pre-edit story spec was unratified).

Cooperative cancellation hook:
    Story 1b.1's `_run_async` uses `contextvars.copy_context()` to propagate
    ContextVar state through the worker-thread fallback. The decorator binds
    `_cancel_event_var` at the decorated-function entry; async-aware
    fan-out keyword bodies access via `current_cancel_event()` and can poll
    the event to exit early. Phase-1: the event-propagation contract ships;
    full provider-client cancellation integration is Story 4.1.

The decorator reads `max_cost_usd` + `max_runtime_seconds` from the bound
`AgentEval` instance (Story 1a.6 wiring + Story 1b.1's `resolve_config` per
FR41). Test fixtures may override via a kwarg-only `_budget` parameter
documented below.

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
import threading
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, TypeVar

from AgentEval.errors import CostExceededError, RuntimeBudgetExceededError

F = TypeVar("F", bound=Callable[..., Any])

__all__ = [
    "guarded_fanout",
    "current_cancel_event",
    "_current_cost_usd_for_run",
]


# Cooperative cancellation hook (per ADR-015 §Decision L27 cancellation).
# Bound by `@guarded_fanout`'s wrapper at decorated-function entry; propagated
# through Story 1b.1's `_run_async` via `contextvars.copy_context()` (H6 fix).
_cancel_event_var: ContextVar[threading.Event | None] = ContextVar(
    "agenteval_guarded_fanout_cancel_event", default=None
)


def _current_cost_usd_for_run() -> float:
    """Phase-1 stub — Layer 2's cost source.

    Returns 0.0 until Story 4.1 (Generic LiteLLM adapter) wires the real
    LiteLLM cost-tracking API. Story 1b.3 ships the polling loop + breach
    detection + cooperative-cancellation hook; the cost source is the stub.

    Tests monkey-patch this function via `monkeypatch.setattr(
    AgentEval._kernel.guardrails, '_current_cost_usd_for_run', fake_fn)` to
    verify the Layer 2 breach path.
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
    cause: str = ""  # "cost" or "runtime"
    threads_to_join: list[threading.Thread] = field(default_factory=list)


def guarded_fanout(
    estimator: Callable[[dict[str, Any]], tuple[float, float]] | None = None,
    *,
    meter_interval_seconds: float = 5.0,
) -> Callable[[F], F]:
    """Decorator factory wrapping a Tier-3 fan-out keyword with 3-layer enforcement.

    Args:
        estimator: Optional callable `(kwargs: dict) -> (cost_est_usd, runtime_est_s)`
            invoked at Layer 1. When None, pre-flight estimation is skipped.
        meter_interval_seconds: Poll cadence for Layer 2 + Layer 3 meters.
            Default 5.0s per ADR-015 reference. Configurable for unit tests
            (use very small values like 0.01s) and for low-budget runs.

    Returns:
        A decorator that wraps the keyword function.

    Notes:
        Decorated function MUST be a method on a class that exposes
        `_max_cost_usd: float` and `_max_runtime_seconds: float | None`
        attributes (per Story 1a.6's `AgentEval.__init__` wiring + Story
        1b.1's `resolve_config`). Tests can use a minimal `SimpleNamespace`
        or `@dataclass` stand-in matching that contract.

        Test-only override: pass `_budget=(max_cost_usd, max_runtime_seconds)`
        as a kwarg-only argument to the DECORATED function call to override
        the instance budget for that single invocation. Production code MUST
        NOT use this — it exists solely for test fixtures.
    """

    def _decorate(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Resolve budget: kwarg override (test-only) > instance attributes.
            budget_override = kwargs.pop("_budget", None)
            if budget_override is not None:
                max_cost_usd, max_runtime_seconds = budget_override
            else:
                max_cost_usd = self._max_cost_usd
                max_runtime_seconds = self._max_runtime_seconds

            # Layer 1: pre-flight estimation.
            if estimator is not None:
                cost_est, runtime_est = estimator(kwargs)
                if cost_est > max_cost_usd:
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

            def _meter_loop() -> None:
                """Background poller for Layer 2 (cost) + Layer 3 (runtime)."""
                while not stop_meter.wait(timeout=meter_interval_seconds):
                    elapsed = time.monotonic() - start_monotonic
                    current_cost = _current_cost_usd_for_run()
                    # Layer 2: cumulative cost meter.
                    if current_cost > max_cost_usd:
                        breach.breached = True
                        breach.cost_at_breach = current_cost
                        breach.elapsed_at_breach = elapsed
                        breach.cause = "cost"
                        cancel_event.set()
                        return
                    # Layer 3: wall-clock meter at EXACTLY the configured budget
                    # (not 1.1× — the 1.1× wording in the pre-edit story spec
                    # was unratified per ADR-015 §Decision L29).
                    if max_runtime_seconds is not None and elapsed > max_runtime_seconds:
                        breach.breached = True
                        breach.cost_at_breach = current_cost
                        breach.elapsed_at_breach = elapsed
                        breach.cause = "runtime"
                        cancel_event.set()
                        return

            meter_thread = threading.Thread(target=_meter_loop, name="agenteval-guarded-fanout-meter")
            meter_thread.start()

            try:
                result = func(self, *args, **kwargs)
            finally:
                stop_meter.set()
                meter_thread.join(timeout=meter_interval_seconds + 1.0)
                _cancel_event_var.reset(token)

            # Post-body: raise typed error if mid-run meter recorded a breach.
            if breach.breached:
                if breach.cause == "cost":
                    raise CostExceededError(
                        f"Mid-run cost {breach.cost_at_breach:.2f} USD breached "
                        f"budget {max_cost_usd:.2f} USD after {breach.elapsed_at_breach:.1f}s; "
                        f"cumulative cost surfaced here."
                    )
                # breach.cause == "runtime"
                raise RuntimeBudgetExceededError(
                    f"Mid-run wall-clock {breach.elapsed_at_breach:.1f}s breached "
                    f"budget {max_runtime_seconds:.1f}s "
                    f"(cumulative cost at breach: {breach.cost_at_breach:.2f} USD)."
                )

            return result

        return wrapper  # type: ignore[return-value]

    return _decorate
