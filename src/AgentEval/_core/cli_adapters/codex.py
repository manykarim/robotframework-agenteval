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

"""codex CLI adapter (fidelity PARTIAL).

Invocation: ``codex exec "<prompt>" --json`` run non-interactively (see
``build_argv``). The CLI streams newline-delimited JSON (JSONL) events on stdout.
``item.completed`` events span several item types - assistant messages
(``agent_message``), ``command_execution`` shell runs, and ``mcp_tool_call``
invocations - which we project into ``ToolCallTrace`` records. Live-confirmed
against codex 0.144.4: assistant text lands on ``item.type == "agent_message"``
under ``text``, and cumulative token usage arrives under ``usage`` on
``turn.completed`` events.

Token usage is reported *cumulatively* across turns, so summing every usage
event double-counts; we DE-CUMULATE (diff consecutive snapshots) to recover the
true run total. Cost is *derived* via ``litellm.completion_cost`` (the CLI
reports no native dollar cost). When stdout is thin (no parseable events), we
fall back to the newest on-disk rollout transcript under ``~/.codex/sessions/``.

VALIDATION-CEILING: per-tool token attribution is not available (usage is
run-level and cumulative, not per item); wall-clock latency is not reported in
the JSONL, so ``latency_seconds`` stays 0 unless a duration is present. The item
type / usage spellings are confirmed for 0.144.4 but remain version-sensitive
(``AdapterVersionDriftWarning`` fires outside the pinned range).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, ClassVar, Literal

from AgentEval._core.cli_adapter import Fidelity, MetricSource, SubprocessCLIAdapter
from AgentEval._core.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

# Default on-disk rollout location when the caller supplies no session_dir.
_DEFAULT_SESSIONS_DIR = "~/.codex/sessions"

# item.type values we treat as an assistant text message (version-sensitive).
_ASSISTANT_ITEM_TYPES = frozenset(("assistant_message", "agent_message"))


class CodexAdapter(SubprocessCLIAdapter):
    """OpenAI ``codex`` CLI: ``codex exec --json``.

    PARTIAL fidelity - tool calls (command executions + MCP calls) are captured;
    token counts arrive cumulative and are de-cumulated to a run total; cost is
    derived. Per-tool token attribution is not available.
    """

    slug: ClassVar[str] = "codex"
    binary_name: ClassVar[str] = "codex"
    fidelity: ClassVar[Fidelity] = "PARTIAL"
    validation_ceiling: ClassVar[str] = (
        "Tool calls (command executions + MCP calls) captured from --json JSONL; "
        "token counts are run-level and de-cumulated from cumulative snapshots "
        "(no reliable per-tool attribution); cost is derived, not native; "
        "wall-clock latency is not reported in the JSONL (stays 0)."
    )
    # Cumulative-token de-cumulation is the behavior for codex exec --json after
    # the 2025-09 rework; pin generously and warn on drift outside it. Live-confirmed
    # against codex 0.144.4 (agent_message text + turn.completed usage schema).
    pinned_version_range: ClassVar[tuple[str, str] | None] = ("0.2.0", "1.0.0")
    install_hint: ClassVar[str] = "Install with: npm install -g @openai/codex (see https://github.com/openai/codex)."

    _SANDBOX_MODES: ClassVar[frozenset[str]] = frozenset(("read-only", "workspace-write", "danger-full-access"))

    def __init__(self, *, sandbox: str = "workspace-write", dangerous_bypass: bool = False, **_kwargs: Any) -> None:
        """Configure how codex runs non-interactively.

        ``sandbox`` is the codex sandbox policy (``read-only`` / ``workspace-write``
        / ``danger-full-access``); the default ``workspace-write`` lets a measurement
        run write within its working directory without prompting. ``dangerous_bypass``
        opts into ``--dangerously-bypass-approvals-and-sandbox`` (no sandbox at all,
        EXTREMELY DANGEROUS - only for an already-externally-sandboxed environment).
        """
        if sandbox not in self._SANDBOX_MODES:
            raise ValueError(f"sandbox must be one of {sorted(self._SANDBOX_MODES)}; got {sandbox!r}")
        self._sandbox = sandbox
        self._dangerous_bypass = dangerous_bypass

    def build_argv(self, prompt: str) -> list[str]:
        """``codex exec "<prompt>" --json`` run non-interactively. No secrets on argv.

        codex 0.144.4 needs ``--skip-git-repo-check`` (run outside a trusted git
        dir) and a non-interactive execution mode, else it exits or waits for an
        approval that never comes. The default is a bounded sandbox
        (``--sandbox <mode>``) with ``approval_policy=never`` - NOT the dangerous
        full bypass, which is opt-in via ``dangerous_bypass=True``.
        """
        argv = [self.binary_name, "exec", prompt, "--json", "--skip-git-repo-check"]
        if self._dangerous_bypass:
            argv.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            argv += ["--sandbox", self._sandbox, "-c", "approval_policy=never"]
        return argv

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        """Normalize the ``--json`` JSONL stream (or rollout fallback) into a result."""
        events = _parse_jsonl(stdout)
        if not events:
            # Thin stdout: fall back to the newest on-disk rollout transcript.
            events = self._events_from_rollout(session_dir)

        response_text = _extract_response_text(events)
        tool_calls = _extract_tool_calls(events)
        usage = _extract_usage(events)
        model_name = _extract_model(events)

        cost_usd = 0.0
        metric_source: MetricSource = "none"
        if model_name and (usage.input_tokens or usage.output_tokens):
            cost_usd, metric_source = self.resolve_cost(
                None,
                completion_response={
                    "model": model_name,
                    "usage": {
                        "prompt_tokens": usage.input_tokens,
                        "completion_tokens": usage.output_tokens,
                        "total_tokens": usage.input_tokens + usage.output_tokens,
                    },
                },
            )

        completeness: Literal["complete", "partial"] = "complete" if exit_code == 0 else "partial"
        return AgentRunResult(
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            metadata=AgentRunMetadata(
                completeness=completeness,
                mcp_coverage="subprocess_with_observer",
                metric_source=metric_source,
                # agent_version left blank: the base stamps the probed --version.
            ),
            cost_usd=cost_usd,
            latency_seconds=0.0,  # not reported in the JSONL (see VALIDATION-CEILING)
        )

    def _events_from_rollout(self, session_dir: str | None) -> list[dict[str, Any]]:
        """Read + parse the newest rollout transcript as JSONL, best-effort."""
        directory = session_dir or os.path.expanduser(_DEFAULT_SESSIONS_DIR)
        newest = self.find_newest_session_file(directory, pattern="*.jsonl")
        if newest is None:
            return []
        try:
            text = Path(newest).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return _parse_jsonl(text)


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    """Parse newline-delimited JSON into a list of dict events; skip bad lines."""
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def _item_of(event: dict[str, Any]) -> dict[str, Any]:
    """Return the ``item`` payload of an ``item.completed`` event, else the event.

    Rollout transcripts sometimes carry the item fields at the top level rather
    than nested under ``item`` - accept both shapes.
    """
    item = event.get("item")
    if isinstance(item, dict):
        return item
    return event


def _extract_response_text(events: list[dict[str, Any]]) -> str:
    """Return the last assistant message's text across the events."""
    text = ""
    for event in events:
        item = _item_of(event)
        # ASSUMPTION: assistant text lands on item.type in _ASSISTANT_ITEM_TYPES
        # with the message under the "text" key (version-sensitive spelling).
        if item.get("type") in _ASSISTANT_ITEM_TYPES:
            candidate = item.get("text")
            if isinstance(candidate, str) and candidate:
                text = candidate
    return text


def _extract_tool_calls(events: list[dict[str, Any]]) -> list[ToolCallTrace]:
    """Project ``command_execution`` + ``mcp_tool_call`` items into traces, in order."""
    traces: list[ToolCallTrace] = []
    sequence_index = 0
    for event in events:
        item = _item_of(event)
        item_type = item.get("type")
        trace: ToolCallTrace | None = None
        if item_type == "command_execution":
            trace = _command_execution_trace(item, sequence_index)
        elif item_type == "mcp_tool_call":
            trace = _mcp_tool_call_trace(item, sequence_index)
        if trace is not None:
            traces.append(trace)
            sequence_index += 1
    return traces


def _command_execution_trace(item: dict[str, Any], sequence_index: int) -> ToolCallTrace:
    """One shell ``command_execution`` item -> a ``ToolCallTrace`` (source=adapter)."""
    # ASSUMPTION: command under "command"; captured output under
    # "aggregated_output" (fallback "output"); shell exit under "exit_code".
    command = item.get("command")
    output = item.get("aggregated_output")
    if output is None:
        output = item.get("output")
    exit_code = item.get("exit_code")
    error = None
    if isinstance(exit_code, int) and exit_code != 0:
        error = f"command exited with code {exit_code}"
    return ToolCallTrace(
        name="command_execution",
        args={"command": command} if command is not None else {},
        result=output,
        error=error,
        source="adapter",
        tool_call_id=str(item.get("id") or ""),
        sequence_index=sequence_index,
    )


def _mcp_tool_call_trace(item: dict[str, Any], sequence_index: int) -> ToolCallTrace:
    """One ``mcp_tool_call`` item -> a ``ToolCallTrace`` (source=hosted_mcp)."""
    # ASSUMPTION: MCP server under "server", tool under "tool", args under
    # "arguments", result under "result"; failure signaled by status=="failed"
    # or a truthy "is_error".
    server = item.get("server")
    tool = item.get("tool")
    name = f"{server}.{tool}" if server and tool else str(tool or server or "mcp_tool_call")
    raw_args = item.get("arguments")
    args = raw_args if isinstance(raw_args, dict) else ({"_raw": raw_args} if raw_args is not None else {})
    status = item.get("status")
    is_error = bool(item.get("is_error"))
    error = None
    if is_error or (isinstance(status, str) and status.lower() in ("failed", "error")):
        error = f"MCP tool call failed (status={status!r})" if status else "MCP tool call failed"
    return ToolCallTrace(
        name=name,
        args=args,
        result=item.get("result"),
        error=error,
        source="hosted_mcp",
        tool_call_id=str(item.get("id") or ""),
        sequence_index=sequence_index,
    )


def _extract_usage(events: list[dict[str, Any]]) -> Usage:
    """De-cumulate cumulative token snapshots into a run-total ``Usage``.

    codex reports token usage cumulatively (each snapshot is the running total).
    We diff consecutive snapshots per field and sum the deltas: for a monotonic
    cumulative stream this equals the final snapshot, and a mid-run reset (a
    snapshot smaller than the previous) is counted fresh rather than going
    negative.
    """
    snapshots = [snap for snap in (_usage_snapshot(e) for e in events) if snap is not None]
    if not snapshots:
        return Usage(input_tokens=0, output_tokens=0)

    total_input = 0
    total_output = 0
    total_cached = 0
    prev_input = prev_output = prev_cached = 0
    for cur_input, cur_output, cur_cached in snapshots:
        total_input += cur_input - prev_input if cur_input >= prev_input else cur_input
        total_output += cur_output - prev_output if cur_output >= prev_output else cur_output
        total_cached += cur_cached - prev_cached if cur_cached >= prev_cached else cur_cached
        prev_input, prev_output, prev_cached = cur_input, cur_output, cur_cached

    return Usage(
        input_tokens=max(total_input, 0),
        output_tokens=max(total_output, 0),
        cached_input_tokens=max(total_cached, 0),
    )


def _usage_snapshot(event: dict[str, Any]) -> tuple[int, int, int] | None:
    """Extract a cumulative ``(input, output, cached)`` snapshot from an event.

    Accepts the counts under a nested ``usage`` object or on the event/item
    itself. Returns ``None`` when no token fields are present.
    """
    # ASSUMPTION: cumulative counts live under a "usage" dict on turn.completed
    # events with keys input_tokens / output_tokens / cached_input_tokens.
    for container in (event.get("usage"), _item_of(event).get("usage"), event, _item_of(event)):
        if not isinstance(container, dict):
            continue
        if "input_tokens" in container or "output_tokens" in container:
            return (
                _as_int(container.get("input_tokens")),
                _as_int(container.get("output_tokens")),
                _as_int(container.get("cached_input_tokens")),
            )
    return None


def _extract_model(events: list[dict[str, Any]]) -> str:
    """Find a model id in the event stream (for cost derivation); '' if none."""
    # ASSUMPTION: the model id appears as a "model" string on an early event
    # (e.g. thread.started / turn.started) or nested in its item.
    for event in events:
        for container in (event, _item_of(event)):
            model = container.get("model")
            if isinstance(model, str) and model:
                return model
    return ""


def _as_int(value: Any) -> int:
    """Coerce a token-count value to a non-negative int, 0 on anything odd."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value if value >= 0 else 0
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result >= 0 else 0
