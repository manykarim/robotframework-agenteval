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

"""The shared spine the four surface libraries import.

This package exposes no Robot Framework keywords - it is the internal machinery
(tier marker, adapter seam, judge, stats, trace, errors, types) that
``MCPLibrary``, ``SkillsLibrary``, ``SubagentsLibrary``, and ``HooksLibrary``
build on. Import what you need straight from here.
"""

from __future__ import annotations

from AgentEval._core import errors, judge, stats, trace
from AgentEval._core.adapter import (
    Adapter,
    GenericAdapter,
    get_adapter,
    resolve_config,
    run_async,
)
from AgentEval._core.errors import (
    AdapterError,
    AgentEvalError,
    BudgetExceededError,
    HookExecutionError,
    IncompleteTraceError,
    InvalidConfigError,
    InvalidRubricError,
    JudgeOutputParseError,
    MCPError,
    MissingExtraError,
    SkillDidNotActivateError,
    SubagentDelegationError,
    TierViolationError,
    error_code_to_exit_code,
)
from AgentEval._core.judge import JudgeRubric, JudgeScore
from AgentEval._core.stats import KeywordRun
from AgentEval._core.tier import (
    deterministic_scope,
    enforce_no_model,
    find_tier_through_wrappers,
    get_keyword_tier,
    tier,
    tier_badge,
)
from AgentEval._core.types import (
    AgentRunMetadata,
    AgentRunResult,
    ToolCallTrace,
    Usage,
)

__all__ = [
    # submodules (call e.g. stats.pass_at_k, judge.score, trace.was_tool_called)
    "errors",
    "judge",
    "stats",
    "trace",
    # tier
    "tier",
    "get_keyword_tier",
    "find_tier_through_wrappers",
    "tier_badge",
    "deterministic_scope",
    "enforce_no_model",
    # adapter
    "Adapter",
    "GenericAdapter",
    "get_adapter",
    "resolve_config",
    "run_async",
    # judge
    "JudgeRubric",
    "JudgeScore",
    # stats
    "KeywordRun",
    # types
    "AgentRunResult",
    "AgentRunMetadata",
    "ToolCallTrace",
    "Usage",
    # errors
    "AgentEvalError",
    "InvalidConfigError",
    "InvalidRubricError",
    "JudgeOutputParseError",
    "MissingExtraError",
    "AdapterError",
    "TierViolationError",
    "IncompleteTraceError",
    "BudgetExceededError",
    "HookExecutionError",
    "SkillDidNotActivateError",
    "SubagentDelegationError",
    "MCPError",
    "error_code_to_exit_code",
]
