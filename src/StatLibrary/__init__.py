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

"""Reach the stochastic-run estimators from ``.robot``.

The spine's ``stats`` module has the math - ``run_n`` gathers trials, ``pass_at_k``
gives the unbiased HumanEval estimate, ``wilson_interval`` puts a confidence band
on a success proportion - but none of it was callable as a keyword. That gap is
why ``Skill.Get Activation Pass At K``'s docstring referenced a phantom
``Stat.Run N Times``. ``StatLibrary`` closes it.

Import it on its own::

    *** Settings ***
    Library    StatLibrary

Every keyword carries the ``Stat.`` prefix, so no ``WITH NAME`` is needed.

- `Stat.Run N Times` fans a keyword (or Python callable) out over N trials and
  returns the per-trial ``KeywordRun`` list. It is labelled **Tier 3** because it
  drives whatever it is handed - which may be a real coding agent.
- `Stat.Get Pass At K` and `Stat.Wilson Interval` are pure estimator math over
  already-collected outcomes, so they stay **Tier 1**.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn

from AgentEval._core import stats, tier
from AgentEval._core.stats import KeywordRun

__all__ = ["StatLibrary"]


class StatLibrary:
    """Run stochastic keywords N times and estimate pass@k / Wilson bands."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    # ------------------------------------------------------------------ #
    # Tier 3 - fan a keyword/callable out over N trials.                 #
    # ------------------------------------------------------------------ #

    @keyword(name="Stat.Run N Times")
    @tier(3)
    def run_n_times(
        self,
        n: int,
        keyword_or_callable: str | Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> list[KeywordRun]:
        """Run a keyword (or Python callable) ``n`` times; return per-trial outcomes.

        ``keyword_or_callable`` is either a Robot Framework keyword name (resolved
        via ``BuiltIn().run_keyword`` at each trial) or a Python callable. The
        trailing positional/named arguments are bound once and replayed on every
        trial. Trial errors are captured on the ``KeywordRun`` rather than raised,
        so a partial fan-out still yields analyzable results - feed the returned
        list straight into `Stat.Get Pass At K`.

        This keyword is Tier 3: it drives whatever it is handed, which may be a
        real coding agent.

        Example:
        | ${runs}=    Stat.Run N Times    10    Skill.Get Activation Decision    ${skill}    ${prompt}
        | ${p}=    Stat.Get Pass At K    ${runs}    k=5
        | Should Be True    ${p} >= 0.7
        """
        trials = int(n)
        if callable(keyword_or_callable):
            fn = keyword_or_callable

            def target() -> Any:
                return fn(*args, **kwargs)
        else:
            name = str(keyword_or_callable)
            rf_args = [*args, *(f"{key}={value}" for key, value in kwargs.items())]

            def target() -> Any:
                return BuiltIn().run_keyword(name, *rf_args)

        return stats.run_n(target, trials)

    # ------------------------------------------------------------------ #
    # Tier 1 - pure estimator math over already-collected outcomes.      #
    # ------------------------------------------------------------------ #

    @keyword(name="Stat.Get Pass At K")
    @tier(1)
    def get_pass_at_k(
        self,
        runs: list[KeywordRun],
        k: int,
        predicate: Callable[[KeywordRun], bool] | None = None,
    ) -> float:
        """Unbiased HumanEval pass@k over ``runs`` collected by `Stat.Run N Times`.

        Delegates to ``stats.pass_at_k``: ``1 - C(n-c, k) / C(n, k)`` where ``c``
        is the number of passing trials. ``predicate`` classifies each trial;
        it defaults to ``stats.default_pass_predicate`` (a trial passes when it
        did not raise and its completeness is not ``"truncated"``/``"partial"``).
        Pure math over pre-collected runs - no model call - so this stays Tier 1.

        Example:
        | ${runs}=    Stat.Run N Times    10    Some Stochastic Keyword
        | ${p}=    Stat.Get Pass At K    ${runs}    k=5
        | Should Be True    ${p} >= 0.7
        """
        return stats.pass_at_k(runs, int(k), predicate=predicate)

    @keyword(name="Stat.Wilson Interval")
    @tier(1)
    def wilson_interval(
        self,
        successes: int,
        trials: int,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """Wilson score confidence interval for a binomial proportion.

        Delegates to ``stats.wilson_interval``. Preferred over the normal
        approximation for small samples or extreme proportions. Returns
        ``(lower, upper)`` in ``[0, 1]``. Pure math, so Tier 1.

        Example:
        | ${ci}=    Stat.Wilson Interval    8    10
        | Should Be True    ${ci}[0] >= 0.4
        """
        return stats.wilson_interval(int(successes), int(trials), float(confidence))
