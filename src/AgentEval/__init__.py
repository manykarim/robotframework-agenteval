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

"""robotframework-agenteval - test the agentic stack with Robot Framework.

Four libraries, imported à la carte - test MCP servers, Agent Skills,
SubAgents, and Hooks deterministically, with an LLM judge, or by driving a
real coding agent:

    *** Settings ***
    Library    MCPLibrary
    Library    SkillsLibrary
    Library    SubagentsLibrary
    Library    HooksLibrary

Each library rides the shared ``AgentEval._core`` spine (tier marker, adapter
seam, judge, stats, trace). This ``AgentEval`` package is that spine's home; a
thin ``Library AgentEval`` composite that bundles all four for one-import
convenience lands with the packaging pass.
"""

from __future__ import annotations

from robotlibcore import DynamicCore

# The stable, public entrypoint to the adapter seam. `_core` is internal (see
# docs/contracts/stability-surface.md); re-export the factory + protocol here so
# docs, tests, and the Agent.* keywords depend on `AgentEval.get_adapter`, not the
# unstable path. The heavy LLM/agent extras stay lazily imported inside `run()`,
# so this re-export adds no import cost.
from AgentEval._core.adapter import Adapter, get_adapter

__version__ = "0.0.1"
__all__ = ["AgentEval", "Adapter", "get_adapter"]


class AgentEval(DynamicCore):  # type: ignore[misc]
    """The optional one-import composite - every surface keyword in one library.

    Prefer importing only what you test (``Library MCPLibrary``); reach for this
    when you want them all at once:

    | *** Settings ***  |
    | Library    AgentEval |
    """

    def __init__(self) -> None:
        # Imported lazily so `import AgentEval` (and the spine) stays cheap and
        # circular-import-free - the surfaces only load when you use the composite.
        from HooksLibrary import HooksLibrary
        from MCPLibrary import MCPLibrary
        from SkillsLibrary import SkillsLibrary
        from SubagentsLibrary import SubagentsLibrary

        DynamicCore.__init__(
            self,
            [HooksLibrary(), MCPLibrary(), SkillsLibrary(), SubagentsLibrary()],
        )
