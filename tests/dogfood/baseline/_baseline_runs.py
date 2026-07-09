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

"""RF helper: build controlled KeywordRun lists for the baseline dogfood.

Lets the dogfood exercise the FAIL / PASS-with-warning bands deterministically
(the Mock provider always returns ``completeness="complete"``, so a real
mock-driven run can only demonstrate the no-regression band).
"""

from __future__ import annotations

from robot.api.deco import keyword, library

from AgentEval.stats.types import KeywordRun


@library(scope="GLOBAL")
class _BaselineRuns:
    @keyword("Make Keyword Runs")
    def make_keyword_runs(self, successes: int, trials: int) -> list[KeywordRun]:
        successes = int(successes)
        trials = int(trials)
        return [
            KeywordRun(
                trial_index=i,
                test_id=f"dogfood::trial-{i}",
                keyword_name="Send Prompt",
                result=None,
                error=None,
                completeness="complete" if i < successes else "partial",
                latency_seconds=0.10 + 0.001 * i,
                seed=None,
            )
            for i in range(trials)
        ]
