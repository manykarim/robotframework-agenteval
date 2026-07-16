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

__version__ = "0.0.1"
__all__: list[str] = []
