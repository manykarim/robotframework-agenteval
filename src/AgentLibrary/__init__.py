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

"""Construct and run an agent adapter from ``.robot`` - any of the three families.

The spine's adapter seam drives an in-process pydantic-ai agent, a one-shot LiteLLM
model, or one of six coding-agent CLIs through the same
``run(prompt) -> AgentRunResult`` protocol - but the only way to reach it was
``Evaluate AgentEval._core.adapter.get_adapter(...)`` into an internal module.
``AgentLibrary`` closes that gap with two keywords.

    *** Settings ***
    Library    AgentLibrary

- `Agent.Get Adapter` builds an adapter (by slug or a pass-through object) with
  native construction arguments. **Tier 1** - construction touches no model; the
  LLM/agent extras stay lazy until the run.
- `Agent.Run Agent` runs a prompt through an adapter (slug or object) and returns
  the raw ``AgentRunResult``. **Tier 3** - it drives a real model/agent. It owns the
  single transient/budget classifier: a category named in ``skip_on`` skips the
  test, a budget overrun re-raises as ``BudgetExceededError``, an unlisted transient
  re-raises, and a genuine config/auth fault always raises - never a fabricated
  result.
"""

from __future__ import annotations

from typing import Any

from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn

from AgentEval import Adapter
from AgentEval import get_adapter as _get_adapter
from AgentEval._core import BudgetExceededError, enforce_no_model, tier
from AgentEval._core.run_classifier import classify_run_exception
from AgentEval._core.types import AgentRunResult

__all__ = ["AgentLibrary"]

# Config values that are naturally lists but which a caller often supplies as a
# single object; coerce a scalar to a one-element list so RF users avoid ${{ [$x] }}.
_LIST_CONFIG_KEYS = ("toolsets", "capabilities")


class AgentLibrary:
    """Construct an adapter and run a prompt through it, across all adapter families."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    @keyword(name="Agent.Get Adapter")
    @tier(1)
    def get_adapter(self, adapter: str | Adapter = "generic", **config: Any) -> Adapter:
        """Build an adapter by slug (or pass through an adapter object).

        ``adapter`` is a slug - ``in-process`` / ``generic`` / a coding-agent CLI
        (``claude-code``, ``gemini``, ``codex``, ``opencode``, ``kilo``,
        ``copilot``) - or an object already satisfying the ``Adapter`` protocol.
        ``config`` is forwarded to the adapter's constructor as native arguments
        (in-process: ``toolsets``/``capabilities``/``instructions``/``request_limit``/
        ``usage_limits``/``model``/``base_url``/``api_key``; generic: ``model`` +
        LiteLLM knobs; CLI slugs take none). A scalar ``toolsets=``/``capabilities=``
        is coerced to a one-element list. Construction is Tier 1 - no model is called
        until `Agent.Run Agent`.

        Example:
        | ${adapter}=    Agent.Get Adapter    in-process    toolsets=${toolset}    request_limit=120
        """
        cleaned = {key: value for key, value in config.items() if value is not None}
        for key in _LIST_CONFIG_KEYS:
            if key in cleaned and not isinstance(cleaned[key], (list, tuple)):
                cleaned[key] = [cleaned[key]]
        return _get_adapter(adapter, **cleaned)

    @keyword(name="Agent.Run Agent")
    @tier(3)
    def run_agent(
        self,
        adapter: str | Adapter,
        prompt: str,
        skip_on: str = "",
        **run_kwargs: Any,
    ) -> AgentRunResult:
        """Run ``prompt`` through ``adapter`` and return the ``AgentRunResult``.

        ``adapter`` is a slug or an adapter object (e.g. from `Agent.Get Adapter`);
        a bare slug builds a no-config adapter, which is all the CLI and one-shot
        generic families need. ``run_kwargs`` are forwarded to the adapter's
        ``run()`` (CLI: ``timeout``/``cwd``/``session_dir``/``env``; per-run
        overrides for the others).

        ``skip_on`` is a comma-separated list of transient categories -
        ``budget_exceeded``, ``provider_error``, ``timeout`` - to turn into a
        Robot **skip** instead of a failure. A ``budget_exceeded`` failure that is
        NOT skipped re-raises as ``BudgetExceededError``; an unlisted transient
        re-raises unchanged; and a genuine config/auth/harness fault (missing extra,
        tier violation, missing binary, non-retryable HTTP status) always raises.
        A failed run is never turned into a fabricated result. Tier 3 - drives a
        real model/agent.

        Example:
        | ${adapter}=    Agent.Get Adapter    in-process    toolsets=${toolset}
        | ${result}=    Agent.Run Agent    ${adapter}    Analyze the login page    skip_on=provider_error
        | ${count}=    MCP.Get Tool Call Count    ${result}
        """
        enforce_no_model()
        adapter_obj = _get_adapter(adapter)
        skip_categories = {token.strip() for token in str(skip_on).split(",") if token.strip()}
        try:
            return adapter_obj.run(prompt, **run_kwargs)
        except BaseException as exc:  # noqa: BLE001 - classified, then re-raised or turned into a skip
            category = classify_run_exception(exc)
            if category is None:
                raise
            adapter_name = getattr(adapter_obj, "name", "agent")
            if category in skip_categories:
                BuiltIn().skip(f"{category}: {adapter_name} agent run skipped - {exc}")
            if category == "budget_exceeded":
                raise BudgetExceededError(f"{adapter_name} agent run exceeded its budget: {exc}") from exc
            raise
