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

"""Unit tests for `KeywordRun` frozen dataclass (Story 6.3 AC-6.3.2)."""

from __future__ import annotations

import dataclasses

import pytest

from AgentEval.stats.types import KeywordRun


def test_keyword_run_is_frozen() -> None:
    """`@dataclass(frozen=True)` — mutation raises FrozenInstanceError."""
    run = KeywordRun(
        trial_index=0,
        test_id="t::trial-0",
        keyword_name="kw",
        result=None,
        error=None,
        completeness="full",
        latency_seconds=0.0,
        seed=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.trial_index = 1  # type: ignore[misc]


def test_keyword_run_uses_slots() -> None:
    """`slots=True` — cannot add new attributes (raises TypeError or AttributeError
    depending on Python's frozen+slots interaction)."""
    run = KeywordRun(
        trial_index=0,
        test_id="t::trial-0",
        keyword_name="kw",
        result=None,
        error=None,
        completeness="full",
        latency_seconds=0.0,
        seed=None,
    )
    with pytest.raises((AttributeError, TypeError)):
        run.new_attr = "x"  # type: ignore[attr-defined]
