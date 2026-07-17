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

"""Opt-in live E2E smoke tests for the kilo + copilot adapters (D6 empirical check).

These are the empirical-truth check the version-drift design calls for: they run
the *real* CLI end to end and confirm the adapter normalizes its output without
raising. They are DISABLED by default and skip unless BOTH:

  * ``AGENTEVAL_LIVE_CLI_SMOKE=1`` is set (explicit opt-in - real runs spend
    provider credits and the agent runs autonomously), and
  * the target binary is resolvable on PATH.

Never run in CI or the default suite. Assertions stay tolerant because a DEGRADED
adapter may legitimately return empty metrics.
"""

from __future__ import annotations

import os
import shutil

import pytest

from AgentEval._core.cli_adapters.copilot import CopilotAdapter
from AgentEval._core.cli_adapters.kilo import KiloAdapter
from AgentEval._core.errors import AdapterError
from AgentEval._core.types import AgentRunResult

_LIVE = pytest.mark.skipif(
    os.environ.get("AGENTEVAL_LIVE_CLI_SMOKE") != "1",
    reason="set AGENTEVAL_LIVE_CLI_SMOKE=1 to run live CLI smoke tests (spends credits)",
)

# A pure-text prompt that should not require any tool call.
_SMOKE_PROMPT = "Reply with exactly the single word: pong"


@_LIVE
def test_kilo_live_smoke() -> None:
    if shutil.which(KiloAdapter.binary_name) is None:
        pytest.skip("kilo binary not on PATH")
    try:
        result = KiloAdapter().run(_SMOKE_PROMPT, timeout=180.0)
    except AdapterError as exc:  # missing credentials surface as a loud adapter error
        pytest.skip(f"kilo run unavailable: {exc}")
    assert isinstance(result, AgentRunResult)


@_LIVE
def test_copilot_live_smoke() -> None:
    if shutil.which(CopilotAdapter.binary_name) is None:
        pytest.skip("copilot binary not on PATH")
    try:
        result = CopilotAdapter().run(_SMOKE_PROMPT, timeout=180.0)
    except AdapterError as exc:
        pytest.skip(f"copilot run unavailable: {exc}")
    assert isinstance(result, AgentRunResult)
    # copilot never reports USD cost - the ceiling must hold even live.
    assert result.cost_usd == 0.0
    assert result.metadata.metric_source == "none"
