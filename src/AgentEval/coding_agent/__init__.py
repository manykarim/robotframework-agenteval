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

"""AgentEval.coding_agent sub-package.

Contributor-facing imports per ADR-003 + ADR-005:

    from AgentEval.coding_agent import (
        CodingAgentAdapter,    # Protocol (declared in AgentEval.types per architecture L853)
        InProcessAdapter,      # Concrete-by-default base for SDK-driven adapters (no abstract hooks per ADR-003 L22-23)
        SubprocessAdapter,     # ABC for CLI-driven adapters (3-hook template-method per ADR-003 L24-29)
        AgentRunResult,        # Normalized run-result dataclass (declared in AgentEval.types)
    )

Concrete adapter implementations land in Epic 4 (Generic LiteLLM + Claude
Code CLI) + Epic 10 (Claude Agent SDK + OpenAI Agents SDK) + Epic 11 (Codex
CLI + Copilot CLI) per ADR-005's "≤2 adapters per vendor + 1 universal
escape hatch" rule.
"""

from AgentEval.coding_agent.base import (
    AgentRunResult,
    CodingAgentAdapter,
    InProcessAdapter,
    SubprocessAdapter,
)

__all__ = [
    "CodingAgentAdapter",
    "InProcessAdapter",
    "SubprocessAdapter",
    "AgentRunResult",
]
