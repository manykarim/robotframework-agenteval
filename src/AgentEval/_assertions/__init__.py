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

"""AgentEval._assertions sub-package.

agenteval's assertion library + AssertionEngine adapter:

- `library.py` (Story 6.2) — `AssertionsLibrary` with 5 `Should *` keywords
  (Trajectory / ToolCall / AgentResponse evidence-layer assertions per PRD
  FR23a/FR23b/FR24/FR25).
- `_internal.py` (Story 6.2) — 7 pure matching helpers consumed by
  `library.py`.
- `adapter.py` (Story 6.3) — `assert_value()` free function with three
  fail-fast gates (FR28 polling-ban + FR43 validate-gate + AssertionEngine
  dispatch per ADR-019).

Per Story 2.1 sub-library discipline: NO re-exports here; the
`AssertionsLibrary` class is loaded by `AgentEval/__init__.py:_SUB_LIBRARIES`
through `importlib.import_module("AgentEval._assertions.library")`. The
`adapter.assert_value()` function is imported directly by consumers.
"""
