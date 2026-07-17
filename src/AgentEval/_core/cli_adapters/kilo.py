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

"""kilo CLI adapter (fidelity DEGRADED).

kilo is an opencode-derived TUI/agent runner. In headless mode
``kilo run --auto --format json <prompt>`` emits raw JSON events on stdout and
persists a message/part transcript on disk (``kilo export <sessionID>`` renders
the same shape). The stream event *envelope* is undocumented and version-gated,
so this adapter parses the message/part transcript **best-effort**: it reads
native token counts and native USD cost when the transcript exposes them and
leaves the numbers at 0 (``metric_source="none"``) when it cannot, per the
DEGRADED contract. Everything it cannot reliably report is named in
``validation_ceiling`` so a degraded run never reads as fake-green.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, Literal

from AgentEval._core.cli_adapter import Fidelity, SubprocessCLIAdapter
from AgentEval._core.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


class KiloAdapter(SubprocessCLIAdapter):
    """``kilo`` CLI: ``kilo run --auto --format json`` (best-effort transcript parse).

    DEGRADED fidelity - the ``--format json`` event schema is undocumented and
    version-gated, so tokens/cost are read only when the transcript exposes them
    and left 0 otherwise. Carries a VALIDATION-CEILING marker so metrics never
    read a degraded run as complete.
    """

    slug: ClassVar[str] = "kilo"
    binary_name: ClassVar[str] = "kilo"
    fidelity: ClassVar[Fidelity] = "DEGRADED"
    validation_ceiling: ClassVar[str] = (
        "VALIDATION-CEILING: kilo's `run --format json` event schema is "
        "undocumented and version-gated; this adapter parses the message/part "
        "transcript best-effort. Native token counts and native USD cost are read "
        "only when the transcript exposes them and left 0 (metric_source=none) "
        "otherwise. Tool-call results are limited to what the transcript records. "
        "Do not treat kilo runs as a complete metric source."
    )
    # Parse logic was confirmed against kilo 7.3.0 (opencode-derived transcript
    # shape). The parser is deliberately tolerant across the 7.x line; a major
    # bump is where the undocumented JSON shape is most likely to break, so warn
    # outside major 7.
    pinned_version_range: ClassVar[tuple[str, str] | None] = ("7.0.0", "7.99.99")
    install_hint: ClassVar[str] = "Install the kilo CLI per its documentation; the adapter expects it on PATH."

    def build_argv(self, prompt: str) -> list[str]:
        # ASSUMPTION: the headless flag is `--format json` (confirmed via
        # `kilo run --help` on 7.3.0), NOT the `--json` spelling some docs use -
        # `--json` is not a recognised flag and would error. `--auto`
        # auto-approves permissions for pipeline use. The prompt is a positional
        # message; no secrets on argv (kilo reads credentials from its own auth
        # store / os.environ).
        return [self.binary_name, "run", "--auto", "--format", "json", prompt]

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        messages = _load_messages(stdout, session_dir)
        return _normalize(messages, exit_code)


# --------------------------------------------------------------------------- #
# Transcript loading + normalization (module-level so unit tests can drive     #
# them with recorded fixtures without spawning the real binary).               #
# --------------------------------------------------------------------------- #


def _load_messages(stdout: str, session_dir: str | None) -> list[dict[str, Any]]:
    """Collect message dicts from stdout JSON, falling back to the on-disk transcript."""
    messages = _extract_messages(_iter_json(stdout))
    if messages:
        return messages
    # Thin/empty stdout: fall back to the newest on-disk session transcript.
    newest = SubprocessCLIAdapter.find_newest_session_file(session_dir, "*.json")
    if newest is not None:
        try:
            payload = json.loads(newest.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            return []
        return _extract_messages([payload])
    return []


def _iter_json(text: str) -> list[Any]:
    """Parse ``text`` as a single JSON document, else as NDJSON (one object per line)."""
    text = text.strip()
    if not text:
        return []
    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        pass
    objects: list[Any] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip non-JSON log noise interleaved on stdout
    return objects


def _as_message(obj: Any) -> dict[str, Any] | None:
    """Return ``obj`` if it looks like a message (``info`` + ``parts``), unwrapping event envelopes."""
    if not isinstance(obj, dict):
        return None
    if isinstance(obj.get("info"), dict) and isinstance(obj.get("parts"), list):
        return obj
    # ASSUMPTION: `run --format json` wraps message state under a `properties`,
    # `data`, or `message` key (opencode-style event envelope). Undocumented, so
    # we probe the common wrappers rather than pin one.
    for key in ("properties", "data", "message"):
        nested = _as_message(obj.get(key))
        if nested is not None:
            return nested
    return None


def _extract_messages(objects: list[Any]) -> list[dict[str, Any]]:
    """Pull message dicts out of a parsed JSON stream or a full export transcript."""
    messages: list[dict[str, Any]] = []
    for obj in objects:
        if isinstance(obj, dict) and isinstance(obj.get("messages"), list):
            # Full export transcript: {"info": {...}, "messages": [...]}.
            for entry in obj["messages"]:
                if isinstance(entry, dict):
                    messages.append(entry)
            continue
        message = _as_message(obj)
        if message is not None:
            messages.append(message)
    return _dedup_messages(messages)


def _dedup_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated message events by ``info.id``, keeping the latest state.

    A ``--format json`` stream can emit the same message many times as it updates
    (opencode-style cumulative ``message.updated`` events); without this a run's
    tokens/tool calls would be counted once per update. Messages with no id (or a
    full export transcript, where ids are unique) pass through unchanged.
    """
    result: list[dict[str, Any]] = []
    index_by_id: dict[str, int] = {}
    for message in messages:
        info = _as_dict(message.get("info"))
        message_id = info.get("id")
        if isinstance(message_id, str) and message_id:
            if message_id in index_by_id:
                result[index_by_id[message_id]] = message  # latest supersedes
                continue
            index_by_id[message_id] = len(result)
        result.append(message)
    return result


def _normalize(messages: list[dict[str, Any]], exit_code: int) -> AgentRunResult:
    """Fold kilo messages/parts into an ``AgentRunResult`` (best-effort, DEGRADED)."""
    input_tokens = 0
    output_tokens = 0
    cached_tokens = 0
    cost = 0.0
    native_cost_seen = False
    tool_calls: list[ToolCallTrace] = []
    assistant_texts: list[str] = []
    created_ms: list[int] = []
    completed_ms: list[int] = []
    seen_tool_ids: set[str] = set()
    seq = 0

    for message in messages:
        info = _as_dict(message.get("info"))
        role = info.get("role")
        _collect_time(info.get("time"), created_ms, completed_ms)

        if role == "assistant":
            tokens = info.get("tokens")
            if isinstance(tokens, dict):
                input_tokens += _as_int(tokens.get("input"))
                output_tokens += _as_int(tokens.get("output"))
                cache = tokens.get("cache")
                if isinstance(cache, dict):
                    cached_tokens += _as_int(cache.get("read"))
            cost_value = info.get("cost")
            if isinstance(cost_value, (int, float)) and not isinstance(cost_value, bool):
                cost += float(cost_value)
                native_cost_seen = True

        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "tool" and isinstance(part.get("tool"), str):
                call_id = str(part.get("callID") or part.get("id") or "")
                if call_id and call_id in seen_tool_ids:
                    continue  # already recorded (duplicate part event)
                if call_id:
                    seen_tool_ids.add(call_id)
                tool_calls.append(_tool_call(part, seq))
                seq += 1
            elif part_type == "text" and role == "assistant" and isinstance(part.get("text"), str):
                if part["text"]:
                    assistant_texts.append(part["text"])

    usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens, cached_input_tokens=cached_tokens)
    cost_usd, metric_source = SubprocessCLIAdapter.resolve_cost(cost if native_cost_seen else None)
    completeness = _completeness(bool(messages), exit_code)
    metadata = AgentRunMetadata(
        completeness=completeness,
        mcp_coverage="subprocess_with_observer",
        metric_source=metric_source,
    )
    return AgentRunResult(
        response_text="\n".join(assistant_texts),
        tool_calls=tool_calls,
        usage=usage,
        metadata=metadata,
        cost_usd=cost_usd,
        latency_seconds=_latency_seconds(created_ms, completed_ms),
    )


def _tool_call(part: dict[str, Any], sequence_index: int) -> ToolCallTrace:
    """Project one kilo ``type=="tool"`` part into a ``ToolCallTrace``."""
    state = _as_dict(part.get("state"))
    args = _as_dict(state.get("input"))
    output = state.get("output")
    status = state.get("status")
    error = None
    if status == "error":
        error = str(state.get("error") or output or "tool call reported an error")
    return ToolCallTrace(
        name=part["tool"],
        args=args,
        result=output,
        error=error,
        latency_ms=_part_latency_ms(state.get("time")),
        tool_call_id=str(part.get("callID") or part.get("id") or ""),
        sequence_index=sequence_index,
    )


def _collect_time(time_obj: Any, created_ms: list[int], completed_ms: list[int]) -> None:
    if not isinstance(time_obj, dict):
        return
    created = time_obj.get("created")
    completed = time_obj.get("completed")
    if isinstance(created, (int, float)) and not isinstance(created, bool):
        created_ms.append(int(created))
    if isinstance(completed, (int, float)) and not isinstance(completed, bool):
        completed_ms.append(int(completed))


def _part_latency_ms(time_obj: Any) -> float:
    if not isinstance(time_obj, dict):
        return 0.0
    start = time_obj.get("start")
    end = time_obj.get("end")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        delta = float(end) - float(start)
        return delta if delta >= 0 else 0.0
    return 0.0


def _latency_seconds(created_ms: list[int], completed_ms: list[int]) -> float:
    if not created_ms or not completed_ms:
        return 0.0
    delta_ms = max(completed_ms) - min(created_ms)
    return delta_ms / 1000.0 if delta_ms > 0 else 0.0


def _completeness(has_messages: bool, exit_code: int) -> Literal["complete", "truncated", "partial"]:
    if not has_messages:
        return "partial"
    return "complete" if exit_code == 0 else "truncated"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0
