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

"""opencode CLI adapter (fidelity PARTIAL).

Wraps the open-source SST ``opencode`` terminal coding agent, invoked as
``opencode run --format json --dangerously-skip-permissions -- "<prompt>"``.
``--format json`` streams newline-delimited JSON events to stdout, so
``parse_output`` folds ``completed`` stdout into an ``AgentRunResult``; when
stdout is empty it falls back to the newest on-disk session transcript.

Field spellings below are probe-verified against ``opencode 1.15.12`` (the
same schema an earlier archived adapter captured as fixtures). Where a mapping
is a semantic *assumption* rather than a literal field read, it is marked
``# ASSUMPTION`` inline and reflected in ``validation_ceiling``.

Stream schema (per stdout line, one JSON object):

- ``step_start`` - ``type == "step_start"``; step boundary marker.
- ``text`` - ``part.text`` carries assistant text; ``part.time`` has
  ``{start, end}`` (epoch ms).
- ``tool_use`` - ``part.tool`` is the tool name, ``part.callID`` the call id
  (a sibling of ``state`` inside ``part``), ``part.state`` carries
  ``{status, input, output, error, metadata{exit, ...}, time{start, end}}``.
  ``status`` is ``"completed"`` on success, ``"error"`` on failure.
- ``step_finish`` - ``part.reason`` in ``{"tool-calls", "stop"}`` (``"stop"``
  is the terminal step); ``part.tokens`` carries
  ``{total, input, output, reasoning, cache{write, read}}`` PER STEP (not
  cumulative - verified across a 2-step run); ``part.cost`` is per-step native
  cost (``0`` for free-tier models). ``total`` and ``cache.write`` are
  intentionally not folded into ``Usage``.

Cost is native: opencode emits per-step ``cost`` (unlike codex), so the run
cost is the sum of per-step costs and ``metric_source`` is ``"native"``
whenever at least one ``step_finish`` was seen. Token usage is summed across
every ``step_finish`` (each step is a distinct billable LLM call).
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, Literal

from AgentEval._core.cli_adapter import Fidelity, SubprocessCLIAdapter
from AgentEval._core.types import (
    AgentRunMetadata,
    AgentRunResult,
    ToolCallTrace,
    Usage,
)


def _as_dict(value: Any) -> dict[str, Any]:
    """Coerce a possibly-untyped nested JSON value into a dict (empty if not a dict)."""
    return value if isinstance(value, dict) else {}


class OpencodeAdapter(SubprocessCLIAdapter):
    """``opencode`` CLI: ``opencode run --format json``.

    PARTIAL fidelity - tool calls, per-step token usage (with cache-read as
    ``cached_input_tokens``), and native per-step cost are all read from the
    ``--format json`` event stream. Per-tool token/cost attribution is not
    available (opencode reports tokens per *step*, not per tool), so those
    ``ToolCallTrace`` fields stay 0 - see ``validation_ceiling``.
    """

    slug: ClassVar[str] = "opencode"
    binary_name: ClassVar[str] = "opencode"
    fidelity: ClassVar[Fidelity] = "PARTIAL"
    # Probe-verified against opencode 1.15.12. The base drift check is inclusive
    # on both bounds; anything on the 2.x line (parse untested) warns.
    pinned_version_range: ClassVar[tuple[str, str] | None] = ("1.15.0", "1.99.99")
    validation_ceiling: ClassVar[str] = (
        "Tool calls, per-step tokens (cache-read as cached_input_tokens), and "
        "native per-step cost are read from --format json events. Per-tool "
        "token/cost attribution is unavailable (opencode reports tokens per "
        "step, not per tool) and stays 0. latency_seconds is derived from the "
        "event-timestamp span, not a native total-duration field."
    )
    install_hint: ClassVar[str] = (
        "Install per https://opencode.ai (e.g. curl -fsSL https://opencode.ai/install | bash)."
    )

    def build_argv(self, prompt: str) -> list[str]:
        """Return argv for a non-interactive JSON-streaming opencode run.

        - ``--format json`` streams raw JSON events to stdout for parsing.
        - ``--dangerously-skip-permissions`` is required for autonomous
          non-interactive tool use (otherwise tool dispatch blocks on an
          interactive prompt).
        - ``--`` end-of-options sentinel guards a prompt that begins with a
          dash from being parsed as a flag; the prompt is the trailing
          positional ``message`` argument. No secrets are placed on argv.
        """
        return [
            self.binary_name,
            "run",
            "--format",
            "json",
            "--dangerously-skip-permissions",
            "--",
            prompt,
        ]

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        """Normalize opencode's JSON event stream into an ``AgentRunResult``.

        Reads events from ``stdout`` when present; when stdout carries no
        parseable events, falls back to the newest on-disk session transcript
        under ``session_dir`` (same JSON-lines schema).
        """
        events = self._parse_events(stdout)
        if not events and session_dir is not None:
            transcript = self.find_newest_session_file(session_dir, "*.jsonl")
            if transcript is not None:
                events = self._parse_events(transcript.read_text(encoding="utf-8", errors="replace"))

        # Assistant text: concatenate every `text` event in stream order.
        texts = [str(_as_dict(ev.get("part")).get("text") or "") for ev in events if ev.get("type") == "text"]
        texts = [t for t in texts if t]
        response_text = "\n".join(texts)

        # Terminal step: the `step_finish` whose reason == "stop".
        terminal = next(
            (
                ev
                for ev in reversed(events)
                if ev.get("type") == "step_finish" and str(_as_dict(ev.get("part")).get("reason") or "") == "stop"
            ),
            None,
        )

        # Fail-loud diagnostic when the subprocess failed with nothing to show.
        if not response_text and exit_code != 0 and terminal is None:
            response_text = f"[SUBPROCESS_NONZERO_EXIT exit_code={exit_code}]"

        tool_calls = self._tool_calls(events)
        input_tokens, output_tokens, cached_tokens, native_cost, saw_step_finish = self._usage(events)

        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_tokens,
        )

        # Cost precedence: opencode emits native per-step cost, so a summed
        # native value is passed whenever any step_finish was seen (0.0 is a
        # real "free-tier" native report, not a missing value). No step_finish
        # -> no token/cost data at all -> metric_source "none".
        cost_usd, metric_source = self.resolve_cost(native_cost) if saw_step_finish else self.resolve_cost()

        # latency_seconds: opencode has no aggregate-duration field, so derive
        # it from the span of top-level event `timestamp` values (epoch ms).
        # ASSUMPTION: `timestamp` is a per-event epoch-ms wall-clock stamp;
        # its span approximates run latency. Flagged in validation_ceiling.
        latency_seconds = self._latency_seconds(events)

        completeness: Literal["complete", "truncated"] = (
            "complete" if terminal is not None and exit_code == 0 else "truncated"
        )

        return AgentRunResult(
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            metadata=AgentRunMetadata(
                completeness=completeness,
                # opencode's JSON surface carries no MCP-attachment confirmation
                # event; hosted_in_process is the honest default for this seam.
                mcp_coverage="hosted_in_process",
                metric_source=metric_source,
                # agent_version left blank; the base stamps the probed --version.
                agent_version="",
            ),
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
        )

    # ------------------------------------------------------------------ #
    # Parse helpers.                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_events(blob: str) -> list[dict[str, Any]]:
        """Parse newline-delimited JSON into a list of event dicts (skip junk)."""
        events: list[dict[str, Any]] = []
        for line in blob.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue  # non-JSON log chatter multiplexed onto stdout
            if isinstance(parsed, dict) and isinstance(parsed.get("type"), str):
                events.append(parsed)
        return events

    @staticmethod
    def _tool_calls(events: list[dict[str, Any]]) -> list[ToolCallTrace]:
        """Synthesize a ``ToolCallTrace`` per ``tool_use`` event.

        ASSUMPTION: opencode emits exactly one ``tool_use`` event per ``callID``
        already carrying the terminal ``state`` (status in
        {"completed","error"}). A future version streaming an interim dispatch
        event plus a completion event would double-count; that is the documented
        Phase-1 limit.
        """
        tool_calls: list[ToolCallTrace] = []
        seq = 0
        for ev in events:
            if ev.get("type") != "tool_use":
                continue
            part = _as_dict(ev.get("part"))
            state = _as_dict(part.get("state"))
            status = state.get("status")
            metadata = _as_dict(state.get("metadata"))
            cmd_exit = metadata.get("exit")

            error_marker: str | None = None
            if status not in (None, "completed"):
                error_marker = str(state.get("error") or status)
            elif isinstance(cmd_exit, int) and cmd_exit != 0:
                error_marker = f"exit_code={cmd_exit}"

            # Per-tool latency: state.time carries {start, end} in epoch ms.
            time_block = _as_dict(state.get("time"))
            latency_ms = _span_ms(time_block.get("start"), time_block.get("end"))

            tool_calls.append(
                ToolCallTrace(
                    name=str(part.get("tool") or ""),
                    args=_as_dict(state.get("input")),
                    result=state.get("output"),
                    error=error_marker,
                    latency_ms=latency_ms,
                    source="adapter",
                    tool_call_id=str(part.get("callID") or ""),
                    sequence_index=seq,
                )
            )
            seq += 1
        return tool_calls

    @staticmethod
    def _usage(events: list[dict[str, Any]]) -> tuple[int, int, int, float, bool]:
        """Sum per-step tokens + native cost across every ``step_finish``.

        Returns ``(input, output, cached_read, cost, saw_step_finish)``. Tokens
        are per-step (not cumulative), so a plain sum is correct.
        """
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        cost = 0.0
        saw = False
        for ev in events:
            if ev.get("type") != "step_finish":
                continue
            saw = True
            part = _as_dict(ev.get("part"))
            tokens = _as_dict(part.get("tokens"))
            input_tokens += _as_int(tokens.get("input"))
            output_tokens += _as_int(tokens.get("output"))
            # ASSUMPTION: cache.read maps to cached_input_tokens (reused prompt
            # cache); cache.write is a distinct write-cost concept and excluded.
            cache = _as_dict(tokens.get("cache"))
            cached_tokens += _as_int(cache.get("read"))
            cost += _as_float(part.get("cost"))
        return input_tokens, output_tokens, cached_tokens, cost, saw

    @staticmethod
    def _latency_seconds(events: list[dict[str, Any]]) -> float:
        """Span of top-level event ``timestamp`` values (epoch ms) in seconds."""
        stamps = [_as_float(ev.get("timestamp")) for ev in events if ev.get("timestamp") is not None]
        if len(stamps) < 2:
            return 0.0
        return max(0.0, (max(stamps) - min(stamps)) / 1000.0)


def _as_int(value: Any) -> int:
    """Best-effort non-negative int coercion (0 on None/garbage)."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    """Best-effort float coercion (0.0 on None/garbage)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _span_ms(start: Any, end: Any) -> float:
    """Return ``end - start`` in ms as a non-negative float (0.0 if unusable)."""
    s = _as_float(start)
    e = _as_float(end)
    if s <= 0.0 or e <= 0.0:
        return 0.0
    return max(0.0, e - s)
