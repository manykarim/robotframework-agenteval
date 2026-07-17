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

"""Concrete coding-agent CLI adapters, one thin subclass of the subprocess seam each.

``SLUG_MAP`` is the registry ``get_adapter`` reaches into (lazily, to keep the
base import cheap): a slug -> adapter-class mapping over the six supported CLIs.
Fidelity is uneven and labeled per adapter (FULL / PARTIAL / DEGRADED).
"""

from __future__ import annotations

from AgentEval._core.cli_adapter import SubprocessCLIAdapter
from AgentEval._core.cli_adapters.claude_code import ClaudeCodeAdapter
from AgentEval._core.cli_adapters.codex import CodexAdapter
from AgentEval._core.cli_adapters.copilot import CopilotAdapter
from AgentEval._core.cli_adapters.gemini import GeminiAdapter
from AgentEval._core.cli_adapters.kilo import KiloAdapter
from AgentEval._core.cli_adapters.opencode import OpencodeAdapter

# Slug -> concrete adapter class. Keyed by the same slug the class carries, so a
# rename can't silently desync the registry from the adapter.
SLUG_MAP: dict[str, type[SubprocessCLIAdapter]] = {
    ClaudeCodeAdapter.slug: ClaudeCodeAdapter,
    GeminiAdapter.slug: GeminiAdapter,
    CodexAdapter.slug: CodexAdapter,
    OpencodeAdapter.slug: OpencodeAdapter,
    KiloAdapter.slug: KiloAdapter,
    CopilotAdapter.slug: CopilotAdapter,
}

__all__ = [
    "SLUG_MAP",
    "ClaudeCodeAdapter",
    "GeminiAdapter",
    "CodexAdapter",
    "OpencodeAdapter",
    "KiloAdapter",
    "CopilotAdapter",
]
