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

"""Unit tests for top-level `Get Keyword Tier` (Story 6.3 AC-6.3.7)."""

from __future__ import annotations

import pytest

from AgentEval import AgentEval


def test_get_keyword_tier_returns_tier_1_for_tier_1_keyword() -> None:
    lib = AgentEval()
    assert lib.get_keyword_tier("Get Effective Config") == 1


def test_get_keyword_tier_returns_tier_3_for_stat_run_n_times() -> None:
    """Per Story 6.3 D-14 amendment: Stat.Run N Times is Tier-3 (architecture L380)."""
    lib = AgentEval()
    assert lib.get_keyword_tier("Stat.Run N Times") == 3


def test_get_keyword_tier_returns_tier_1_for_stat_get_pass_at_k() -> None:
    lib = AgentEval()
    assert lib.get_keyword_tier("Stat.Get Pass At K") == 1


def test_get_keyword_tier_returns_tier_1_for_assert_run_determinism() -> None:
    lib = AgentEval()
    assert lib.get_keyword_tier("Stat.Assert Run Determinism") == 1


def test_get_keyword_tier_unknown_keyword_raises() -> None:
    lib = AgentEval()
    with pytest.raises(ValueError, match=r"not found in AgentEval library"):
        lib.get_keyword_tier("Does Not Exist")


def test_get_keyword_tier_works_on_composed_sub_library_keyword() -> None:
    """Verifies the DynamicCore-composed walker finds keywords from sub-libraries."""
    lib = AgentEval()
    # Tool Call Should Have Occurred is shipped by AssertionsLibrary (Story 6.2).
    assert lib.get_keyword_tier("Tool Call Should Have Occurred") == 1
