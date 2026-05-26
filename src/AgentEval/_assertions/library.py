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

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions
# on a single physical line. Per-line 120-char limit waived for this
# file per Phase 3 docstring-refresh proposal (2026-05-26).

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

# Browser-Library-style docstring migration marker (Phase 3, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


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
        """Asserts the agent's tool-call trajectory matches an expected sequence (PRD FR23a + FR23b).

        [Tier 1 — Deterministic] — four match modes available. Failure
        messages are ``redact()``-scrubbed per FR38a so credentials in
        tool args don't leak into RF logs.

        | =Arguments= | =Description= |
        | ``result`` | ``AgentRunResult`` carrying the observed ``tool_calls``. |
        | ``expected`` | List of expected tool names (or regex patterns when ``mode="regex"``). |
        | ``mode`` | Match mode: ``"exact"`` (ordered equality) / ``"subsequence"`` (ordered, extras allowed between) / ``"set"`` (unordered set-equality of distinct names) / ``"regex"`` (each ``expected[i]`` is a ``re.fullmatch`` pattern against ``<tool>:<json.dumps(args, sort_keys=True)>``). Default ``"exact"``. |

        Set-mode caveat: duplicate names collapse — ``["a", "a"]`` set-
        equals ``["a"]``. Operators wanting multiset semantics ("exactly
        N calls of tool X") should use ``mode="exact"``.

        Raises ``ValueError`` when ``mode`` is not one of the 4 documented
        values (caller-typo gate fires BEFORE the FR37 coverage gate).
        Raises ``IncompleteTraceError`` per FR37 on
        ``mcp_coverage="external_mixed"`` + ``allow_external_mcp_blind=False``.
        Raises ``AssertionError`` on trajectory mismatch.

        Example (illustrative — assumes a real adapter with the expected 3-call trajectory):
        | ${result} =    `Send Prompt`    prompt=Find news    adapter=generic    provider=mock
        | `Trajectory Should Match`    ${result}    ${{['web_search', 'fetch', 'summarize']}}
        | `Trajectory Should Match`    ${result}    ${{['web_search', 'summarize']}}    mode=subsequence
        | `Trajectory Should Match`    ${result}    ${{['fetch', 'web_search']}}    mode=set
        | `Trajectory Should Match`    ${result}    ${{['web_search:.*', 'fetch:.*', 'summarize:.*']}}    mode=regex

        Notes:
        - PRD FR23a + FR23b ratify the 4 match modes.
        - mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.
        - Sibling keyword: `Tool Call Should Have Occurred` for single-call name+args assertions.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Asserts that a tool call with the given name (and optional args) occurred (PRD FR24).

        [Tier 1 — Deterministic] — searches all observed ``tool_calls``
        for one matching ``tool`` + (optionally) ``args``. Failure
        messages are ``redact()``-scrubbed per FR38a.

        | =Arguments= | =Description= |
        | ``result`` | ``AgentRunResult`` carrying the observed ``tool_calls``. |
        | ``tool`` | Expected tool name (exact-match required). |
        | ``args`` | Optional dict of expected args. ``None`` (default) = name-only match. |
        | ``match_mode`` | ``"subset"`` (default — ``args`` is a dict-subset of ``tc.args``; recursive for nested dicts) OR ``"exact"`` (``tc.args == args``). |

        Raises ``ValueError`` when ``match_mode`` is invalid (caller-typo
        gate fires BEFORE the FR37 coverage gate). Raises
        ``IncompleteTraceError`` per FR37 on
        ``mcp_coverage="external_mixed"`` + ``allow_external_mcp_blind=False``.
        Raises ``AssertionError`` when no tool call matches.

        Example (illustrative — assumes a real adapter with the expected ``web_search`` call):
        | ${result} =    `Send Prompt`    prompt=Find news    adapter=generic    provider=mock
        | `Tool Call Should Have Occurred`    ${result}    web_search
        | `Tool Call Should Have Occurred`    ${result}    web_search    args=${{ {"query": "agenteval"} }}
        | `Tool Call Should Have Occurred`    ${result}    web_search    args=${{ {"query": "x"} }}    match_mode=exact

        Notes:
        - PRD FR24 ratifies the name + args + match-mode contract.
        - mcp_coverage gating per FR37 + FR42; failure-message redaction per FR38a + Story 5.3.
        - Sibling keyword: `Trajectory Should Match` for ordered-sequence assertions over multiple calls.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Asserts that ``substring`` appears in ``result.response_text`` (PRD FR25).

        [Tier 1 — Deterministic] — provider-reported scalar; NOT
        ``mcp_coverage``-gated. Failure messages are ``redact()``-scrubbed
        per FR38a.

        | =Arguments= | =Description= |
        | ``result`` | ``AgentRunResult`` carrying ``response_text``. |
        | ``substring`` | Literal substring to match. Case-sensitive. |

        Raises ``AssertionError`` when the substring is not found.

        Example:
        | ${result} =    `Send Prompt`    prompt=Robot Framework is a test automation framework    adapter=generic    provider=mock
        | `Agent Response Should Contain`    ${result}    Robot Framework                                          # Mock echoes the prompt.
        | `Agent Response Should Contain`    ${result}    test automation

        Notes:
        - PRD FR25 ratifies the 3 response assertions (Contain / Match Regex / Match Schema).
        - Response text is observer-independent — no mcp_coverage gate.
        - Failure-message redaction per FR38a + Story 5.3.
        - Sibling keywords: `Agent Response Should Match Regex` (regex), `Agent Response Should Match Schema` (JSON schema).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if substring not in result.response_text:
            # Story 6.2 code-review HIGH-δ fix (Edge HIGH-4 / FR38a): redact
            # the response-text echo. Response text can carry tokens emitted
            # by the agent (e.g., echoed API keys in error messages).
            raise AssertionError(redact(f"Substring {substring!r} not found in response: {result.response_text!r}"))

    @keyword(name="Agent Response Should Match Regex")
    @tier(1)
    def agent_response_should_match_regex(self, result: AgentRunResult, pattern: str) -> None:
        """Asserts a regex pattern matches ``result.response_text`` (PRD FR25).

        [Tier 1 — Deterministic] — uses ``re.search`` (substring-match by
        default per FR25's "match" terminology). Multi-line text supported
        via standard ``re`` flags in the pattern. NOT
        ``mcp_coverage``-gated. Failure messages are ``redact()``-scrubbed
        per FR38a.

        | =Arguments= | =Description= |
        | ``result`` | ``AgentRunResult`` carrying ``response_text``. |
        | ``pattern`` | Python ``re`` pattern. Use ``(?i)`` / ``(?m)`` / ``(?s)`` inline flags as needed. |

        Raises ``AssertionError`` when the pattern does not match.

        Example:
        | ${result} =    `Send Prompt`    prompt=Released in 2020 — Robot Framework 3.x    adapter=generic    provider=mock
        | `Agent Response Should Match Regex`    ${result}    20\\d{2}                          # 4-digit year — matches the echoed "2020".
        | `Agent Response Should Match Regex`    ${result}    (?i)robot.*framework              # Case-insensitive multi-word.

        Notes:
        - PRD FR25 ratifies the regex assertion; `re.search` semantics (not `re.fullmatch`).
        - Response text is observer-independent — no mcp_coverage gate.
        - Failure-message redaction per FR38a + Story 5.3.
        - Sibling keywords: `Agent Response Should Contain` (literal substring), `Agent Response Should Match Schema` (JSON schema).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
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
        """Asserts ``response_text`` parses as JSON + validates against a JSON Schema (PRD FR25).

        [Tier 1 — Deterministic] — provider-reported scalar; NOT
        ``mcp_coverage``-gated. Parses ``response_text`` as JSON, then
        validates against the schema via ``jsonschema``.

        | =Arguments= | =Description= |
        | ``result`` | ``AgentRunResult`` carrying ``response_text`` (expected to be JSON-parsable). |
        | ``schema`` | JSON Schema as a ``dict`` OR a file path (``str`` / ``pathlib.Path``). |

        Raises ``ValueError`` when ``schema`` is not a ``dict``/``str``/``Path``,
        or when the file is not a valid JSON schema dict. Raises
        ``AssertionError`` (redacted per FR38a) when ``response_text`` is
        not JSON-parsable. Raises ``jsonschema.ValidationError`` when the
        parsed JSON does not validate against the schema (preserves the
        jsonschema convention so consumers can catch the specific
        exception).

        Example:
        | ${result} =    `Send Prompt`    prompt={"answer": 42}    adapter=generic    provider=mock
        | `Agent Response Should Match Schema`    ${result}    ${{ {"type": "object", "required": ["answer"]} }}
        | # Path form: `Agent Response Should Match Schema`    ${result}    ${CURDIR}/schemas/response.json    (requires the schema file to exist)

        Notes:
        - PRD FR25 ratifies the schema-validation contract; Story 6.2 D-4 supports both dict + path forms.
        - Uses ``jsonschema`` package — the upstream ``ValidationError`` is preserved on validation failure (callers can catch specifically).
        - Failure-message redaction per FR38a + Story 5.3.
        - Sibling keywords: `Agent Response Should Contain` (literal substring), `Agent Response Should Match Regex` (regex pattern).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        resolved = _internal._resolve_schema(schema)
        try:
            parsed = json.loads(result.response_text)
        except json.JSONDecodeError as exc:
            # Story 6.2 code-review HIGH-δ fix (Edge HIGH-4 / FR38a): redact
            # the 200-char response-text excerpt before echoing.
            raise AssertionError(redact(f"response_text is not valid JSON: {result.response_text[:200]!r}")) from exc
        jsonschema.validate(instance=parsed, schema=resolved)
