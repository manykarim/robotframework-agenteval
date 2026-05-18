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

"""AgentEval.security sub-package.

Sandbox Policy + NullSandbox default + SandboxBackend Protocol per ADR-018
(was ADR-A8; ratified 2026-05-17). Phase 1 ships policy + gate + Protocol;
bundled backend implementations (Docker / ephemeral-worktree / gVisor) ship
in Phase 3 via the `[project.entry-points."agenteval.sandboxes"]` discovery
mechanism.

Authored by Story 1a.1 per ADR-018 §Decision items 3 + 4 (correction applied
2026-05-17 during Story 1a.1 code review — initial 1a.1 deferred to Story
1a.6 in contradiction of the ratified ADR; the ADR takes precedence).
"""
