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
(PRD FR1 + Epic 2 Story 2.1).

Story 2.1 code-review fix: this `__init__.py` does NOT eagerly re-export
`SkillsLibrary`. The earlier shape (`from AgentEval.skills.library
import SkillsLibrary`) created a circular import that only test-ordering
masked: when `tests/unit/conventions/_walk.py` loads `library.py`
directly via `spec_from_file_location` (registering it in `sys.modules`
under its fully-qualified name BEFORE finishing `exec_module`), Python
tries to initialize the parent `AgentEval.skills` package, which then
re-imports the half-loaded `library` module + raises ImportError.

Consumers reach `SkillsLibrary` via:
1. `from AgentEval.skills.library import SkillsLibrary` (Python).
2. `Library AgentEval.skills.library.SkillsLibrary` (.robot).
3. `importlib.import_module("AgentEval.skills.library")` + getattr
   (the DynamicCore lazy-import loop in `AgentEval.__init__`).

All 3 paths resolve through `library.py` directly; the package
`__init__.py` does not need to re-export. Phase-2 + Epic 7 will add
FR4 model-API-key-gated activation (`Get Activation Decision`) here.
"""
