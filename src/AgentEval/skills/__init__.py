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

"""AgentEval.skills sub-package.

Skill sub-library: static-inspection keywords for skill `.md` files
(PRD FR1 + Epic 2 Story 2.1). Re-exports `SkillsLibrary` for the
top-level `AgentEval` `DynamicCore` composition + advanced consumers
who import the sub-library directly (`Library AgentEval.skills.library
WITH NAME Skill`).

Phase-2 + Epic 7 add the FR4 model-API-key-gated activation decision
(`Get Activation Decision`) on top of these Phase-1 static inspectors.
"""

from AgentEval.skills.library import SkillsLibrary

__all__ = ["SkillsLibrary"]
