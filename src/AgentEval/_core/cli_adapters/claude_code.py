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

"""claude-code CLI adapter (fidelity FULL) - the reference parse strategy.

Anthropic's ``claude`` CLI emits newline-delimited JSON events under
``-p --output-format stream-json --verbose``: a ``system``/``init`` event, one
``assistant`` event per turn (carrying ``text`` and ``tool_use`` content blocks
plus incremental ``usage``), ``user`` events carrying ``tool_result`` blocks,
and a final ``result`` event that carries the settled ``usage`` (with a cache
breakdown), a NATIVE ``total_cost_usd``, and ``duration_ms``.

This adapter reads that stream from stdout when present and falls back to the
newest on-disk session transcript (``~/.claude/projects/<slug>/<id>.jsonl``,
same line-shape) when stdout is thin. Both paths normalize into the identical
``AgentRunResult``: final text, per-turn ``tool_calls`` as ``ToolCallTrace``
records, token ``usage`` with cache reads, native cost, and latency.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Literal

from AgentEval._core.cli_adapter import Fidelity, SubprocessCLIAdapter
from AgentEval._core.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


class ClaudeCodeAdapter(SubprocessCLIAdapter):
    """Anthropic ``claude`` CLI: ``claude -p --output-format stream-json --verbose``.

    FULL fidelity - the stream carries tool calls, token usage (with cache
    breakdown), and a native cost, so every normalized field is read from the
    CLI's own accounting rather than estimated.
    """

    slug: ClassVar[str] = "claude-code"
    binary_name: ClassVar[str] = "claude"
    fidelity: ClassVar[Fidelity] = "FULL"
    validation_ceiling: ClassVar[str] = (
        "Reports tool calls, cached/uncached tokens, and native cost from "
        "stream-json; does not capture executed-tool side effects beyond the "
        "tool_result payload the stream emits, and per-tool token/cost "
        "attribution is not broken out by the CLI (left 0 on each ToolCallTrace)."
    )
    # stream-json + --verbose is stable across the claude-code 1.x/2.x line; the
    # bounds are a broad-but-honest guess pending live-smoke confirmation of the
    # exact tested range (ASSUMPTION - see report).
    pinned_version_range: ClassVar[tuple[str, str] | None] = ("1.0.0", "3.0.0")
    install_hint: ClassVar[str] = (
        "Install with: npm install -g @anthropic-ai/claude-code (see https://docs.anthropic.com/en/docs/claude-code)."
    )

    def build_argv(self, prompt: str) -> list[str]:
        """``claude -p <prompt> --output-format stream-json --verbose``.

        ``--verbose`` is required for ``stream-json`` to emit the per-event NDJSON
        the parser consumes. The API key is sourced from the child environment
        (``ANTHROPIC_API_KEY``) by the base - never placed here.
        """
        return [
            self.binary_name,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
        ]

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        """Normalize the stream-json stdout, or the newest session transcript, into a result."""
        events = _parse_ndjson(stdout)
        if not _has_agent_events(events):
            # Thin stdout: fall back to the newest on-disk session transcript.
            transcript = self.find_newest_session_file(session_dir, "*.jsonl")
            if transcript is not None:
                events = _parse_ndjson(_read_text(transcript))
        return _normalize(events, exit_code)


# --------------------------------------------------------------------------- #
# Pure parse helpers - stdout stream-json and the session transcript share a   #
# line-shape, so one normalizer serves both paths.                            #
# --------------------------------------------------------------------------- #


def _parse_ndjson(blob: str) -> list[dict[str, Any]]:
    """Parse newline-delimited JSON, skipping blank and non-object lines."""
    events: list[dict[str, Any]] = []
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def _has_agent_events(events: list[dict[str, Any]]) -> bool:
    """True when the stream carried real assistant/result content worth parsing."""
    return any(ev.get("type") in ("assistant", "result") for ev in events)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _message_content(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of content blocks on an assistant/user event, or []."""
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _stringify(content: Any) -> str:
    """Flatten a tool_result content payload (str | list[block]) into text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", block.get("content", ""))))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _collect_tool_calls(events: list[dict[str, Any]]) -> list[ToolCallTrace]:
    """Pair ``tool_use`` blocks (assistant) with ``tool_result`` blocks (user)."""
    tool_uses: list[tuple[str, str, dict[str, Any]]] = []
    tool_results: dict[str, tuple[Any, bool]] = {}
    for event in events:
        for block in _message_content(event):
            btype = block.get("type")
            if btype == "tool_use":
                args = block.get("input")
                tool_uses.append(
                    (
                        str(block.get("id", "")),
                        str(block.get("name", "")),
                        args if isinstance(args, dict) else {},
                    )
                )
            elif btype == "tool_result":
                tool_results[str(block.get("tool_use_id", ""))] = (
                    block.get("content"),
                    bool(block.get("is_error", False)),
                )

    tool_calls: list[ToolCallTrace] = []
    for index, (tool_id, name, args) in enumerate(tool_uses):
        raw_result, is_error = tool_results.get(tool_id, (None, False))
        tool_calls.append(
            ToolCallTrace(
                name=name,
                args=args,
                result=None if is_error else raw_result,
                error=_stringify(raw_result) if is_error else None,
                source="adapter",
                tool_call_id=tool_id,
                sequence_index=index,
                # Per-tool token/cost attribution is not surfaced by the CLI.
            )
        )
    return tool_calls


def _response_text(events: list[dict[str, Any]], result_event: dict[str, Any] | None) -> str:
    """Prefer the settled ``result`` field; else concatenate assistant text blocks."""
    if result_event is not None:
        settled = result_event.get("result")
        if isinstance(settled, str) and settled:
            return settled
    parts: list[str] = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in _message_content(event):
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
    return "".join(parts)


def _int(value: Any) -> int:
    """Coerce a possibly-missing count to a non-negative int (Usage rejects negatives)."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _usage_from(usage: dict[str, Any]) -> Usage:
    """Map claude usage to ``Usage``; cached = cache-read tokens."""
    return Usage(
        input_tokens=_int(usage.get("input_tokens")),
        output_tokens=_int(usage.get("output_tokens")),
        # cache_read_input_tokens = tokens served from the prompt cache this run.
        cached_input_tokens=_int(usage.get("cache_read_input_tokens")),
    )


def _pick_usage(events: list[dict[str, Any]], result_event: dict[str, Any] | None) -> Usage:
    """Settled usage from the ``result`` event; else the last assistant usage."""
    if result_event is not None and isinstance(result_event.get("usage"), dict):
        return _usage_from(result_event["usage"])
    for event in reversed(events):
        if event.get("type") != "assistant":
            continue
        message = event.get("message")
        if isinstance(message, dict) and isinstance(message.get("usage"), dict):
            return _usage_from(message["usage"])
    return Usage(input_tokens=0, output_tokens=0)


def _completeness(
    result_event: dict[str, Any] | None,
) -> Literal["complete", "truncated", "partial"]:
    """Map the CLI's terminal subtype to a completeness label.

    ``success`` -> complete; ``error_max_turns`` (turn budget hit) -> truncated;
    any other terminal error, or no terminal event at all -> partial.
    """
    if result_event is None:
        return "partial"
    if result_event.get("is_error"):
        return "partial"
    subtype = result_event.get("subtype")
    if subtype == "success":
        return "complete"
    if subtype == "error_max_turns":
        return "truncated"
    return "partial"


def _normalize(events: list[dict[str, Any]], exit_code: int) -> AgentRunResult:
    """Build the ``AgentRunResult`` from parsed events (empty -> honest empty result)."""
    result_event: dict[str, Any] | None = None
    for event in events:
        if event.get("type") == "result":
            result_event = event  # last result event wins

    if not events:
        # Nothing parseable from stdout or transcript: do not fabricate numbers.
        return AgentRunResult(
            response_text="",
            metadata=AgentRunMetadata(
                completeness="partial",
                mcp_coverage="subprocess_with_observer",
                metric_source="none",
            ),
        )

    tool_calls = _collect_tool_calls(events)
    usage = _pick_usage(events, result_event)
    response_text = _response_text(events, result_event)

    native_cost = result_event.get("total_cost_usd") if result_event is not None else None
    cost_usd, metric_source = SubprocessCLIAdapter.resolve_cost(
        native_cost if isinstance(native_cost, (int, float)) else None
    )

    latency_seconds = 0.0
    if result_event is not None:
        duration_ms = result_event.get("duration_ms")
        if isinstance(duration_ms, (int, float)):
            latency_seconds = float(duration_ms) / 1000.0

    trace_id = ""
    if result_event is not None:
        trace_id = str(result_event.get("session_id", ""))

    return AgentRunResult(
        response_text=response_text,
        tool_calls=tool_calls,
        usage=usage,
        cost_usd=cost_usd,
        latency_seconds=latency_seconds,
        trace_id=trace_id,
        metadata=AgentRunMetadata(
            completeness=_completeness(result_event),
            mcp_coverage="subprocess_with_observer",
            metric_source=metric_source,
            # agent_version left blank so the base stamps the probed --version.
        ),
    )
