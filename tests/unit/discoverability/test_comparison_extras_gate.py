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

"""ImportError-gate tests for `MCP.Compare Tool Discoverability` (Story 13.3 L-2 lesson).

Mirrors `tests/unit/stats/test_advanced_extras_gate.py` (Story 13.1) +
`tests/unit/telemetry/test_backends_otlp_extras_gate.py` (Story 13.2)
discipline: NO module-top `pytest.importorskip` so these tests run in
BOTH the WITH-extras and WITHOUT-extras CI environments.

Per AC-13.3.4 + Story 13.1 L-2 lesson: the WITHOUT-extras CI matrix
MUST verify (a) the comparison schema module imports without scipy;
(b) the keyword raises the spec-mandated ImportError when invoked
without scipy/numpy; (c) the ImportError message contains the verbatim
`uv pip install robotframework-agenteval[agenteval-advanced]` install
hint.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_comparison_schema_importable_without_extra() -> None:
    """`from AgentEval.discoverability.schema import DiscoverabilityComparisonResult` succeeds without `[agenteval-advanced]`.

    The dataclasses reference `MannWhitneyResult` via `TYPE_CHECKING`
    only — no runtime scipy import at module load time.
    """
    from AgentEval.discoverability.schema import (  # noqa: F401
        DiscoverabilityComparisonResult,
        DiscoverabilityComparisonSummary,
        PairwiseAdapterDelta,
    )


def test_compare_keyword_raises_import_error_when_advanced_extra_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`MCP.Compare Tool Discoverability` raises ImportError when `_ADVANCED_AVAILABLE=False`.

    Monkeypatches the Story 13.1 module-level gate directly (vs reloading
    the module with scipy stubbed out) per Story 13.1 review HIGH-B lesson.
    The gate check sits BEFORE the per-adapter fan-out (D-6 fail-fast)
    so operators discovering the missing extra do not pay any trial cost.
    """
    pytest.importorskip("opentelemetry")  # MCPLibrary infrastructure dep.

    from AgentEval.mcp.library import MCPLibrary
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)

    lib = MCPLibrary()
    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
    with pytest.raises(ImportError, match="agenteval-advanced"):
        lib.get_tool_discoverability_comparison(
            mcp_server="echo",
            adapters=["any_a", "any_b"],
            tasks=str(fixture_path),
            trials_per_task=1,
        )


def test_compare_keyword_import_error_message_contract() -> None:
    """The ImportError message contains the verbatim install hint.

    Per Story 13.2 D-3 + AC-13.3.4 in-flight decision (b): the MCP
    keyword raises directly (not via the Stats helper) so the message
    is `MCP.Compare Tool Discoverability:`-prefixed (NOT `Stat.`).
    """
    pytest.importorskip("opentelemetry")

    from unittest.mock import patch

    from AgentEval.mcp.library import MCPLibrary
    from AgentEval.stats import library as stats_lib

    fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "tasks-basic.yaml"
    lib = MCPLibrary()

    with patch.object(stats_lib, "_ADVANCED_AVAILABLE", False), pytest.raises(ImportError) as exc_info:
        lib.get_tool_discoverability_comparison(
            mcp_server="echo",
            adapters=["a", "b"],
            tasks=str(fixture_path),
            trials_per_task=1,
        )
    msg = str(exc_info.value)
    assert "MCP.Compare Tool Discoverability" in msg
    assert "scipy + numpy required" in msg
    assert "uv pip install robotframework-agenteval[agenteval-advanced]" in msg


def test_compare_keyword_arg_validation_runs_before_extras_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Arg validation (mcp_server / adapters / tasks) runs BEFORE the extras gate.

    Rationale: a user with a missing extra AND missing args should see
    the arg error first (more actionable). Empty `mcp_server` → ValueError
    even when `_ADVANCED_AVAILABLE=False`.
    """
    pytest.importorskip("opentelemetry")

    from AgentEval.mcp.library import MCPLibrary
    from AgentEval.stats import library as stats_lib

    monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)
    lib = MCPLibrary()
    with pytest.raises(ValueError, match="mcp_server"):
        lib.get_tool_discoverability_comparison(
            mcp_server="",  # empty — arg validation should fire first.
            adapters=["a", "b"],
            tasks="some.yaml",
            trials_per_task=1,
        )
