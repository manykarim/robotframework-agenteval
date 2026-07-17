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

"""The in-process PreToolUse-style tool gate (pydantic-ai tool-approval).

These tests need pydantic-ai (the ``[agent]`` extra); skip cleanly if absent.
No live model is called in the deterministic tests - a scripted ``FunctionModel``
drives the tool calls and the allow/deny policy is applied at pydantic-ai's
approval seam. A single gated live smoke exercises a real MiniMax denial.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from AgentEval._core.errors import HookExecutionError, MissingExtraError
from HooksLibrary import HooksLibrary
from HooksLibrary._agent_bridge import (
    GUARD_CEILING,
    ToolDecision,
    ToolPolicyReport,
    run_tool_policy,
)

pytest.importorskip("pydantic_ai", reason="the in-process tool gate needs the [agent] extra")

_LIVE = pytest.mark.skipif(
    not (os.environ.get("AGENTEVAL_API_KEY") and os.environ.get("AGENTEVAL_MODEL")),
    reason="set AGENTEVAL_MODEL/AGENTEVAL_BASE_URL/AGENTEVAL_API_KEY for the live tool-gate smoke",
)


def _toolset() -> Any:
    """A FunctionToolset with two side-effecting tools the model can call."""
    from pydantic_ai.toolsets import FunctionToolset

    ts = FunctionToolset()
    ts.add_function(lambda path: f"deleted {path}", name="delete_file")
    ts.add_function(lambda path: f"contents of {path}", name="read_file")
    return ts


def _scripted_model(*responses: Any) -> Any:
    """A FunctionModel that returns each scripted ModelResponse in turn."""
    from pydantic_ai.models.function import FunctionModel

    state = {"i": 0}

    def model_fn(messages: list, info: Any) -> Any:  # type: ignore[type-arg]
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        return responses[idx]

    return FunctionModel(model_fn)


def _call(tool_name: str, **args: Any) -> Any:
    from pydantic_ai.messages import ModelResponse, ToolCallPart

    return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])


def _text(value: str) -> Any:
    from pydantic_ai.messages import ModelResponse, TextPart

    return ModelResponse(parts=[TextPart(value)])


# --------------------------------------------------------------------------- #
# Bridge: policy application at the approval seam
# --------------------------------------------------------------------------- #


def test_deny_list_denies_matching_call_and_allows_others() -> None:
    model = _scripted_model(_call("delete_file", path="/etc/passwd"), _call("read_file", path="/tmp/ok"), _text("done"))
    report = run_tool_policy(
        model,
        "clean up",
        toolset=_toolset(),
        policy=HooksLibrary._build_tool_policy(None, "delete_file"),
    )
    assert report.response_text == "done"
    assert report.denied == ("delete_file",)
    assert report.allowed == ("read_file",)
    # The denied call carries the policy reason; the allowed one does not.
    denied = report.decisions_for("delete_file")[0]
    assert denied.decision == "deny"
    assert "deny-list" in denied.reason
    assert denied.args == {"path": "/etc/passwd"}


def test_allow_list_denies_every_other_gated_tool() -> None:
    model = _scripted_model(_call("read_file", path="/tmp/a"), _call("delete_file", path="/tmp/a"), _text("ok"))
    report = run_tool_policy(
        model,
        "read then delete",
        toolset=_toolset(),
        policy=HooksLibrary._build_tool_policy("read_file", None),
    )
    assert report.allowed == ("read_file",)
    assert report.denied == ("delete_file",)


def test_no_policy_allows_all_but_records_every_call() -> None:
    model = _scripted_model(_call("delete_file", path="/x"), _call("read_file", path="/y"), _text("fin"))
    report = run_tool_policy(model, "do both", toolset=_toolset(), policy=None)
    assert report.denied == ()
    assert report.allowed == ("delete_file", "read_file")
    assert [d.sequence_index for d in report.decisions] == [0, 1]


def test_gated_tools_restricts_which_calls_are_observed() -> None:
    # Only delete_file is gated; read_file executes without an approval decision.
    model = _scripted_model(_call("read_file", path="/y"), _call("delete_file", path="/x"), _text("fin"))
    report = run_tool_policy(
        model,
        "read then delete",
        toolset=_toolset(),
        policy=HooksLibrary._build_tool_policy(None, "delete_file"),
        gated_tools={"delete_file"},
    )
    # read_file was never gated -> no decision recorded for it.
    assert report.decisions_for("read_file") == ()
    assert report.denied == ("delete_file",)


def test_ungated_run_needs_no_approval_and_records_nothing() -> None:
    model = _scripted_model(_call("read_file", path="/y"), _text("done"))
    report = run_tool_policy(
        model,
        "just read",
        toolset=_toolset(),
        policy=HooksLibrary._build_tool_policy(None, "delete_file"),
        gated_tools={"delete_file"},
    )
    assert report.decisions == ()
    assert report.rounds == 0
    assert report.response_text == "done"


def test_custom_deny_reason_is_surfaced() -> None:
    model = _scripted_model(_call("delete_file", path="/x"), _text("done"))
    report = run_tool_policy(
        model,
        "delete",
        toolset=_toolset(),
        policy=lambda name, args: False,  # bare-bool deny -> default reason applies
        default_deny_reason="blocked by test policy",
    )
    assert report.decisions_for("delete_file")[0].reason == "blocked by test policy"


def test_runaway_approval_loop_raises_hook_execution_error() -> None:
    # The model keeps requesting a denied tool; the loop must fail loud, not hang.
    model = _scripted_model(_call("delete_file", path="/x"))  # always the same call
    with pytest.raises(HookExecutionError, match="did not converge"):
        run_tool_policy(
            model,
            "keep trying",
            toolset=_toolset(),
            policy=HooksLibrary._build_tool_policy(None, "delete_file"),
            max_rounds=3,
        )


# --------------------------------------------------------------------------- #
# Report projections + assertion keywords
# --------------------------------------------------------------------------- #


def _report(*decisions: ToolDecision) -> ToolPolicyReport:
    return ToolPolicyReport(decisions=tuple(decisions), response_text="", rounds=len(decisions))


def _decision(tool: str, verdict: str, idx: int) -> ToolDecision:
    return ToolDecision(tool_name=tool, args={}, decision=verdict, reason="", sequence_index=idx)


def test_should_be_denied_passes_on_a_denial() -> None:
    report = _report(_decision("delete_file", "deny", 0))
    HooksLibrary().tool_should_be_denied(report, "delete_file")  # no raise


def test_should_be_denied_fails_when_tool_never_called() -> None:
    report = _report(_decision("read_file", "allow", 0))
    with pytest.raises(AssertionError, match="never called it"):
        HooksLibrary().tool_should_be_denied(report, "delete_file")


def test_should_be_denied_fails_when_tool_was_allowed() -> None:
    report = _report(_decision("delete_file", "allow", 0))
    with pytest.raises(AssertionError, match="every call to it was allowed"):
        HooksLibrary().tool_should_be_denied(report, "delete_file")


def test_should_be_allowed_passes_and_fails() -> None:
    lib = HooksLibrary()
    lib.tool_should_be_allowed(_report(_decision("read_file", "allow", 0)), "read_file")
    with pytest.raises(AssertionError, match="never called it"):
        lib.tool_should_be_allowed(_report(), "read_file")
    with pytest.raises(AssertionError, match="was denied"):
        lib.tool_should_be_allowed(_report(_decision("read_file", "deny", 0)), "read_file")


def test_assertion_rejects_non_report() -> None:
    with pytest.raises(TypeError, match="Hook.Get Tool Decisions"):
        HooksLibrary().tool_should_be_denied({"not": "a report"}, "x")


# --------------------------------------------------------------------------- #
# Policy/name-parsing helpers
# --------------------------------------------------------------------------- #


def test_as_name_set_parses_string_and_list_forms() -> None:
    assert HooksLibrary._as_name_set("a|b, c") == {"a", "b", "c"}
    assert HooksLibrary._as_name_set(["x", " y "]) == {"x", "y"}
    assert HooksLibrary._as_name_set(None) is None
    assert HooksLibrary._as_name_set("") is None


def test_build_tool_policy_allow_list_wins_over_deny() -> None:
    policy = HooksLibrary._build_tool_policy("read_file", "read_file")
    assert policy is not None
    assert policy("read_file", {})[0] is True
    assert policy("delete_file", {})[0] is False


def test_build_tool_policy_none_when_no_lists() -> None:
    assert HooksLibrary._build_tool_policy(None, None) is None


def test_ceiling_is_honest_about_the_partial_surface() -> None:
    assert HooksLibrary.TOOL_GATE_CEILING is GUARD_CEILING
    lowered = GUARD_CEILING.lower()
    assert "partial" in lowered
    assert "not the claude code" in lowered
    assert "hook.fire hook event" in lowered.replace("`", "")


# --------------------------------------------------------------------------- #
# Missing-extra behaviour
# --------------------------------------------------------------------------- #


def test_build_agent_model_requires_a_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTEVAL_MODEL", raising=False)
    with pytest.raises(MissingExtraError, match="needs a model"):
        HooksLibrary._build_agent_model(None, None, None)


# --------------------------------------------------------------------------- #
# Gated live smoke: a real model's denied tool call is observable
# --------------------------------------------------------------------------- #


@_LIVE
def test_live_denied_tool_call_is_observable() -> None:
    """Live smoke: a real model asks to delete a file; the policy denies it in-process."""
    report = HooksLibrary().get_tool_decisions(
        "Use the delete_file tool to delete the file at /tmp/agenteval-smoke.log. Call the tool, then reply DONE.",
        _toolset(),
        deny="delete_file",
    )
    assert "delete_file" in report.denied, f"model never triggered a gated delete_file call: {report.decisions}"
    denied = report.decisions_for("delete_file")[0]
    assert denied.decision == "deny"
    assert "deny-list" in denied.reason
