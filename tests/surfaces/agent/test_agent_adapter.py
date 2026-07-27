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
from AgentEval._core.agent_adapter import (
    InProcessAgentAdapter,
    _map_agent_result,
    _resolve_instructions,
    _resolve_usage_limits,
)


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


class _FakeUsageLimits:
    """Stand-in for pydantic-ai's ``UsageLimits`` so precedence is testable without the extra."""

    def __init__(self, *, request_limit: int) -> None:
        self.request_limit = request_limit


def test_resolve_usage_limits_precedence() -> None:
    ul = _FakeUsageLimits

    def rl(x: object) -> int | None:
        return None if x is None else x.request_limit  # type: ignore[attr-defined]

    # A run-level usage_limits object beats everything (returned as-is).
    obj = ul(request_limit=7)
    assert (
        _resolve_usage_limits(
            run_usage_limits=obj,
            run_request_limit=9,
            init_usage_limits=ul(request_limit=3),
            init_request_limit=4,
            usage_limits_cls=ul,
        )
        is obj
    )
    # The reconciled rule: a run-level request_limit beats an __init__-level usage_limits object.
    assert (
        rl(
            _resolve_usage_limits(
                run_usage_limits=None,
                run_request_limit=120,
                init_usage_limits=ul(request_limit=3),
                init_request_limit=None,
                usage_limits_cls=ul,
            )
        )
        == 120
    )
    # Within __init__, the object beats the shortcut.
    init_obj = ul(request_limit=3)
    assert (
        _resolve_usage_limits(
            run_usage_limits=None,
            run_request_limit=None,
            init_usage_limits=init_obj,
            init_request_limit=9,
            usage_limits_cls=ul,
        )
        is init_obj
    )
    # The __init__ shortcut is used when nothing else is set.
    assert (
        rl(
            _resolve_usage_limits(
                run_usage_limits=None,
                run_request_limit=None,
                init_usage_limits=None,
                init_request_limit=50,
                usage_limits_cls=ul,
            )
        )
        == 50
    )
    # All unset -> None -> pydantic-ai's built-in default applies (non-breaking).
    assert (
        _resolve_usage_limits(
            run_usage_limits=None,
            run_request_limit=None,
            init_usage_limits=None,
            init_request_limit=None,
            usage_limits_cls=ul,
        )
        is None
    )


def test_resolve_instructions_precedence() -> None:
    assert _resolve_instructions("run", "init") == "run"  # run wins
    assert _resolve_instructions(None, "init") == "init"  # falls back to init
    assert _resolve_instructions("", "init") == ""  # empty string is a set value, not "unset"
    assert _resolve_instructions(None, None) is None  # default: no injection


def _spy_run_capture(monkeypatch: pytest.MonkeyPatch, captured: dict[str, object]) -> None:
    """Patch the pydantic-ai symbols run() imports so agent.run(**kwargs) is captured, no network."""
    pytest.importorskip("pydantic_ai")

    class _SpyAgent:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def run(self, prompt: str, **kwargs: object) -> object:
            captured["prompt"] = prompt
            captured.update(kwargs)
            return SimpleNamespace(
                all_messages=lambda: [],
                output="",
                usage=SimpleNamespace(input_tokens=0, output_tokens=0, cache_read_tokens=0),
            )

    monkeypatch.setattr("pydantic_ai.Agent", _SpyAgent)
    monkeypatch.setattr("pydantic_ai.models.openai.OpenAIChatModel", lambda *a, **k: object())
    monkeypatch.setattr("pydantic_ai.providers.openai.OpenAIProvider", lambda *a, **k: object())


def test_run_forwards_usage_limit_and_instructions(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic_ai.usage import UsageLimits

    captured: dict[str, object] = {}
    _spy_run_capture(monkeypatch, captured)

    # run-level request_limit overrides an __init__-level usage_limits object (pins the rule),
    # and run-level instructions reach agent.run().
    adapter = get_adapter("in-process", model="m", usage_limits=UsageLimits(request_limit=3))
    adapter.run("hello", request_limit=120, instructions="GUIDE")

    assert isinstance(captured["usage_limits"], UsageLimits)
    assert captured["usage_limits"].request_limit == 120  # type: ignore[union-attr]
    assert captured["instructions"] == "GUIDE"
    assert captured["prompt"] == "hello"
    # Exactly these reach agent.run() - no request_limit/model/base_url/api_key leak.
    assert set(captured) == {"prompt", "usage_limits", "instructions"}


def test_run_default_path_is_non_breaking(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    _spy_run_capture(monkeypatch, captured)

    get_adapter("in-process", model="m").run("hi")

    assert captured["usage_limits"] is None  # no override -> library default (50)
    assert "instructions" not in captured  # instructions kwarg omitted entirely
    assert set(captured) == {"prompt", "usage_limits"}  # nothing else leaks to agent.run()


def test_request_limit_gates_the_agent_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import UsageLimitExceeded
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.toolsets import FunctionToolset

    toolset = FunctionToolset()
    toolset.add_function(lambda: "pong", takes_ctx=False, name="ping")

    def always_call_ping(messages: object, info: object) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(tool_name="ping", args={})])

    # The adapter builds its own model; make it an always-call-tool FunctionModel.
    monkeypatch.setattr("pydantic_ai.models.openai.OpenAIChatModel", lambda *a, **k: FunctionModel(always_call_ping))
    monkeypatch.setattr("pydantic_ai.providers.openai.OpenAIProvider", lambda *a, **k: object())

    def run_with(request_limit: int) -> None:
        get_adapter("in-process", model="m", toolsets=[toolset], request_limit=request_limit).run("go")

    # The loop never stops on its own, so it trips at *exactly the caller's* ceiling.
    # Matching the value (not just the exception type) proves the caller's request_limit
    # gates the loop rather than pydantic-ai's default of 50 - a match on "of 3" alone
    # could not distinguish an honored limit from an ignored one.
    with pytest.raises(UsageLimitExceeded, match=r"request_limit of 3\b"):
        run_with(3)
    # 120 is ABOVE the default 50: this proves a *raised* cap is honored end to end -
    # the feature's headline use case (long scenarios that need more than 50 requests).
    with pytest.raises(UsageLimitExceeded, match=r"request_limit of 120\b"):
        run_with(120)


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
