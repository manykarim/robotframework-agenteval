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

# ruff: noqa: E501
# Browser-Library-style docstring tables (`| =Arguments= | =Description= |`)
# can carry long descriptions on a single physical line. The per-line
# 120-char limit is waived for this file per Phase 2 docstring-refresh
# proposal (2026-05-26).

"""Statistical primitives RF-keyword surface (Story 6.3 / PRD FR26 + FR27 + FR31a).

Ships 4 `@keyword`-decorated methods on `StatsLibrary`:

- FR26: `Stat.Run N Times` (Tier-3 fan-out via `@guarded_fanout`) — independent-
  sample N-trial runner; returns `list[KeywordRun]` per Story 1b.6 ratified
  return type.
- FR27: `Stat.Get Pass At K` (Tier-1) — HumanEval unbiased estimator; returns
  `float ∈ [0, 1]`.
- D-1 resolution paired getter: `Stat.Get Pass At K Confidence Interval` (Tier-1)
  — Wilson score interval at `confidence` level.
- FR31a: `Stat.Assert Run Determinism` (Tier-1) — runs a Tier-1 keyword twice,
  asserts bit-identical output.

Sub-library registration via `_SUB_LIBRARIES` in `AgentEval/__init__.py`.
Tier-3 `Stat.Run N Times` reads `_max_cost_usd` + `_max_runtime_seconds`
from `self` (forwarded from top-level `AgentEval(...)` per Story 1a.6 +
Story 4.3 propagation pattern).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.context import current_context
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.host_budget_plumbing import _HostBudgetPlumbing
from AgentEval._kernel.redaction import redact
from AgentEval._kernel.tier import tier
from AgentEval.errors import TierViolationError
from AgentEval.stats import _internal
from AgentEval.stats.types import KeywordRun, MannWhitneyResult

__all__ = ["StatsLibrary"]

# Browser-Library-style docstring migration marker (Phase 2, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True

# Story 13.1 — Phase-2 `[agenteval-advanced]` extra gate. scipy + numpy power
# the 3 advanced keyword methods (Mann-Whitney U, Cliff Delta, Bootstrap CI).
# The `StatsLibrary` class itself MUST remain importable WITHOUT the extra so
# Phase-1 surface keywords stay functional; only the 3 Phase-2 methods raise
# ImportError on invocation.
try:
    import numpy as _numpy_advanced  # noqa: F401
    import scipy as _scipy_advanced  # noqa: F401

    _ADVANCED_AVAILABLE = True
    _ADVANCED_IMPORT_ERROR: ImportError | None = None
except ImportError as _advanced_err:  # pragma: no cover  -- exercised via monkeypatch
    _ADVANCED_AVAILABLE = False
    _ADVANCED_IMPORT_ERROR = _advanced_err


def _raise_advanced_extra_missing(keyword_name: str) -> None:
    """Raise the canonical `[agenteval-advanced]` extra-missing ImportError.

    Per Story 13.1 D-3 + epics.md L2153: the ImportError MUST recommend
    ``uv pip install robotframework-agenteval[agenteval-advanced]``.
    """
    raise ImportError(
        f"Stat.{keyword_name}: scipy + numpy required. "
        f"Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
    ) from _ADVANCED_IMPORT_ERROR


class StatsLibrary(_HostBudgetPlumbing):
    """4 `@keyword`-decorated statistical primitives (Story 6.3 / PRD FR26-FR31a).

    Inherits `_HostBudgetPlumbing` for the `_max_cost_usd` +
    `_max_runtime_seconds` instance attrs consumed by `@guarded_fanout`
    on `Stat.Run N Times` (Tier-3 fan-out keyword). Budgets are forwarded
    from top-level `AgentEval(max_cost_usd=..., max_runtime_seconds=...)`
    via `_build_components`' unified `_HostBudgetPlumbing` subclass check
    (`compose-single-library-import` change; formerly a dedicated
    class-name branch per Story 6.3 AC-6.3.8).
    """

    # ----------------------------------------------------------------- #
    # FR26 — Stat.Run N Times (Tier-3 fan-out)                          #
    # ----------------------------------------------------------------- #

    @keyword(name="Stat.Run N Times")
    @tier(3)
    @guarded_fanout()
    def run_n_times(
        self,
        n: int,
        keyword: str | Callable[..., Any],
        keyword_args: dict[str, Any] | list[Any] | None = None,
        seed: int | None = None,
    ) -> list[KeywordRun]:
        """Runs a keyword ``n`` times independently and returns the per-trial results (PRD FR26).

        [Tier 3 — Stochastic Fan-Out] — wraps the target keyword in
        independent trials. Returns ``list[KeywordRun]`` of length ``n``.
        Trial-level errors are re-raised from this keyword — wrap in
        ``Run Keyword And Ignore Error`` for "ignore failures" semantics.

        | =Arguments= | =Description= |
        | ``n`` | Number of independent trials. Must be ``>= 1``. |
        | ``keyword`` | RF keyword name (``str``) OR a Python callable. String form requires an active RF execution context (resolved via ``BuiltIn``); callable form is useful for pytest unit tests. |
        | ``keyword_args`` | Optional ``dict`` of kwargs OR ``list`` of RF named-arg strings (e.g. ``{"adapter": "generic", "prompt": "Hi"}`` or ``["adapter=generic", "prompt=Hi"]``). ``None`` = no args. |
        | ``seed`` | Optional ``int`` seed; each trial receives ``seed + trial_index`` via a ``seed=`` kwarg injection so trials are deterministic but distinct. ``None`` = OS-entropy seeding per trial. |

        Raises ``ValueError`` when ``n < 1``. Raises ``CostExceededError`` /
        ``RuntimeBudgetExceededError`` per the ``@guarded_fanout`` 3-layer
        enforcement.

        Example:
        | @{runs} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock', 'prompt=Hi']}}
        | ${pass_at_5} =    `Stat.Get Pass At K`    ${runs}    k=5
        | Should Be True    ${pass_at_5} >= 0.6
        | @{runs} =    `Stat.Run N Times`    n=10    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}    seed=42

        Notes:
        - PRD FR26 ratifies the independent-trial fan-out shape; determinism-contract.md L55 pins the ``list[KeywordRun]`` return type.
        - Cost / runtime guardrails per ADR-015 + `_kernel/guardrails.py::@guarded_fanout`.
        - Sibling keyword: `Stat.Get Pass At K` (Tier-1) consumes the returned list.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if n < 1:
            raise ValueError(f"n must be >= 1; got {n!r}")
        positional, named = _internal._normalize_keyword_args(keyword_args)
        callable_ref: Callable[..., Any]
        kw_name: str
        if isinstance(keyword, str):
            kw_name = keyword
            # Story 6.3 code-review HIGH-γ fix (Codex empirical STAR):
            # `BuiltIn.run_keyword(name, /, *args)` is varargs-only — passing
            # `**kwargs` raises TypeError. Reconstruct RF-style positional +
            # `key=value` tokens that the run_keyword(name, *args) signature
            # accepts.
            from robot.libraries.BuiltIn import BuiltIn

            def callable_ref_impl(*pos: Any, **kw: Any) -> Any:
                rf_args: list[Any] = list(pos)
                for k, v in kw.items():
                    rf_args.append(f"{k}={v}")
                return BuiltIn().run_keyword(kw_name, *rf_args)

            callable_ref = callable_ref_impl
        else:
            callable_ref = keyword
            # Story 6.3 code-review LOW-9 fix (Codex): prefer `robot_name`
            # over Python `__name__` for operator-facing telemetry consistency.
            target = getattr(keyword, "__func__", keyword)
            kw_name = str(getattr(target, "robot_name", None) or getattr(keyword, "__name__", repr(keyword)))

        ctx = current_context()
        parent_test_id = ctx.test_id if ctx is not None else ""

        runs: list[KeywordRun] = []
        for trial_index in range(n):
            run = _internal._dispatch_trial(
                callable_ref,
                kw_name,
                positional,
                named,
                parent_test_id,
                trial_index,
                seed,
            )
            runs.append(run)
        return runs

    # ----------------------------------------------------------------- #
    # FR27 — Stat.Get Pass At K (Tier-1)                                #
    # ----------------------------------------------------------------- #

    @keyword(name="Stat.Get Pass At K")
    @tier(1)
    def get_pass_at_k(
        self,
        runs: list[KeywordRun],
        k: int,
        predicate: Callable[[KeywordRun], bool] | None = None,
    ) -> float:
        """Computes the HumanEval Pass@k unbiased estimator over independent trials (PRD FR27).

        [Tier 1 — Deterministic] — closed-form computation of the
        HumanEval estimator ``1 - C(n-c, k) / C(n, k)``. Returns
        ``float ∈ [0, 1]``. Scalar return preserves AssertionEngine
        compatibility (``>=`` / ``<=`` matchers); CI is a separate paired
        getter — see `Stat.Get Pass At K Confidence Interval`.

        | =Arguments= | =Description= |
        | ``runs`` | ``list[KeywordRun]`` — typically the result of `Stat.Run N Times`. |
        | ``k`` | Top-k parameter. Must satisfy ``1 <= k <= len(runs)``. |
        | ``predicate`` | Optional ``Callable[[KeywordRun], bool]`` for pass/fail classification. Default checks ``r.completeness == "complete"`` per epic AC-2 + Story 6.4 fix-NOW. |

        Raises ``ValueError`` when ``k < 1``, ``k > len(runs)``, or
        ``len(runs) == 0``.

        Example:
        | @{runs} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
        | ${pass_at_1} =    `Stat.Get Pass At K`    ${runs}    k=1
        | ${pass_at_5} =    `Stat.Get Pass At K`    ${runs}    k=5
        | Should Be True    ${pass_at_5} >= ${pass_at_1}                            # Pass@k is monotone non-decreasing in k.
        | ${pred} =    Evaluate    lambda r: r.error is None
        | ${pass_strict} =    `Stat.Get Pass At K`    ${runs}    k=5    predicate=${pred}

        Notes:
        - PRD FR27 ratifies the scalar ``float`` return type — no tuple, no dataclass (Wilson CI is a separate paired getter per Story 6.3 D-1 resolution).
        - Default predicate updated by Story 6.4 fix-NOW: ``completeness == "complete"`` (pre-edit ``"full"`` was fake-green; `AgentRunMetadata._VALID_COMPLETENESS` is ``{"complete", "truncated", "partial"}``).
        - Sibling keyword: `Stat.Get Pass At K Confidence Interval` for the Wilson score CI.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        predicate_fn = predicate if predicate is not None else _internal._default_pass_predicate
        c = sum(1 for r in runs if predicate_fn(r))
        n = len(runs)
        return _internal._compute_pass_at_k(c, n, k)

    @keyword(name="Stat.Get Pass At K Confidence Interval")
    @tier(1)
    def get_pass_at_k_confidence_interval(
        self,
        runs: list[KeywordRun],
        k: int,
        predicate: Callable[[KeywordRun], bool] | None = None,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """Computes the Wilson score confidence interval for the trial success rate (Story 6.3 D-1).

        [Tier 1 — Deterministic] — Wilson score interval at the given
        ``confidence`` level for the latent per-trial success probability.
        Returns ``(ci_lower, ci_upper)`` tuple of ``float`` in ``[0, 1]``.
        Paired with `Stat.Get Pass At K` — the scalar point estimate plus
        this CI together satisfy epic AC-2's "Pass@k with confidence
        interval" promise.

        | =Arguments= | =Description= |
        | ``runs`` | ``list[KeywordRun]`` — typically the result of `Stat.Run N Times`. |
        | ``k`` | Top-k parameter. Validated for ``1 <= k <= len(runs)`` but only used for sanity check — the Wilson interval is on the underlying success proportion, not on the Pass@k estimate itself. |
        | ``predicate`` | Optional ``Callable[[KeywordRun], bool]`` for pass/fail classification. Same default as `Stat.Get Pass At K`. |
        | ``confidence`` | Confidence level in ``(0, 1)``. Defaults to ``0.95``. |

        Raises ``ValueError`` when ``k`` is non-positive or ``k > n`` (with
        ``n > 0`` — empty ``runs`` is permitted per the Wilson formula).

        Example:
        | @{runs} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
        | ${ci_lo}    ${ci_hi} =    `Stat.Get Pass At K Confidence Interval`    ${runs}    k=5
        | Should Be True    0.0 <= ${ci_lo} <= ${ci_hi} <= 1.0                      # CI bounds are well-formed probabilities.
        | ${ci99_lo}    ${ci99_hi} =    `Stat.Get Pass At K Confidence Interval`    ${runs}    k=5    confidence=0.99
        | Should Be True    (${ci99_hi} - ${ci99_lo}) >= (${ci_hi} - ${ci_lo})      # Higher confidence → wider interval.

        Notes:
        - Story 6.3 D-1 resolution: scalar Pass@k vs CI separated to preserve AssertionEngine compatibility on the point estimate.
        - PRD FR27 covers Pass@k; CI is an epic-AC-2 extension.
        - Sibling keyword: `Stat.Get Pass At K` for the scalar point estimate.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        predicate_fn = predicate if predicate is not None else _internal._default_pass_predicate
        c = sum(1 for r in runs if predicate_fn(r))
        n = len(runs)
        # Story 6.3 code-review MED Wilson-k fix (Codex MED-7 + Edge MED-11 2-way):
        # validate `k` unconditionally regardless of `n` value. Pre-edit
        # short-circuited validation when `n=0`, silently returning `(0.0, 1.0)`
        # for invalid k values like `k=-5` or `k=99`.
        if k < 1:
            raise ValueError(f"k must be positive; got {k!r}")
        if n > 0 and k > n:
            raise ValueError(f"k must be <= n; got k={k!r} n={n!r}")
        return _internal._compute_wilson_ci(c, n, confidence)

    # ----------------------------------------------------------------- #
    # FR31a — Stat.Assert Run Determinism (Tier-1)                      #
    # ----------------------------------------------------------------- #

    @keyword(name="Stat.Assert Run Determinism")
    @tier(1)
    def assert_run_determinism(
        self,
        keyword: str | Callable[..., Any],
        keyword_args: dict[str, Any] | list[Any] | None = None,
        expect: str = "byte_identical",
    ) -> None:
        """Asserts bit-identical output across 2 invocations of a Tier-1 keyword (PRD FR31a).

        [Tier 1 — Deterministic] — invokes the wrapped keyword twice with
        identical inputs and compares via deep-equality. The bit-identical
        guarantee is scoped to Tier-1 keywords only (FR31a contract); the
        keyword raises ``TierViolationError`` if a Tier-2/3 keyword is
        passed.

        | =Arguments= | =Description= |
        | ``keyword`` | RF keyword name (``str``) OR callable. Same dispatch rules as `Stat.Run N Times` (string form requires active RF context). |
        | ``keyword_args`` | Optional ``dict`` of kwargs OR ``list`` of RF named-arg strings. |
        | ``expect`` | Comparison mode. Phase-1 supports ``"byte_identical"`` only; ``"approximate"`` + ``"schema_identical"`` deferred to Phase-2. |

        Raises ``ValueError`` when ``expect != "byte_identical"`` (Phase-1
        scope). Raises ``TierViolationError`` when the wrapped keyword is
        not Tier-1 — FR31a is scoped to Tier-1 only. Raises
        ``AssertionError`` on output mismatch with a ``redact()``-scrubbed
        diff per FR38a credential-safety contract.

        Example:
        | `Stat.Assert Run Determinism`    keyword=Get Keyword Tier    keyword_args=${{['Send Prompt']}}
        | `Stat.Assert Run Determinism`    keyword=Get Effective Config
        | Run Keyword And Expect Error    TierViolationError*    `Stat.Assert Run Determinism`    keyword=Send Prompt

        Notes:
        - PRD FR31a ratifies the bit-identical guarantee for Tier-1 keywords; Tier-2/3 keywords are stochastic by tier definition + must use `Stat.Run N Times` + `Stat.Get Pass At K` for statistical assertions instead.
        - Diff redaction per FR38a + Story 5.3 — credentials in args / output don't leak into RF logs.
        - Story 6.3 ratifies ``"byte_identical"`` as the Phase-1 contract; ``"approximate"`` + ``"schema_identical"`` are Phase-2 work-items.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if expect != "byte_identical":
            raise ValueError(
                f"expect must be 'byte_identical' in Phase-1; got {expect!r}. "
                f"Other modes (approximate, schema_identical) deferred to Phase-2."
            )
        positional, named = _internal._normalize_keyword_args(keyword_args)
        callable_ref: Callable[..., Any]
        kw_name: str
        if isinstance(keyword, str):
            kw_name = keyword
            from robot.libraries.BuiltIn import BuiltIn

            builtin = BuiltIn()
            kw_tier = _resolve_keyword_tier_by_name(kw_name, builtin)
            # Story 6.3 code-review HIGH-α fix (4-way Codex empirical + Blind +
            # Edge + Auditor): pre-edit `if kw_tier is not None and kw_tier != 1`
            # silently admitted unknown-tier keywords. Now `None` raises too —
            # unresolved tier is treated as a TierViolationError per FR31a
            # "bit-identical guarantee scoped to Tier-1 only" — we cannot
            # guarantee anything for keywords we can't resolve.
            if kw_tier != 1:
                actual = f"tier {kw_tier}" if kw_tier is not None else "unresolved (tier annotation not found)"
                raise TierViolationError(
                    f"Stat.Assert Run Determinism: keyword {kw_name!r} is {actual}; "
                    f"bit-identical only guaranteed for Tier-1 (FR31a)."
                )

            # Story 6.3 code-review HIGH-γ fix (Codex empirical): use varargs form.
            def callable_ref_impl(*pos: Any, **kw: Any) -> Any:
                rf_args: list[Any] = list(pos)
                for k, v in kw.items():
                    rf_args.append(f"{k}={v}")
                return builtin.run_keyword(kw_name, *rf_args)

            callable_ref = callable_ref_impl
        else:
            callable_ref = keyword
            # Story 6.3 code-review HIGH-δ fix (Codex + Blind + Auditor 3-way):
            # `find_tier_through_wrappers` walks the decorator chain so
            # `@tier`-annotated wrapped methods are detected.
            from AgentEval._kernel.tier import find_tier_through_wrappers

            target = getattr(keyword, "__func__", keyword)
            kw_name = str(getattr(target, "robot_name", None) or getattr(keyword, "__name__", repr(keyword)))
            kw_tier = find_tier_through_wrappers(target)
            # Story 6.3 code-review HIGH-α fix (4-way): callable-form likewise
            # raises on unresolved tier (was silent bypass pre-edit).
            if kw_tier != 1:
                actual = f"tier {kw_tier}" if kw_tier is not None else "unresolved (no @tier annotation)"
                raise TierViolationError(
                    f"Stat.Assert Run Determinism: keyword {kw_name!r} is {actual}; "
                    f"bit-identical only guaranteed for Tier-1 (FR31a)."
                )

        result_1 = callable_ref(*positional, **named)
        result_2 = callable_ref(*positional, **named)
        if not _byte_identical(result_1, result_2):
            # Truncate diff per FR34b (1000-char convention) + redact per FR38a.
            diff_repr = f"result_1={result_1!r}\nresult_2={result_2!r}"
            if len(diff_repr) > 1000:
                diff_repr = diff_repr[:1000] + "...(truncated)"
            raise AssertionError(
                redact(
                    f"Stat.Assert Run Determinism: bit-identical guarantee violated for "
                    f"keyword={kw_name!r}.\n{diff_repr}"
                )
            )

    # ----------------------------------------------------------------- #
    # FR29a/b/c — Phase-2 advanced statistical primitives (Story 13.1)  #
    # Behind `[agenteval-advanced]` optional extra (scipy + numpy).     #
    # ----------------------------------------------------------------- #

    @keyword(name="Stat.Mann Whitney U")
    @tier(1)
    def compute_mann_whitney_u(
        self,
        runs_a: list[KeywordRun],
        runs_b: list[KeywordRun],
        predicate: Callable[[KeywordRun], float] | None = None,
    ) -> MannWhitneyResult:
        """Computes the two-sided Mann-Whitney U test on two independent run samples (PRD FR29a; Story 13.1).

        [Tier 1 — Deterministic] — closed-form non-parametric test for
        whether two independent samples were drawn from the same
        distribution. Returns ``MannWhitneyResult`` with U statistic,
        two-sided p-value, rank-biserial effect size, and sample sizes.

        Requires the ``[agenteval-advanced]`` optional extra (scipy + numpy);
        raises ``ImportError`` when invoked without it. The ``StatsLibrary``
        class itself remains importable without the extra; only this Phase-2
        keyword method raises on invocation.

        | =Arguments= | =Description= |
        | ``runs_a`` | ``list[KeywordRun]`` — first sample (typically the result of `Stat.Run N Times` against flow A). |
        | ``runs_b`` | ``list[KeywordRun]`` — second sample (typically the result of `Stat.Run N Times` against flow B). |
        | ``predicate`` | REQUIRED ``Callable[[KeywordRun], float]`` value-extractor producing the numeric quantity to compare (e.g., ``lambda r: r.latency_seconds``). Default ``None`` raises ``ValueError`` — no sensible default numeric metric across all ``KeywordRun`` shapes. NOTE: distinct from `Stat.Get Pass At K`'s boolean predicate. |

        Raises ``ImportError`` when scipy/numpy are unavailable (missing
        ``[agenteval-advanced]`` extra). Raises ``ValueError`` when
        ``predicate`` is ``None`` OR when either ``runs_a`` / ``runs_b`` is
        empty.

        Example:
        | @{runs_a} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=claude_code_cli']}}
        | @{runs_b} =    `Stat.Run N Times`    n=20    keyword=Send Prompt    keyword_args=${{['adapter=codex_cli']}}
        | ${cost_pred} =    Evaluate    lambda r: r.result.cost_usd
        | ${mwu} =    `Stat.Mann Whitney U`    ${runs_a}    ${runs_b}    predicate=${cost_pred}
        | Should Be True    ${mwu.p_value} < 0.05                                  # Reject the null at α=0.05.
        | Should Be True    abs(${mwu.effect_size_r}) > 0.3                        # Medium-or-larger effect.

        Notes:
        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
        - PRD FR29a ratifies the ``MannWhitneyResult`` dataclass with ``u_statistic`` / ``p_value`` / ``effect_size_r`` + ``n_a`` / ``n_b``.
        - Math reference: ``scipy.stats.mannwhitneyu(alternative="two-sided", use_continuity=False)``. The returned ``p_value`` matches scipy exactly; the returned ``u_statistic`` is normalized to ``min(U1, U2)`` (smaller-U canonical form) and does NOT match scipy's ``.statistic`` directly — scipy returns ``U1``. Consumers needing scipy's U1 can recover it via ``U1 = (1 + effect_size_r) * n_a * n_b / 2``.
        - Effect size: signed rank-biserial ``r = 2*U1/(n_a*n_b) - 1`` (where U1 is the M-W U for samples_a); positive r → samples_a tends to be larger; matches ``Stat.Cliff Delta`` sign convention.
        - One-sided variants (``alternative="greater"``/``"less"``) deferred to Phase-2 (DF-13.1-S1).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if not _ADVANCED_AVAILABLE:
            _raise_advanced_extra_missing("Mann Whitney U")
        if predicate is None:
            raise ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")
        # Import lazily so the keyword method body owns the import attempt.
        from AgentEval.stats import mannwhitney as _mannwhitney

        samples_a = [float(predicate(r)) for r in runs_a]
        samples_b = [float(predicate(r)) for r in runs_b]
        return _mannwhitney.compute_mann_whitney_u(samples_a, samples_b)

    @keyword(name="Stat.Cliff Delta")
    @tier(1)
    def compute_cliff_delta(
        self,
        runs_a: list[KeywordRun],
        runs_b: list[KeywordRun],
        predicate: Callable[[KeywordRun], float] | None = None,
    ) -> float:
        """Computes Cliff's delta non-parametric effect size between two run samples (PRD FR29b; Story 13.1).

        [Tier 1 — Deterministic] — closed-form Cliff (1993) brute-force
        formula. Returns ``float ∈ [-1.0, 1.0]``. Positive values indicate
        ``runs_a`` tends to produce larger values; negative values indicate
        ``runs_b`` tends to produce larger values.

        Requires the ``[agenteval-advanced]`` optional extra.

        | =Arguments= | =Description= |
        | ``runs_a`` | ``list[KeywordRun]`` — first sample. |
        | ``runs_b`` | ``list[KeywordRun]`` — second sample. |
        | ``predicate`` | REQUIRED ``Callable[[KeywordRun], float]`` value-extractor. ``None`` raises ``ValueError``. |

        Raises ``ImportError`` when scipy/numpy unavailable; ``ValueError``
        when ``predicate`` is ``None`` OR either sample is empty.

        Example:
        | ${latency_pred} =    Evaluate    lambda r: r.latency_seconds
        | ${delta} =    `Stat.Cliff Delta`    ${runs_a}    ${runs_b}    predicate=${latency_pred}
        | Should Be True    abs(${delta}) > 0.474                                  # Large effect per Romano-Coraggio-Smith conventions.

        Notes:
        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
        - PRD FR29b ratifies the scalar ``float`` return type (NOT a dataclass) — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.
        - Math: ``δ = (#{a>b} - #{a<b}) / (n_a * n_b)``; ties contribute 0.
        - Complexity: ``O(n_a * n_b)``. Fine for typical n ≤ 100 trials; Phase-2 perf carve-out for n_a + n_b > 1000.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if not _ADVANCED_AVAILABLE:
            _raise_advanced_extra_missing("Cliff Delta")
        if predicate is None:
            raise ValueError("predicate is required; pass a Callable[[KeywordRun], float] value-extractor")
        from AgentEval.stats import cliffs_delta as _cliffs_delta

        samples_a = [float(predicate(r)) for r in runs_a]
        samples_b = [float(predicate(r)) for r in runs_b]
        return _cliffs_delta.compute_cliff_delta(samples_a, samples_b)

    @keyword(name="Stat.Bootstrap Confidence Interval")
    @tier(1)
    def compute_bootstrap_ci(
        self,
        samples: list[KeywordRun] | list[float],
        seed: int,
        statistic: Callable[[list[float]], float] | None = None,
        predicate: Callable[[KeywordRun], float] | None = None,
        alpha: float = 0.05,
        n_resamples: int = 10_000,
    ) -> tuple[float, float]:
        """Computes a percentile bootstrap confidence interval for any statistic (PRD FR29c; Story 13.1).

        [Tier 1 — Deterministic] — given fixed ``samples`` + ``seed``, the
        result is bit-identical across calls (FR31a guarantee). Returns
        ``(ci_lower, ci_upper)`` tuple at the ``(1 - alpha) * 100%`` percentile
        level (default 95% CI).

        Requires the ``[agenteval-advanced]`` optional extra.

        | =Arguments= | =Description= |
        | ``samples`` | Either ``list[KeywordRun]`` (then ``predicate`` extracts floats) OR ``list[float]`` (predicate ignored). Mixed-type lists raise ``TypeError`` — homogeneous types required. |
        | ``seed`` | REQUIRED ``int`` seed for the numpy ``Generator``. No default — the ``@tier(1)`` bit-identical guarantee (FR31a) requires a fixed seed. Operators wanting OS-entropy randomness must pass an explicit seed (e.g., ``seed=random.randrange(2**32)``). |
        | ``statistic`` | ``Callable[[list[float]], float]`` whose CI is computed. Default ``None`` → ``statistics.mean``. |
        | ``predicate`` | Optional ``Callable[[KeywordRun], float]`` value-extractor (required when ``samples`` is ``list[KeywordRun]``). |
        | ``alpha`` | Significance level; CI is at ``(1-alpha)*100%`` confidence. Must satisfy ``0.0 < alpha < 1.0``. Default ``0.05``. |
        | ``n_resamples`` | Number of bootstrap resamples (with replacement). Must be ``>= 100``. Default ``10_000``. |

        Raises ``ImportError`` when scipy/numpy unavailable; ``ValueError``
        when ``samples`` is empty / ``alpha`` is out of range / ``n_resamples
        < 100`` / ``predicate`` is missing for a ``list[KeywordRun]`` input.
        Raises ``TypeError`` when ``samples`` mixes ``KeywordRun`` and raw
        floats (homogeneous types required).

        Example:
        | @{runs} =    `Stat.Run N Times`    n=50    keyword=Send Prompt    keyword_args=${{['adapter=mock']}}
        | ${cost_pred} =    Evaluate    lambda r: r.result.cost_usd
        | ${ci_lo}    ${ci_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    seed=42    predicate=${cost_pred}
        | Should Be True    ${ci_lo} <= ${ci_hi}                                    # CI bounds well-ordered.
        | ${median_stat} =    Evaluate    statistics.median    modules=statistics
        | ${med_lo}    ${med_hi} =    `Stat.Bootstrap Confidence Interval`    ${runs}    seed=42    statistic=${median_stat}    predicate=${cost_pred}

        Notes:
        - Story 13.1 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra.
        - PRD FR29c ratifies the ``(lo, hi)`` tuple return type — preserves AssertionEngine matcher compatibility per Story 6.3 D-1 precedent.
        - Method: percentile bootstrap. BCa + BC-corrected variants deferred to Phase-2 (DF-13.1-S2).
        - Math reference: ``scipy.stats.bootstrap(samples, statistic, rng=numpy.random.default_rng(seed), method="percentile")``. The local implementation uses the same ``numpy.random.default_rng(seed)`` source so reference equivalence is verifiable.
        - Mandatory ``seed`` preserves the ``@tier(1)`` FR31a bit-identical guarantee (Story 13.1 code-review HIGH-C catch, Opus tier review).
        - Resampling result determinism is pinned to a single ``numpy.random.Generator`` algorithm (PCG64). Major numpy ABI changes that retire PCG64 would shift CI bounds; track via ``_TESTED_UP_TO``-style pinning in Phase-2 if numpy 3.x ships a different default generator.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if not _ADVANCED_AVAILABLE:
            _raise_advanced_extra_missing("Bootstrap Confidence Interval")
        import statistics as _statistics

        from AgentEval.stats import bootstrap as _bootstrap

        if statistic is None:
            statistic = _statistics.mean
        # Determine if samples are KeywordRun (need predicate) or raw floats.
        if not samples:
            raise ValueError("samples must be non-empty")
        # Validate homogeneity up-front per Story 13.1 code-review Codex MED-1
        # catch: silently filtering mixed-type elements produced wrong CIs
        # without raising. Reject the mix at the boundary.
        kw_count = sum(1 for s in samples if isinstance(s, KeywordRun))
        if kw_count not in (0, len(samples)):
            raise TypeError(
                "samples must be a homogeneous list[KeywordRun] OR list[float]; "
                f"got mixed types ({kw_count} KeywordRun + {len(samples) - kw_count} non-KeywordRun)"
            )
        numeric_samples: list[float]
        if kw_count > 0:
            if predicate is None:
                raise ValueError(
                    "predicate is required when samples is list[KeywordRun]; "
                    "pass a Callable[[KeywordRun], float] value-extractor"
                )
            numeric_samples = [float(predicate(r)) for r in samples if isinstance(r, KeywordRun)]
        else:
            numeric_samples = [float(s) for s in samples if not isinstance(s, KeywordRun)]
        return _bootstrap.compute_bootstrap_ci(
            numeric_samples,
            statistic,
            alpha,
            n_resamples,
            seed,
        )


def _byte_identical(a: Any, b: Any) -> bool:
    """Story 6.3 code-review HIGH-ο fix (Blind): NaN-aware equality.

    Python `==` on `float('nan')` returns False, breaking the bit-identical
    guarantee for any Tier-1 keyword returning NaN. This helper does
    structural equality with `math.isnan` short-circuit. For non-float
    values, falls back to `==`. Handles nested containers via recursion.
    """
    import math

    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b
    if type(a) is not type(b):
        # Differing types still allow Python `==` to handle numeric coercion
        # but reject for sequence/dict mismatches.
        return bool(a == b)
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_byte_identical(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_byte_identical(x, y) for x, y in zip(a, b, strict=True))
    return bool(a == b)


def _resolve_keyword_tier_by_name(kw_name: str, builtin: Any) -> int | None:
    """Look up the `_agenteval_tier` for an RF-named keyword via `BuiltIn`.

    Story 6.3 code-review HIGH-δ fix (Codex + Blind + Auditor): walks the
    DynamicCore-composed `keywords` registry (not `dir(lib)` which only
    enumerates direct attrs) + unwraps decorator chains with `inspect.unwrap`
    so wrapped `@tier`-annotated methods are detected.

    Returns the tier int when found + annotated, or `None` when the keyword
    is unknown OR its method has no `@tier` annotation.
    """
    from AgentEval._kernel.tier import find_tier_through_wrappers

    try:
        lib = builtin.get_library_instance("AgentEval")
    except Exception:
        return None
    # DynamicCore `self.keywords` is the canonical {name: bound_method} registry.
    kw_map = getattr(lib, "keywords", None)
    if isinstance(kw_map, dict) and kw_name in kw_map:
        bound = kw_map[kw_name]
        target = getattr(bound, "__func__", bound)
        return find_tier_through_wrappers(target)
    # Fallback: walk direct attrs (some sub-libraries may register outside DynamicCore).
    for attr_name in dir(lib):
        if attr_name.startswith("_"):
            continue
        attr = getattr(lib, attr_name, None)
        target = getattr(attr, "__func__", attr) if attr is not None else None
        if target is None:
            continue
        if getattr(target, "robot_name", None) == kw_name:
            return find_tier_through_wrappers(target)
    return None
