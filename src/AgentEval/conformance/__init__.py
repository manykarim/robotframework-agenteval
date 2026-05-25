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

"""Conformance reporting CLI (Story 8a.2 FR57).

`python -m AgentEval.conformance --adapter <name>` discovers conformance
fixtures + executes them against the configured adapter + emits a JSON
report + Markdown summary per the schema documented at
``docs/contracts/conformance-fixture-format.md``.

Phase-1 ships the standalone CLI only; the listener-variable trigger path
(`robot --variable conformance_report:json+human tests/`) is deferred to
Phase-1.5 (DF-8a.2-S1 / C63).
"""

from AgentEval.conformance.cli import main

__all__ = ["main"]
