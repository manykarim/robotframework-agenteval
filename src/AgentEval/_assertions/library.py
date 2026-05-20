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

"""Assertion RF-keyword surface (Story 6.2 / PRD FR23a + FR23b + FR24 + FR25).

Ships 5 assertion keywords reading from `AgentRunResult` instances:

- FR23a + FR23b: `Trajectory Should Match` (4 modes: exact, subsequence, set, regex).
- FR24: `Tool Call Should Have Occurred` (name + optional dict-subset args).
- FR25: `Agent Response Should Contain` + `Should Match Regex` + `Should Match Schema`.

Each keyword:
- Carries `@tier(1)` Tier-1 badge + `[Tier 1 — Deterministic]` docstring
  per `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`.
- Tool-call-bearing keywords (Trajectory + Tool Call) gate on
  `mcp_coverage` via `_kernel/coverage._check_mcp_coverage` per FR37.
- Response keywords (Contain / Match Regex / Match Schema) do NOT gate —
  response text is provider-reported scalar.

**Phase-1 backend per Story 6.2 D-1 drift fix:** uses Python stdlib
(`re`, `jsonschema`) for matching. AssertionEngine integration deferred
to Story 6.3 which plans `_assertions/adapter.py` scaffolding + the
`robotframework-assertion-engine>=4.0,<5.0` dep per architecture L138.

Sub-library registration via `_SUB_LIBRARIES` in `AgentEval/__init__.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
from robot.api.deco import keyword

from AgentEval._assertions import _internal
from AgentEval._kernel.coverage import _check_mcp_coverage
from AgentEval._kernel.redaction import redact
from AgentEval._kernel.tier import tier
from AgentEval.types import AgentRunResult

__all__ = ["AssertionsLibrary"]


_VALID_TRAJECTORY_MODES = ("exact", "subsequence", "set", "regex")


class AssertionsLibrary:
    """5 `@keyword`-decorated assertion methods (Story 6.2 / PRD FR23-25)."""

    def __init__(self, allow_external_mcp_blind: bool = False) -> None:
        """Library-level `allow_external_mcp_blind` per Story 6.1 precedent.

        Forwarded from top-level `AgentEval(allow_external_mcp_blind=...)`
        via `_build_components` per Story 4.3 pattern.
        """
        self._allow_external_mcp_blind = allow_external_mcp_blind

    # ----------------------------------------------------------------- #
    # FR23a + FR23b — Trajectory Should Match                           #
    # ----------------------------------------------------------------- #

    @keyword(name="Trajectory Should Match")
    @tier(1)
    def trajectory_should_match(
        self,
        result: AgentRunResult,
        expected: list[str],
        mode: str = "exact",
    ) -> None:
        """[Tier 1 — Deterministic] Assert the tool-call trajectory matches `expected` (PRD FR23a + FR23b).

        Args:
            result: `AgentRunResult` carrying the observed `tool_calls`.
            expected: List of expected tool names (or regex patterns for
                `mode="regex"`).
            mode: Match mode per PRD FR23a verbatim:

                - `"exact"` (default): ordered list equality.
                - `"subsequence"`: ordered, extras allowed between/around.
                - `"set"`: unordered, no extras — **set equality** semantics.
                  Note: duplicate names collapse (`["a", "a"]` set-equals
                  `["a"]`); operators wanting multiset semantics ("exactly
                  N calls of tool X") should use `mode="exact"` or count
                  via `Get Tool Calls`. Per PRD FR23a verbatim "unordered,
                  no extras" — implementation is set-equality of distinct
                  tool names. Story 6.2 code-review MED-6 docstring fix.
                - `"regex"`: per FR23b, each `expected[i]` is a regex
                  matched via `re.fullmatch` against the concatenation
                  `"<tool_name>:<json.dumps(args, sort_keys=True)>"`.

        Raises:
            `IncompleteTraceError`: per FR37 when `mcp_coverage="external_mixed"`
                + `allow_external_mcp_blind=False` (default).
            `ValueError`: if `mode` is not one of the 4 documented values.
            `AssertionError`: if the trajectory does not match. Failure
                message is `redact()`-scrubbed per FR38a (Story 5.3) so
                credentials in args don't leak into RF logs.
        """
        # Story 6.2 code-review MED ordering fix (Blind LOW-17 + Edge MED-7 +
        # Auditor #7 3-way): validate `mode` BEFORE the FR37 gate so caller-side
        # typos surface as `ValueError` regardless of run-coverage state.
        # Pre-edit: `mode="bogus"` on an `external_mixed` run masked the typo
        # behind `IncompleteTraceError`.
        if mode not in _VALID_TRAJECTORY_MODES:
            raise ValueError(f"mode must be one of: {', '.join(_VALID_TRAJECTORY_MODES)}; got {mode!r}")
        _check_mcp_coverage(
            result,
            allow_external_mcp_blind=self._allow_external_mcp_blind,
            metric_keyword="Trajectory Should Match",
        )
        observed_names = [tc.name for tc in result.tool_calls]
        matched: bool
        if mode == "exact":
            matched = _internal._match_trajectory_exact(observed_names, expected)
        elif mode == "subsequence":
            matched = _internal._match_trajectory_subsequence(observed_names, expected)
        elif mode == "set":
            matched = _internal._match_trajectory_set(observed_names, expected)
        else:  # mode == "regex"
            matched = _internal._match_trajectory_regex(result.tool_calls, expected)
        if not matched:
            # Story 6.2 code-review HIGH-δ fix (Edge HIGH-4 / FR38a Story 5.3
            # contract): route the message through `redact()` so tool names
            # carrying secrets (rare but possible) don't bypass the central
            # credential-scrub policy.
            raise AssertionError(
                redact(f"Trajectory mismatch (mode={mode}): expected={expected!r}, observed={observed_names!r}")
            )

    # ----------------------------------------------------------------- #
    # FR24 — Tool Call Should Have Occurred                             #
    # ----------------------------------------------------------------- #

    @keyword(name="Tool Call Should Have Occurred")
    @tier(1)
    def tool_call_should_have_occurred(
        self,
        result: AgentRunResult,
        tool: str,
        args: dict[str, Any] | None = None,
        match_mode: str = "subset",
    ) -> None:
        """[Tier 1 — Deterministic] Assert a tool call with given name + args occurred (PRD FR24).

        Args:
            result: `AgentRunResult` carrying the observed `tool_calls`.
            tool: Expected tool name (exact match required).
            args: Optional dict of expected args. `None` = name-only match.
            match_mode: Per FR24 verbatim:

                - `"subset"` (default): `args` is a dict-subset of `tc.args`
                  (extra args allowed); recursive for nested dicts.
                - `"exact"`: `tc.args == args` exact equality.

        Raises:
            `IncompleteTraceError`: per FR37 on `external_mixed` coverage.
            `AssertionError`: if no tool call matches. Failure message is
                `redact()`-scrubbed per FR38a (Story 5.3) so credentials
                in tool args don't leak into RF logs.
            `ValueError`: if `match_mode` is invalid.
        """
        # Story 6.2 code-review HIGH-α + MED ordering fix (Edge HIGH-2 + Codex
        # probe + Auditor #7/#8): validate `match_mode` up-front BEFORE the
        # FR37 gate AND before the tool-name loop so typos like
        # `match_mode="bogus"` surface as `ValueError` regardless of (a)
        # whether `args` is None, (b) whether any tool name matches, (c) the
        # run's mcp_coverage. Pre-edit: invalid mode + `args=None` returned
        # True silently; invalid mode + no-name-match raised confusing
        # AssertionError instead of ValueError.
        if match_mode not in _internal._VALID_TOOL_CALL_MATCH_MODES:
            raise ValueError(
                f"match_mode must be one of: {', '.join(_internal._VALID_TOOL_CALL_MATCH_MODES)}; got {match_mode!r}"
            )
        _check_mcp_coverage(
            result,
            allow_external_mcp_blind=self._allow_external_mcp_blind,
            metric_keyword="Tool Call Should Have Occurred",
        )
        for tc in result.tool_calls:
            if _internal._match_tool_call(tc, tool, args, match_mode):
                return
        # Story 6.2 code-review HIGH-δ fix (Edge HIGH-4): `redact()` the
        # `Observed:` dump so tool-call args carrying credentials don't get
        # written to RF `output.xml` verbatim. Story 5.3 ratified emit-time
        # redaction as a project contract.
        raise AssertionError(
            redact(
                f"No tool call matched: tool={tool!r}, args={args!r}, match_mode={match_mode!r}. "
                f"Observed: {[(tc.name, dict(tc.args)) for tc in result.tool_calls]!r}"
            )
        )

    # ----------------------------------------------------------------- #
    # FR25 — Agent Response assertions (no mcp_coverage gate — response  #
    # text is provider-reported scalar, observer-independent)           #
    # ----------------------------------------------------------------- #

    @keyword(name="Agent Response Should Contain")
    @tier(1)
    def agent_response_should_contain(self, result: AgentRunResult, substring: str) -> None:
        """[Tier 1 — Deterministic] Assert `substring` appears in `result.response_text` (PRD FR25).

        Raises:
            `AssertionError`: if the substring is not in the response text.
        """
        if substring not in result.response_text:
            # Story 6.2 code-review HIGH-δ fix (Edge HIGH-4 / FR38a): redact
            # the response-text echo. Response text can carry tokens emitted
            # by the agent (e.g., echoed API keys in error messages).
            raise AssertionError(redact(f"Substring {substring!r} not found in response: {result.response_text!r}"))

    @keyword(name="Agent Response Should Match Regex")
    @tier(1)
    def agent_response_should_match_regex(self, result: AgentRunResult, pattern: str) -> None:
        """[Tier 1 — Deterministic] Assert `pattern` matches `result.response_text` (PRD FR25).

        Uses `re.search` (substring-match by default per the "match"
        terminology in FR25). Multi-line text supported via standard
        `re` flags in the pattern.

        Raises:
            `AssertionError`: if the pattern does not match.
        """
        if not re.search(pattern, result.response_text):
            # Story 6.2 code-review HIGH-δ fix (Edge HIGH-4 / FR38a): redact
            # response-text echo.
            raise AssertionError(redact(f"Pattern {pattern!r} not found in response: {result.response_text!r}"))

    @keyword(name="Agent Response Should Match Schema")
    @tier(1)
    def agent_response_should_match_schema(
        self,
        result: AgentRunResult,
        schema: dict[str, Any] | str | Path,
    ) -> None:
        """[Tier 1 — Deterministic] Assert `response_text` (parsed JSON) validates against schema (PRD FR25).

        Args:
            result: `AgentRunResult`.
            schema: JSON Schema as a dict OR a file path (str or
                `pathlib.Path`) per Story 6.2 D-4 drift fix supporting
                both forms (operator convenience).

        Raises:
            `ValueError`: if `schema` is not a `dict`/`str`/`Path`, OR if
                the str/Path is not a valid file, OR if the loaded JSON is
                not a top-level dict (Story 6.2 code-review HIGH-β fix —
                tightened dispatch so an unexpected `schema` type raises
                the documented `ValueError` instead of leaking a bare
                `TypeError` from `pathlib`).
            `AssertionError`: if `response_text` is not parseable as JSON.
                Failure message is `redact()`-scrubbed per FR38a.
            `jsonschema.ValidationError`: if the parsed JSON does not
                validate against the schema (preserves the jsonschema
                convention so consumers can catch the specific exception).
        """
        resolved = _internal._resolve_schema(schema)
        try:
            parsed = json.loads(result.response_text)
        except json.JSONDecodeError as exc:
            # Story 6.2 code-review HIGH-δ fix (Edge HIGH-4 / FR38a): redact
            # the 200-char response-text excerpt before echoing.
            raise AssertionError(redact(f"response_text is not valid JSON: {result.response_text[:200]!r}")) from exc
        jsonschema.validate(instance=parsed, schema=resolved)
