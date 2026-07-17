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

"""Unit + gated-live tests for the in-process pydantic-ai agent adapter."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from AgentEval._core.adapter import get_adapter
from AgentEval._core.agent_adapter import InProcessAgentAdapter, _map_agent_result


def test_slug_resolves_to_in_process_adapter() -> None:
    a = get_adapter("in-process")
    assert isinstance(a, InProcessAgentAdapter)
    assert a.name == "in-process"
    assert "PROXY" in a.validation_ceiling


def test_map_agent_result_projects_tool_calls_and_activation() -> None:
    # A fake pydantic-ai run result: a load_capability activation + a plain tool call.
    call_a = SimpleNamespace(
        part_kind="tool-call", tool_name="load_capability", args='{"id": "refunds"}', tool_call_id="1"
    )
    call_b = SimpleNamespace(part_kind="tool-call", tool_name="lookup", args={"order": "4821"}, tool_call_id="2")
    ret_b = SimpleNamespace(part_kind="tool-return", tool_call_id="2", content="eligible")
    msgs = [SimpleNamespace(parts=[call_a, call_b]), SimpleNamespace(parts=[ret_b])]
    usage = SimpleNamespace(input_tokens=573, output_tokens=153, cache_read_tokens=0)
    result = SimpleNamespace(output="Order 4821 is eligible.", all_messages=lambda: msgs, usage=usage)

    run = _map_agent_result(result)
    assert [t.name for t in run.tool_calls] == ["load_capability", "lookup"]
    activated = [t.args.get("id") for t in run.tool_calls if t.name == "load_capability"]
    assert activated == ["refunds"]  # skill activation derivable from tool_calls
    assert run.tool_calls[1].result == "eligible"  # executed tool result populated
    assert run.usage.input_tokens == 573
    assert run.metadata.metric_source == "derived"


_LIVE = pytest.mark.skipif(
    not (os.environ.get("AGENTEVAL_API_KEY") and os.environ.get("AGENTEVAL_MODEL")),
    reason="set AGENTEVAL_MODEL/AGENTEVAL_BASE_URL/AGENTEVAL_API_KEY for the live in-process smoke",
)


@_LIVE
def test_live_skill_activation() -> None:
    from pydantic_ai.capabilities import Capability

    skill = Capability(
        id="refunds",
        description="Use for refund eligibility questions.",
        instructions="Confirm the order ID.",
        defer_loading=True,
    )
    r = get_adapter("in-process", capabilities=[skill]).run("Is order #4821 eligible for a refund?")
    activated = [t.args.get("id") for t in r.tool_calls if t.name == "load_capability"]
    assert "refunds" in activated
