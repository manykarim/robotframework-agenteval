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

"""Cohort-heatmap rendering (Story 8b.2 / FR55-ASCII + dict).

Public surface:
    - ``AgentEval._heatmap.models.CohortHeatmap`` — frozen dataclass with
      ``.as_ascii()`` + ``.as_dict()``.
    - ``AgentEval._heatmap.library.HeatmapLibrary`` — RF library exposing
      ``Get Cohort Heatmap``.

Phase-1 ships **single-model** heatmap input (``DiscoverabilityResult``
from Story 4.4). Multi-model cohort comparison (rows = tasks,
columns = models, cells = Pass@k) is Phase-2 / Epic 13.

The package init does NOT re-export the public names — direct submodule
imports avoid the eager-import-circular-dependency footgun (Story 2.1
code-review pattern; the same conventions-test loader that surfaces the
issue would crash if we re-exported here).
"""
