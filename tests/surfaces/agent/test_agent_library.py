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

"""AgentLibrary: Get Adapter / Run Agent across families, with honest skip/raise."""

from __future__ import annotations

from typing import Any

import pytest
from robot.api import SkipExecution

from AgentEval._core.errors import BudgetExceededError
from AgentEval._core.tier import deterministic_scope
from AgentEval._core.types import AgentRunResult
from AgentLibrary import AgentLibrary


class _FakeAdapter:
    """A protocol-satisfying adapter that records the run and can raise on demand."""

    name = "fake"

    def __init__(self, *, raises: BaseException | None = None) -> None:
        self._raises = raises
        self.ran: tuple[str, dict[str, Any]] | None = None

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        if self._raises is not None:
            raise self._raises
        self.ran = (prompt, kwargs)
        return AgentRunResult(response_text="ok")


@pytest.fixture
def lib() -> AgentLibrary:
    return AgentLibrary()


# --- Get Adapter -----------------------------------------------------------------


def test_get_adapter_passes_through_an_adapter_object(lib: AgentLibrary) -> None:
    obj = _FakeAdapter()
    assert lib.get_adapter(obj) is obj


def test_get_adapter_resolves_a_slug(lib: AgentLibrary) -> None:
    from AgentEval._core.adapter import GenericAdapter

    assert isinstance(lib.get_adapter("generic", model="x"), GenericAdapter)


def test_get_adapter_real_inprocess_coerces_and_preserves_lists(lib: AgentLibrary) -> None:
    # End-to-end (no monkeypatch): the coerced value is actually accepted by the
    # real InProcessAgentAdapter; an already-list value is preserved as-is.
    pytest.importorskip("pydantic_ai")
    from AgentEval._core.agent_adapter import InProcessAgentAdapter

    scalar_toolset, listed_capability = object(), object()
    adapter = lib.get_adapter("in-process", toolsets=scalar_toolset, capabilities=[listed_capability])
    assert isinstance(adapter, InProcessAgentAdapter)
    assert adapter._toolsets == [scalar_toolset]  # scalar coerced to a one-element list
    assert adapter._capabilities == [listed_capability]  # already a list, preserved


def test_get_adapter_coerces_scalar_toolset_and_strips_none(lib: AgentLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_factory(adapter: Any, **config: Any) -> Any:
        captured.update(config)
        captured["_adapter"] = adapter
        return _FakeAdapter()

    monkeypatch.setattr("AgentLibrary._get_adapter", fake_factory)
    sentinel = object()
    lib.get_adapter("in-process", toolsets=sentinel, model=None, instructions="g")

    assert captured["toolsets"] == [sentinel]  # scalar coerced to a one-element list
    assert "model" not in captured  # None-valued config stripped
    assert captured["instructions"] == "g"


# --- Run Agent -------------------------------------------------------------------


def test_run_agent_success_forwards_run_kwargs(lib: AgentLibrary) -> None:
    adapter = _FakeAdapter()
    result = lib.run_agent(adapter, "hello", timeout=30)
    assert result.response_text == "ok"
    assert adapter.ran == ("hello", {"timeout": 30})


def test_run_agent_budget_not_skipped_raises_budget_error(lib: AgentLibrary) -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import UsageLimitExceeded

    adapter = _FakeAdapter(raises=UsageLimitExceeded("request_limit of 50"))
    with pytest.raises(BudgetExceededError):
        lib.run_agent(adapter, "go")  # budget_exceeded not in skip_on


def test_run_agent_skips_a_listed_provider_error(lib: AgentLibrary) -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import ModelHTTPError

    adapter = _FakeAdapter(raises=ModelHTTPError(503, "m"))
    # The skip message must name the category and the adapter (spec scenario).
    with pytest.raises(SkipExecution, match=r"provider_error.*fake"):
        lib.run_agent(adapter, "go", skip_on="provider_error")


def test_run_agent_budget_skipped_when_opted_in(lib: AgentLibrary) -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import UsageLimitExceeded

    adapter = _FakeAdapter(raises=UsageLimitExceeded("request_limit of 50"))
    with pytest.raises(SkipExecution, match=r"budget_exceeded.*fake"):
        lib.run_agent(adapter, "go", skip_on="budget_exceeded")


def test_run_agent_unlisted_transient_reraises_original(lib: AgentLibrary) -> None:
    # The never-fabricate safety branch: a classified transient NOT in skip_on
    # re-raises the ORIGINAL exception unchanged (no fabricated result, no skip).
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import ModelHTTPError

    adapter = _FakeAdapter(raises=ModelHTTPError(503, "m"))
    with pytest.raises(ModelHTTPError):
        lib.run_agent(adapter, "go")  # provider_error not listed in skip_on


def test_run_agent_resolves_a_bare_slug_then_runs(lib: AgentLibrary, monkeypatch: pytest.MonkeyPatch) -> None:
    # The "run a prompt from a bare slug" spec scenario: a slug string resolves via
    # the factory, then the prompt runs - no separate Get Adapter step.
    recorded: dict[str, Any] = {}
    fake = _FakeAdapter()

    def factory(adapter: Any, **config: Any) -> Any:
        recorded["slug"] = adapter
        return fake

    monkeypatch.setattr("AgentLibrary._get_adapter", factory)
    result = lib.run_agent("claude-code", "do it", timeout=60)
    assert recorded["slug"] == "claude-code"
    assert result.response_text == "ok"
    assert fake.ran == ("do it", {"timeout": 60})


def test_run_agent_auth_fault_always_raises_even_when_skip_on_lists_provider(lib: AgentLibrary) -> None:
    # A 401 is a ModelHTTPError but non-retryable: it must fail loud, never skip,
    # so an auth bug cannot masquerade as a transient skip.
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import ModelHTTPError

    adapter = _FakeAdapter(raises=ModelHTTPError(401, "m"))
    with pytest.raises(ModelHTTPError):
        lib.run_agent(adapter, "go", skip_on="budget_exceeded,provider_error,timeout")


def test_run_agent_config_fault_raises(lib: AgentLibrary) -> None:
    adapter = _FakeAdapter(raises=ValueError("bad config"))
    with pytest.raises(ValueError):
        lib.run_agent(adapter, "go", skip_on="provider_error,budget_exceeded,timeout")


def test_run_agent_enforces_the_tier_gate(lib: AgentLibrary) -> None:
    from AgentEval._core.errors import TierViolationError

    with pytest.raises(TierViolationError), deterministic_scope():
        lib.run_agent(_FakeAdapter(), "go")


# --- Non-breaking public/internal parity -----------------------------------------


def test_public_and_internal_entrypoints_agree() -> None:
    import AgentEval
    from AgentEval._core.adapter import get_adapter as core_get_adapter

    assert AgentEval.get_adapter is core_get_adapter  # public re-export is the same object
    # the internal path still resolves (non-breaking)
    assert type(core_get_adapter("generic", model="x")) is type(AgentEval.get_adapter("generic", model="x"))


def test_import_agenteval_does_not_load_extras() -> None:
    # evaluation-core invariant: the public re-export must not eagerly pull in the
    # optional LLM/agent extras. Checked in a fresh interpreter for isolation.
    import subprocess
    import sys

    code = (
        "import sys, AgentEval; "
        "assert 'litellm' not in sys.modules, 'litellm eagerly imported'; "
        "assert 'pydantic_ai' not in sys.modules, 'pydantic_ai eagerly imported'; "
        "print('clean')"
    )
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert "clean" in completed.stdout
