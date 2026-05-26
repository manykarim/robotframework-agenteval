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

"""`CopilotCLIAdapter` — `SubprocessAdapter` for the `copilot` CLI (Story 11.2 / PRD FR12 + FR13d).

Wraps the GitHub Copilot CLI binary (`copilot` v1.0.9+) invoked with
`copilot --allow-all-tools -p "<prompt>"` to produce a normalized
`AgentRunResult`. Implements the Story 1b.4 ratified 3-hook
`SubprocessAdapter` template-method pattern per ADR-003 **with one
override**: `run()` is overridden to do post-hoc events.jsonl parsing
because copilot does NOT stream events to stdout — events are written
to `~/.copilot/session-state/{uuid}/events.jsonl` during the run.

## Phase-1 pinned binary range

Per PRD FR47 + ADR-010 (Copilot CLI version-pinning original source +
precedent), this adapter pins the `copilot` binary to `>=1.0.9,<2.0`.
Below `1.0.9` predates the documented `--allow-all-tools` autopilot
mode + the events.jsonl trace format this adapter parses. Local probe
at story-authoring: `GitHub Copilot CLI 1.0.54.` — in range.

## Events.jsonl schema (empirical probe 2026-05-26)

Captured via probe BEFORE writing this adapter per
`feedback_listener_hook_api_surface_empirical_check` (Epic 8 retro NEW
norm). 10 event types:

- ``session.start`` — sessionId + copilotVersion + context (cwd, gitRoot, etc.)
- ``session.model_change`` — newModel
- ``session.shutdown`` — terminal event
- ``user.message`` — content
- ``assistant.turn_start`` / ``assistant.turn_end`` — turn boundaries
- ``assistant.message`` — content + toolRequests[] + outputTokens
- ``tool.execution_start`` / ``tool.execution_complete`` — tool dispatch

## Phase-1 mcp_coverage

Per ADR-016 §Decision L33 safer-default rule: empty `mcp_servers` →
`hosted_in_process`; non-empty → `external_mixed` until observer wiring
lands (DF-11.2-S1 / C75). Copilot's events.jsonl exposes
`mcpServerName`/`mcpToolName` per `tool.execution_start` event — a
future observer could verify hosted MCP attachment by checking these
fields match the requested `mcp_servers`. Phase-2 carry-over.

## Cross-story UPSTREAM lessons applied (2nd use of `feedback_cross_story_upstream_lesson_propagation`)

This adapter ships with **12 cross-story lessons from Stories 4.2 +
10.1 + 10.2 + 11.1 applied UPSTREAM** — see Story 11.2 spec drift-check
D-1 through D-12. Most load-bearing:

- D-1 (Story 11.1 D-1 / Story 4.2 HIGH-A): prompt via `-p` flag
- D-2 (Story 11.1 D-2 / Story 4.2 HIGH-B): stderr multiplex
- D-3 (Story 11.1 D-3 / Story 4.2 MED-3): nonzero-exit diagnostic
- D-7 (Story 11.1 D-7 / Stories 10.1+10.2 HIGH-2): external_mixed default
- D-8 (Story 11.1 kilo HIGH-1): `Usage.reasoning_output_tokens` populated if present
- D-9 (Copilot-specific): override `run()` for post-hoc events.jsonl parse
- D-11 (Story 11.1 MED-1): NO module-level `_VERSION_RE` dead-code constant
- D-12 (Story 11.1 MED-3): class-docstring thread-safety from start

References:
    - PRD FR12, FR13d (Copilot CLI scope), FR17a, FR47.
    - ADR-003 (SubprocessAdapter template-method).
    - ADR-002 (Tier-1 Adapter Ceiling Rule).
    - ADR-010 (Copilot CLI version-pin precedent — original source).
    - ADR-016 §Decision L33 (external_mixed safer default).
    - Story 1b.4 `coding_agent/base.py:SubprocessAdapter` + `_assert_binary_version`.
    - Story 4.2 ClaudeCodeCLIAdapter + Story 11.1 CodexCLIAdapter precedents.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from AgentEval.coding_agent.base import SubprocessAdapter
from AgentEval.coding_agent.generic import _hash_prompt, _manifest_entries_from_servers
from AgentEval.types import (
    AgentRunMetadata,
    AgentRunResult,
    ToolCallTrace,
    Usage,
)

__all__ = ["CopilotCLIAdapter", "CopilotEvent"]


COPILOT_BINARY = "copilot"
MIN_VERSION = "1.0.9"
MAX_VERSION = "2.0.0"
# Story 11.3 (Epic 11) — adapter's "tested-up-to" version for the FR60
# `AdapterVersionDriftWarning` surface. Bump in lockstep with future
# "tested against" updates. DF-11.3-S1 tracks automated upstream-probe.
_TESTED_UP_TO = "1.0.54"

# `copilot --version` prints e.g. ``GitHub Copilot CLI 1.0.54.`` (trailing
# period). The base `_assert_binary_version`'s default `_SEMVER_RE.search()`
# extracts `1.0.54` via substring search — no module-level constant needed
# (Story 11.2 D-11; Story 11.1 MED-1 lesson UPSTREAM).

# Default location where copilot writes session-state directories. Each
# session creates a UUID-named subdirectory containing `events.jsonl`.
DEFAULT_COPILOT_SESSION_STATE_DIR = Path.home() / ".copilot" / "session-state"


@dataclass(frozen=True)
class CopilotEvent:
    """One parsed event from `copilot` CLI's events.jsonl trace (Story 11.2).

    Phase-1 captures the union of Copilot CLI's 10 event types as a
    single dataclass with a discriminator + raw payload. Convenience
    accessors handle common nested paths.
    """

    event_type: str
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # M_R6 shallow-copy pattern.
        object.__setattr__(self, "raw", dict(self.raw))

    @property
    def is_terminal(self) -> bool:
        """``session.shutdown`` is the terminal event."""
        return self.event_type == "session.shutdown"

    @property
    def assistant_text(self) -> str:
        """Extract text from an `assistant.message` event (excluding tool_requests)."""
        if self.event_type != "assistant.message":
            return ""
        data = self.raw.get("data") or {}
        return str(data.get("content") or "")

    @property
    def assistant_output_tokens(self) -> int:
        """Output-tokens count carried on `assistant.message` events."""
        if self.event_type != "assistant.message":
            return 0
        data = self.raw.get("data") or {}
        return int(data.get("outputTokens") or 0)

    @property
    def tool_requests(self) -> list[dict[str, Any]]:
        """Tool requests embedded in an `assistant.message` event.

        Each entry has: `toolCallId`, `name`, `arguments`, optional
        `mcpServerName` + `mcpToolName` + `toolTitle`.
        """
        if self.event_type != "assistant.message":
            return []
        data = self.raw.get("data") or {}
        requests = data.get("toolRequests") or []
        return [dict(r) for r in requests if isinstance(r, dict)]

    @property
    def tool_execution_complete_payload(self) -> dict[str, Any] | None:
        """Return the data dict for `tool.execution_complete`, else None."""
        if self.event_type != "tool.execution_complete":
            return None
        data = self.raw.get("data") or {}
        return dict(data)


class CopilotCLIAdapter(SubprocessAdapter):
    """`SubprocessAdapter` for the `copilot` CLI (Story 11.2 / PRD FR13d).

    Implements the 3-hook template-method pattern per ADR-003 WITH a
    `run()` override (D-9) because copilot writes events to disk
    (`~/.copilot/session-state/{uuid}/events.jsonl`) rather than to
    stdout. The override does `spawn → wait → glob newest session-state
    directory → read events.jsonl → call _finalize`.

    **Thread safety: NOT concurrent-safe.** ``run()`` uses
    ``self._last_mcp_servers`` instance state to thread ``mcp_servers``
    through to ``_finalize`` (Phase-1 single-threaded-per-instance
    design; mirrors Story 11.1 / DF-11.2-S1 / C75). **Do not call
    ``run()`` concurrently on the same ``CopilotCLIAdapter`` instance**
    — the second thread's ``mcp_servers`` overwrites the first's before
    ``_finalize`` reads it. Construct one adapter per concurrent run.
    Inline from the start per Story 11.1 MED-3 UPSTREAM lesson.

    Additionally: the post-hoc events.jsonl read pattern means the
    `~/.copilot/session-state/` directory is scanned during `run()`. The
    adapter records the directory's mtime snapshot before `_spawn` so
    it can identify the run's session UUID by selecting the newest
    directory created within the run window — concurrent runs against
    the same `~/.copilot/session-state/` parent would race for the
    "newest directory" pick. Documented; tracked DF-11.2-S3 carry-over
    if a real consumer hits this.
    """

    def __init__(self, *, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Story 1b.4 ratified helper validates binary version at construction.
        # The default `_SEMVER_RE.search()` extracts `1.0.54` from
        # `GitHub Copilot CLI 1.0.54.` (trailing period included; substring
        # search is tolerant). No `_VERSION_RE` override needed (D-11
        # UPSTREAM from Story 11.1 MED-1).
        self._assert_binary_version(COPILOT_BINARY, min=MIN_VERSION, max=MAX_VERSION)
        # Story 11.3 (Epic 11): emit `AdapterVersionDriftWarning` if drift exceeds threshold.
        from AgentEval._kernel.version_drift import (
            emit_adapter_version_drift_warning_if_applicable,
            parse_binary_version,
        )

        emit_adapter_version_drift_warning_if_applicable(
            adapter_name="copilot-cli",
            detected_version=parse_binary_version(COPILOT_BINARY),
            tested_up_to=_TESTED_UP_TO,
            compat_min=MIN_VERSION,
            compat_max=MAX_VERSION,
        )
        self._model = model
        # See class docstring for thread-safety invariant.
        self._last_mcp_servers: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return "copilot-cli"

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Override base `run()` for post-hoc events.jsonl parsing (Story 11.2 D-9).

        Copilot writes events to ``~/.copilot/session-state/{uuid}/events.jsonl``
        during the run — NOT to stdout. The base ``SubprocessAdapter.run()``
        assumes events arrive on ``proc.stdout``; we bypass that
        iteration pattern and do:

        1. Snapshot existing session-state directory contents.
        2. Spawn subprocess + wait for exit.
        3. Identify the new session-state directory created during the run.
        4. Read events.jsonl line-by-line through ``_parse_event``.
        5. Call ``_finalize(events, exit_code)``.

        Per Story 10.1 HIGH-4 + Story 11.1 D-6 UPSTREAM: wires
        ``_record_run_metadata`` to capture per-run identity in the
        Story 5.3 RunManifest sidecar.
        """
        from AgentEval.telemetry.listener import record_active_run_metadata

        self._last_mcp_servers = mcp_servers
        # Snapshot existing session-state directories BEFORE spawn so
        # we can identify the new one created during the run.
        session_root = DEFAULT_COPILOT_SESSION_STATE_DIR
        pre_existing = self._snapshot_session_dirs(session_root)
        events: list[CopilotEvent] = []
        try:
            proc = self._spawn(prompt, tools=tools, mcp_servers=mcp_servers, **kwargs)
            # Drain stdout to avoid pipe-buffer deadlock under verbose
            # output (per D-2 stderr=STDOUT multiplex + base ABC pattern).
            if proc.stdout is not None:
                # Discard stdout content; events come from events.jsonl on
                # disk. We still iterate to drain the pipe.
                for _line in proc.stdout:
                    pass
            exit_code = proc.wait()
            # Identify newest session-state dir that did NOT exist before spawn.
            events_jsonl = self._find_new_events_jsonl(session_root, pre_existing)
            if events_jsonl is not None:
                with events_jsonl.open() as fh:
                    for line in fh:
                        parsed = self._parse_event(line)
                        if parsed is not None:
                            events.append(parsed)
            result = self._finalize(events, exit_code)
        finally:
            self._last_mcp_servers = None

        record_active_run_metadata(
            adapter_name=self.name,
            adapter_version=self.version,
            model=self._model,
            mcp_servers=_manifest_entries_from_servers(mcp_servers),
            total_cost_usd=result.cost_usd,
            completeness=result.metadata.completeness,
            mcp_coverage=result.metadata.mcp_coverage,
            prompt_hashes=[_hash_prompt(prompt)],
        )
        return result

    @staticmethod
    def _snapshot_session_dirs(session_root: Path) -> set[str]:
        """Return the set of session UUID directory names that exist now."""
        if not session_root.exists():
            return set()
        try:
            return {p.name for p in session_root.iterdir() if p.is_dir()}
        except OSError:
            # Permission / IO error — treat as empty snapshot.
            return set()

    def _find_new_events_jsonl(self, session_root: Path, pre_existing: set[str]) -> Path | None:
        """Locate the events.jsonl for the session created during this run.

        Strategy: list session-state directories, filter to ones not in
        the pre-spawn snapshot, pick the one with the most recent mtime,
        return its `events.jsonl` if present.
        """
        if not session_root.exists():
            return None
        try:
            candidates = [
                p for p in session_root.iterdir() if p.is_dir() and p.name not in pre_existing
            ]
        except OSError:
            return None
        if not candidates:
            return None
        # Pick the newest by mtime — defensive against concurrent
        # sessions with overlapping timestamps (we documented the
        # thread-safety + dir-race invariant in the class docstring).
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        events_path = candidates[0] / "events.jsonl"
        return events_path if events_path.exists() else None

    def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:
        """Launch `copilot --allow-all-tools -p "<prompt>"` (Story 11.2 D-1 + D-2).

        D-1 (Story 11.1 D-1 / Story 4.2 HIGH-A UPSTREAM): prompt is
        passed via the ``-p``/``--prompt`` flag for non-interactive mode
        (per `copilot --help`: "Execute a prompt in non-interactive mode").

        D-2 (Story 11.1 D-2 / Story 4.2 HIGH-B UPSTREAM):
        ``stderr=subprocess.STDOUT`` multiplex to avoid pipe-buffer
        deadlock under verbose output.

        ``--allow-all-tools`` is required for non-interactive mode (per
        `copilot --help`: "required for non-interactive mode"). Without
        it, copilot would prompt for permission on each tool dispatch.
        """
        # Phase-1: tools / mcp_servers forwarded but not acted upon at
        # this layer (DF-11.2-S1 observer wiring carry-over).
        _ = kwargs

        cmd = [COPILOT_BINARY, "--allow-all-tools"]
        if self._model is not None:
            cmd.extend(["--model", self._model])
        cmd.extend(["-p", prompt])
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

    def _parse_event(self, line: str) -> CopilotEvent | None:
        """Parse one events.jsonl line into a `CopilotEvent`, or None to skip."""
        stripped = line.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        event_type = parsed.get("type")
        if not isinstance(event_type, str):
            return None
        return CopilotEvent(event_type=event_type, raw=parsed)

    def _finalize(self, events: list[CopilotEvent], exit_code: int) -> AgentRunResult:
        """Fold the event stream into an `AgentRunResult`.

        Story 11.2 D-3 (cross-story UPSTREAM from Story 11.1 D-3 +
        Story 4.2 MED-3): when exit_code != 0 AND no terminal event AND
        no assistant text, surface a ``[SUBPROCESS_NONZERO_EXIT
        exit_code=<N>]`` diagnostic marker. M_R11 fail-loud.
        """
        terminal = next((e for e in reversed(events) if e.is_terminal), None)

        # Response text: concatenate every `assistant.message` content
        # (intermediate narration + final response).
        assistant_texts = [e.assistant_text for e in events if e.assistant_text]
        response_text = "\n".join(assistant_texts) if assistant_texts else ""

        # D-3 diagnostic when subprocess failed silently.
        if not response_text and exit_code != 0 and terminal is None:
            response_text = f"[SUBPROCESS_NONZERO_EXIT exit_code={exit_code}]"

        # Tool calls: project from `assistant.message.toolRequests[]` +
        # matching `tool.execution_complete` payloads. Iterate
        # chronologically; build a tool_call_id → completion map for O(N).
        completion_by_id: dict[str, dict[str, Any]] = {}
        for ev in events:
            payload = ev.tool_execution_complete_payload
            if payload is None:
                continue
            tcid = payload.get("toolCallId")
            if isinstance(tcid, str):
                completion_by_id[tcid] = payload

        tool_calls: list[ToolCallTrace] = []
        seq = 0
        for ev in events:
            for req in ev.tool_requests:
                tc_id = str(req.get("toolCallId") or "")
                completion = completion_by_id.get(tc_id, {})
                success = completion.get("success", True)
                error_marker: str | None = None
                if completion and success is False:
                    # Tool failed — surface as ToolCallTrace.error.
                    error_marker = str(completion.get("result", {}).get("error") or "tool_failed")
                tool_calls.append(
                    ToolCallTrace(
                        name=str(req.get("name") or ""),
                        args=dict(req.get("arguments") or {}),
                        result=completion.get("result") if completion else None,
                        error=error_marker,
                        latency_ms=0.0,  # Phase-1 placeholder; DF-11.2-S1 observer would correlate.
                        source="adapter",
                        gen_ai_tool_call_id=tc_id,
                        sequence_index=seq,
                    )
                )
                seq += 1

        # Usage: sum `outputTokens` from `assistant.message` events.
        # Copilot doesn't surface `inputTokens` directly in our probe — Phase-1
        # placeholder 0. D-8 + Story 11.1 kilo HIGH-1 lesson UPSTREAM: if any
        # event carries `reasoningTokens`, populate `reasoning_output_tokens`.
        output_tokens = sum(e.assistant_output_tokens for e in events)
        reasoning_tokens = 0
        for ev in events:
            if ev.event_type == "assistant.message":
                data = ev.raw.get("data") or {}
                rt = data.get("reasoningTokens")
                if isinstance(rt, int):
                    reasoning_tokens += rt
        usage = Usage(
            input_tokens=0,  # Copilot events.jsonl doesn't expose input tokens — DF-11.2-S2.
            output_tokens=output_tokens,
            cached_input_tokens=0,
            reasoning_output_tokens=reasoning_tokens,
        )

        # Cost: Copilot events.jsonl doesn't surface cost_usd — DF-11.2-S2.
        cost_usd = 0.0

        # Latency: copilot events have per-event timestamps but no aggregate
        # duration — Phase-1 placeholder.
        latency_seconds = 0.0

        completeness: str = "complete" if terminal is not None and exit_code == 0 else "truncated"

        mcp_coverage = self._detect_mcp_coverage(self._last_mcp_servers)

        return AgentRunResult(
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            metadata=AgentRunMetadata(
                completeness=completeness,  # type: ignore[arg-type]
                mcp_coverage=mcp_coverage,  # type: ignore[arg-type]
            ),
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
            # Phase-1 placeholder; Story 5.3 / Epic 5 wires real trace-id
            # (mirrors `codex_cli.py:472` documented-placeholder pattern).
            # Story 11.2 kilo H-1 + copilot H-1 cross-LLM review 2026-05-26.
            trace_id="",
        )

    def _detect_mcp_coverage(self, mcp_servers: dict[str, Any] | None) -> str:
        """Detection-contract per ADR-016 §Decision L33 (Story 11.2 D-7).

        - Empty / None ``mcp_servers``: ``"hosted_in_process"`` (trivially honest).
        - Non-empty without verified hosted-attachment: ``"external_mixed"``
          per ADR-016 §Decision L33 safer-default rule.
        - DF-11.2-S1 / C75 tracks the `HostedMcpObserver` wiring upgrade path.
        """
        if not mcp_servers:
            return "hosted_in_process"
        return "external_mixed"
