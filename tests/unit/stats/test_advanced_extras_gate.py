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

"""ImportError-gate tests for the Phase-2 `[agenteval-advanced]` stats keywords.

This file deliberately does NOT carry `pytest.importorskip("scipy")` at the
top so the tests run in BOTH the WITH-extras and WITHOUT-extras CI environments
(Story 13.1 code-review Codex HIGH-1 catch: the math + happy-path tests in
`test_advanced.py` are correctly gated by `importorskip` but the gate-coverage
tests must run unconditionally to verify the Phase-1 base-env compat
guarantee).

Per the spec (AC-13.1.5 + epics.md L2153): `StatsLibrary` itself MUST be
importable WITHOUT scipy/numpy installed; only the 3 Phase-2 keyword methods
raise `ImportError` on invocation.
"""

from __future__ import annotations

import statistics

import pytest

from AgentEval.stats.types import KeywordRun


def _make_run(value: float, *, trial_index: int = 0) -> KeywordRun:
    """Construct a minimal `KeywordRun` carrying `value` in `latency_seconds`."""
    return KeywordRun(
        trial_index=trial_index,
        test_id=f"gate::trial-{trial_index}",
        keyword_name="fake",
        result=None,
        error=None,
        completeness="complete",
        latency_seconds=value,
        seed=None,
    )


def test_statslibrary_importable_without_extra() -> None:
    """`StatsLibrary` class itself must import cleanly without scipy/numpy."""
    from AgentEval.stats.library import StatsLibrary

    # Construction must succeed.
    lib = StatsLibrary()
    assert lib is not None


def test_raise_advanced_extra_missing_helper_carries_canonical_message() -> None:
    """`_raise_advanced_extra_missing` produces the spec-mandated ImportError text.

    Per Story 13.1 D-3 + epics.md L2153: the message MUST include both the
    keyword name and the verbatim install hint
    `uv pip install robotframework-agenteval[agenteval-advanced]`.
    """
    from AgentEval.stats.library import _raise_advanced_extra_missing

    for kw in ("Mann Whitney U", "Cliff Delta", "Bootstrap Confidence Interval"):
        with pytest.raises(ImportError) as exc_info:
            _raise_advanced_extra_missing(kw)
        msg = str(exc_info.value)
        assert f"Stat.{kw}" in msg
        assert "agenteval-advanced" in msg
        assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg


def test_phase2_keywords_raise_import_error_when_extra_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All 3 Phase-2 keywords raise ImportError when `_ADVANCED_AVAILABLE = False`.

    Monkeypatches the module-level gate directly. Runs in both WITH-extras and
    WITHOUT-extras CI environments (no top-level `importorskip` in this file).
    """
    from AgentEval.stats import library as lib_mod

    monkeypatch.setattr(lib_mod, "_ADVANCED_AVAILABLE", False)
    lib = lib_mod.StatsLibrary()

    with pytest.raises(ImportError, match="agenteval-advanced"):
        lib.compute_mann_whitney_u(
            [_make_run(1.0)],
            [_make_run(2.0)],
            predicate=lambda r: r.latency_seconds,
        )

    with pytest.raises(ImportError, match="agenteval-advanced"):
        lib.compute_cliff_delta(
            [_make_run(1.0)],
            [_make_run(2.0)],
            predicate=lambda r: r.latency_seconds,
        )

    with pytest.raises(ImportError, match="agenteval-advanced"):
        lib.compute_bootstrap_ci(
            [1.0, 2.0, 3.0, 4.0, 5.0] * 10,
            seed=42,
            statistic=statistics.mean,
            n_resamples=200,
        )
