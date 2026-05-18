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

"""Sandbox policy + gate logic.

Authored in Story 1a.1 per ADR-018 §Decision item 4 (ratified 2026-05-17):
Phase 1 ships policy + gate + Protocol; bundled backend implementations
defer to Phase 3.

Phase-1 PLACEHOLDER: this module is currently empty by design. The gate
logic (which inspects `mcp_per_test` / `validate` operator decisions /
Tier-3 scenario requests and decides whether to invoke the configured
SandboxBackend) wires together with the library-init code path that Epic 6
ships (statistical primitives + tier ACL + determinism enforcement). The
NullSandbox default refusal (see `null_sandbox.py`) is the only sandbox-aware
behavior available in Phase 1.

When the validate-operator gate ships (Epic 6 Story 6.3), this module fills
with the policy decision tree:

1. Is the scenario Tier-3 (code execution)? — no → bypass gate
2. Is `allow_validate_operator=True` set? — yes → invoke configured backend
3. Default — invoke configured backend; `NullSandbox` raises (refuses)

See `docs/adr/ADR-018-sandbox-phase-1-policy.md` for the full ratification.
"""

from __future__ import annotations
