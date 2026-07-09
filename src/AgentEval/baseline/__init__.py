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

"""Regression baseline tracking (OpenSpec ``add-regression-baseline-tracking``).

Public package (no leading underscore — the models are part of the stability
surface). Composes into the top-level ``AgentEval`` library via
``_SUB_LIBRARIES`` and is importable standalone
(``Library    AgentEval.baseline.library.BaselineLibrary``).

Per Story 2.1 sub-library discipline, ``__init__`` re-exports only the public
``BaselineLibrary`` class + the public dataclasses named on the stability
surface; internal helpers stay in their modules.
"""

from __future__ import annotations

from AgentEval.baseline.models import (
    ContinuousEvidence,
    MetricComparison,
    MetricsBaseline,
    ProportionEvidence,
    RegressionReport,
    RunContext,
    TrendGrid,
    TrendPoint,
    TrendSeries,
)

__all__ = [
    "ContinuousEvidence",
    "MetricComparison",
    "MetricsBaseline",
    "ProportionEvidence",
    "RegressionReport",
    "RunContext",
    "TrendGrid",
    "TrendPoint",
    "TrendSeries",
]
