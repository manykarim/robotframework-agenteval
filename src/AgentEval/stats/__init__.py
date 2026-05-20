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

"""AgentEval.stats sub-package.

Statistical primitives per PRD FR26 / FR27 / FR31a, shipped by Story 6.3:

- `library.py` — `StatsLibrary` with 4 `@keyword + @tier(N)` methods:
  `Stat.Run N Times` (Tier-3 fan-out), `Stat.Get Pass At K` (Tier-1),
  `Stat.Get Pass At K Confidence Interval` (Tier-1 paired getter per
  Story 6.3 D-1 resolution), `Stat.Assert Run Determinism` (Tier-1 FR31a).
- `_internal.py` — pure helpers (`_dispatch_trial`, `_compute_pass_at_k`,
  `_normalize_keyword_args`, `_default_pass_predicate`, `_compute_wilson_ci`).
- `types.py` — `KeywordRun` frozen dataclass (PRD FR26 verbatim return-type
  element per `docs/contracts/determinism-contract.md:55`).
- `wilson.py` — pure-stdlib Wilson score interval (no SciPy dep per
  architecture L1308).

Per Story 2.1 sub-library `__init__.py` discipline: NO re-exports here;
the `StatsLibrary` class is loaded by `AgentEval/__init__.py:_SUB_LIBRARIES`
through `importlib.import_module("AgentEval.stats.library")` directly.
"""
