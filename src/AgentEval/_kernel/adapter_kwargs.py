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

"""Shared adapter-kwarg splitting helper (add-multi-turn-conversation-testing).

Factored out of `orchestration/library.py` so BOTH `OrchestrationLibrary`
(`Send Prompt` / `Run Scenario`) AND `ConversationLibrary`
(`Start Conversation`) can split caller kwargs into constructor-bound vs
`run()`-bound without a circular import (orchestration's `Run Scenario`
lazy-imports the conversation threading layer for `turns:` evals, so
conversation MUST NOT import back from orchestration).

The behavior is byte-identical to the Story 4.3 implementation that
previously lived in `orchestration/library.py` — orchestration now
re-exports this function.
"""

from __future__ import annotations

import inspect
from typing import Any

__all__ = ["split_adapter_kwargs"]


def split_adapter_kwargs(adapter_cls: type, kwargs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split caller kwargs into ctor kwargs vs run-time kwargs via signature introspection.

    Named params on the adapter's ``__init__`` (other than ``self`` and
    ``**kwargs``) are constructor-bound; everything else flows to ``run()``.
    Adapters whose ``__init__`` accepts ``**kwargs`` get ALL kwargs (preserves
    the Story 1b.4 ``InProcessAdapter._adapter_config`` swallow-pattern).
    """
    try:
        sig = inspect.signature(adapter_cls)  # signature of the class IS the __init__ signature minus self
    except (TypeError, ValueError):
        # Fallback: forward everything to ctor (Story 4.3 Phase-1 behavior).
        return dict(kwargs), {}
    accepts_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    if accepts_var_keyword:
        return dict(kwargs), {}
    ctor_param_names = {
        p.name
        for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    ctor_kwargs = {k: v for k, v in kwargs.items() if k in ctor_param_names}
    run_kwargs = {k: v for k, v in kwargs.items() if k not in ctor_param_names}
    return ctor_kwargs, run_kwargs
