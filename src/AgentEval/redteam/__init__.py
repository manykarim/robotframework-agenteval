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

"""Red-team probe capability (add-red-team-probes).

DEFENSIVE, single-turn adversarial-robustness testing of a coding agent the
operator OWNS. Ships a curated, versioned probe pack (``prompt_injection`` /
``jailbreak`` / ``pii_leakage`` / ``encoding_obfuscation``), refusal detection
(pattern / judge / both), and an attack-success-rate metric derived from the
existing Pass@k / Wilson fan-out machinery. This is NOT an offensive tool: it
measures whether an agent RESISTS injection, jailbreak, PII-leakage, and
encoding-obfuscation attacks. Multi-turn / Crescendo attacks are DEFERRED (they
build on ``add-multi-turn-conversation-testing``'s ``Simulate User``).

The retired ``security/`` sandbox stubs (0 callers) were removed by the
``remove-dead-machinery`` change; this package is the functional successor.
"""

from __future__ import annotations

__all__ = ["RedTeamLibrary"]


def __getattr__(name: str) -> object:
    # Lazy re-export so `from AgentEval.redteam import RedTeamLibrary` works
    # without importing the (robot-dependent) library module at package import.
    if name == "RedTeamLibrary":
        from AgentEval.redteam.library import RedTeamLibrary

        return RedTeamLibrary
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
