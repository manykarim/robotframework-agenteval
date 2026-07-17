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

"""copilot CLI adapter (fidelity DEGRADED).

The GitHub Copilot CLI (``copilot``) runs non-interactively via ``-p/--prompt``.
Recent versions (confirmed on 1.0.54) add ``--output-format json`` which streams
a JSONL event log to stdout - the same event schema the CLI persists on disk at
``~/.copilot/session-state/<uuid>/events.jsonl``. This adapter parses that event
stream best-effort, falling back to the newest on-disk ``events.jsonl`` when
stdout is thin.

copilot is DEGRADED for one hard reason: **it never reports a USD cost.** The
only cost-ish signal is ``totalPremiumRequests`` (a request counter, not
dollars), so ``cost_usd`` is always 0 and ``metric_source="none"``. Token counts
and tool calls are reconstructed from the event stream where present. The
``validation_ceiling`` names exactly what cannot be reported so a degraded run
never reads as fake-green.
"""

from __future__ import annotations

import json
import os
from typing import Any, ClassVar, Literal

from AgentEval._core.cli_adapter import Fidelity, SubprocessCLIAdapter
from AgentEval._core.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

# ASSUMPTION: when the caller supplies no session_dir, copilot writes its event
# log under this per-user directory (confirmed on 1.0.54). Used only as the
# thin-stdout fallback source.
_DEFAULT_SESSION_ROOT = os.path.join(os.path.expanduser("~"), ".copilot", "session-state")


class CopilotAdapter(SubprocessCLIAdapter):
    """GitHub ``copilot`` CLI: ``copilot -p --output-format json`` (JSONL events).

    DEGRADED fidelity - no USD cost is ever reported (only a premiumRequests
    counter, which is not dollars), so cost_usd is 0 and metric_source=none.
    Tokens and tool calls are reconstructed from the JSONL event stream / on-disk
    session log. Carries a VALIDATION-CEILING marker.
    """

    slug: ClassVar[str] = "copilot"
    binary_name: ClassVar[str] = "copilot"
    fidelity: ClassVar[Fidelity] = "DEGRADED"
    validation_ceiling: ClassVar[str] = (
        "VALIDATION-CEILING: copilot reports no USD cost (only a premiumRequests "
        "counter, which is NOT dollars), so cost_usd is always 0 and "
        "metric_source=none. Token counts and tool calls are reconstructed "
        "best-effort from the JSONL event stream / on-disk session log; per-tool "
        "token attribution is unavailable. Do not treat copilot runs as a "
        "complete metric source."
    )
    # Parse logic was confirmed against copilot 1.0.54 (the version that ships
    # `--output-format json`). Older majors lack JSONL stdout; warn on a major
    # bump where the event schema is most likely to shift.
    pinned_version_range: ClassVar[tuple[str, str] | None] = ("1.0.0", "1.99.99")
    install_hint: ClassVar[str] = (
        "Install the GitHub Copilot CLI per https://docs.github.com/copilot; the adapter expects it on PATH."
    )

    def build_argv(self, prompt: str) -> list[str]:
        # `-p` runs non-interactively and exits after completion.
        # `--allow-all-tools` is documented as required for non-interactive mode
        # (otherwise the CLI blocks on a permission prompt).
        # ASSUMPTION: `--output-format json` emits the same JSONL event schema the
        # CLI persists to events.jsonl (confirmed on 1.0.54). No secrets on argv -
        # copilot reads its token from os.environ / its own credential store.
        return [self.binary_name, "-p", prompt, "--allow-all-tools", "--output-format", "json"]

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        events = _load_events(stdout, session_dir)
        return _normalize(events, exit_code)


# --------------------------------------------------------------------------- #
# Event loading + normalization (module-level so unit tests can drive them     #
# with recorded fixtures without spawning the real binary).                    #
# --------------------------------------------------------------------------- #


def _load_events(stdout: str, session_dir: str | None) -> list[dict[str, Any]]:
    """Parse the JSONL event stream from stdout, falling back to the on-disk session log."""
    events = _parse_jsonl(stdout)
    if events:
        return events
    root = session_dir if session_dir is not None else _DEFAULT_SESSION_ROOT
    newest = SubprocessCLIAdapter.find_newest_session_file(root, "events.jsonl")
    if newest is not None:
        try:
            return _parse_jsonl(newest.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return []
    return []


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    """Parse one JSON object per line, keeping only typed event dicts."""
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate interleaved non-JSON banner/log lines
        if isinstance(obj, dict) and "type" in obj:
            events.append(obj)
    return events


def _normalize(events: list[dict[str, Any]], exit_code: int) -> AgentRunResult:
    """Fold copilot JSONL events into an ``AgentRunResult`` (best-effort, DEGRADED)."""
    response_texts: list[str] = []
    starts: list[dict[str, Any]] = []
    completes: dict[str, dict[str, Any]] = {}
    request_fallback: list[dict[str, Any]] = []
    shutdown: dict[str, Any] | None = None
    timestamps: list[int] = []
    session_start: int | None = None

    for event in events:
        event_type = event.get("type")
        data = _as_dict(event.get("data"))
        ts = event.get("timestamp")
        if isinstance(ts, (int, float)) and not isinstance(ts, bool):
            timestamps.append(int(ts))

        if event_type == "assistant.message":
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                response_texts.append(content)
            requests = data.get("toolRequests")
            if isinstance(requests, list):
                request_fallback.extend(r for r in requests if isinstance(r, dict))
        elif event_type == "tool.execution_start":
            starts.append(data)
        elif event_type == "tool.execution_complete":
            call_id = data.get("toolCallId")
            if isinstance(call_id, str):
                completes[call_id] = data
        elif event_type == "session.shutdown":
            shutdown = data
            start = data.get("sessionStartTime")
            if isinstance(start, (int, float)) and not isinstance(start, bool):
                session_start = int(start)

    tool_calls = _tool_calls(starts, completes, request_fallback)
    usage = _usage(shutdown)
    # copilot never reports USD; premiumRequests is a request counter, not dollars.
    # Leave cost 0 and metric_source=none rather than fabricate a dollar figure.
    metadata = AgentRunMetadata(
        completeness=_completeness(bool(events), shutdown is not None, exit_code),
        mcp_coverage="subprocess_with_observer",
        metric_source="none",
    )
    return AgentRunResult(
        response_text="\n".join(response_texts),
        tool_calls=tool_calls,
        usage=usage,
        metadata=metadata,
        cost_usd=0.0,
        latency_seconds=_latency_seconds(session_start, timestamps),
    )


def _tool_calls(
    starts: list[dict[str, Any]],
    completes: dict[str, dict[str, Any]],
    request_fallback: list[dict[str, Any]],
) -> list[ToolCallTrace]:
    """Build ToolCallTrace records, matching execution_start -> execution_complete by id."""
    if starts:
        traces: list[ToolCallTrace] = []
        for index, start in enumerate(starts):
            call_id = str(start.get("toolCallId") or "")
            name = start.get("toolName") or start.get("name") or ""
            args = _as_dict(start.get("arguments"))
            complete = completes.get(call_id, {})
            result_obj = complete.get("result")
            result = result_obj.get("content") if isinstance(result_obj, dict) else result_obj
            success = complete.get("success")
            error = None
            if success is False:
                error = str(result if result is not None else "tool execution reported failure")
            traces.append(
                ToolCallTrace(
                    name=str(name),
                    args=args,
                    result=result,
                    error=error,
                    tool_call_id=call_id,
                    sequence_index=index,
                )
            )
        return traces
    # Fallback: no execution_start events (thin stream) - reconstruct request-only
    # traces from assistant.message.toolRequests. Results are unavailable here.
    traces = []
    for index, request in enumerate(request_fallback):
        args = _as_dict(request.get("arguments"))
        traces.append(
            ToolCallTrace(
                name=str(request.get("name") or ""),
                args=args,
                tool_call_id=str(request.get("toolCallId") or ""),
                sequence_index=index,
            )
        )
    return traces


def _usage(shutdown: dict[str, Any] | None) -> Usage:
    """Sum per-model token usage from the session.shutdown summary."""
    if not shutdown:
        return Usage(input_tokens=0, output_tokens=0)
    model_metrics = shutdown.get("modelMetrics")
    if not isinstance(model_metrics, dict):
        return Usage(input_tokens=0, output_tokens=0)
    input_tokens = 0
    output_tokens = 0
    cached_tokens = 0
    for stats in model_metrics.values():
        if not isinstance(stats, dict):
            continue
        usage = stats.get("usage")
        if not isinstance(usage, dict):
            continue
        input_tokens += _as_int(usage.get("inputTokens"))
        output_tokens += _as_int(usage.get("outputTokens"))
        cached_tokens += _as_int(usage.get("cacheReadTokens"))
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens, cached_input_tokens=cached_tokens)


def _latency_seconds(session_start: int | None, timestamps: list[int]) -> float:
    if session_start is None or not timestamps:
        return 0.0
    delta_ms = max(timestamps) - session_start
    return delta_ms / 1000.0 if delta_ms > 0 else 0.0


def _completeness(has_events: bool, has_shutdown: bool, exit_code: int) -> Literal["complete", "truncated", "partial"]:
    if not has_events:
        return "partial"
    if has_shutdown and exit_code == 0:
        return "complete"
    return "truncated"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0
