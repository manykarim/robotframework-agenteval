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

"""`ClaudeCodeCLIAdapter` — `SubprocessAdapter` for the `claude` CLI (Story 4.2 / PRD FR13b).

Wraps the `claude` binary (Claude Code CLI) invoked with
`--output-format=stream-json` + `--verbose` + `--print` to produce a
normalized `AgentRunResult`. Implements the Story 1b.4 ratified 3-hook
`SubprocessAdapter` template-method pattern (`_spawn`, `_parse_event`,
`_finalize`) per ADR-003.

## Phase-1 pinned binary range

Per PRD FR47 + ADR-010 (Copilot CLI version-pinning precedent), Story
4.2 pins the `claude` binary to `>=2.0.0,<3.0.0`. Range chosen at
story-authoring time by inspecting the locally-installed Claude Code
2.x line; out-of-range raises `UnsupportedBinaryVersionError` at
adapter construction.

## Stream-json schema

Captured via behavioral probe at story-authoring time (2026-05-20).
Key events:

- `system` (subtype=`init`): session metadata + tools + model + mcp_servers.
- `rate_limit_event`: rate-limit info (ignored Phase-1).
- `assistant`: nested `message.content[]` with type=`text` or `tool_use`.
- `user`: user messages (typically tool_result echoes).
- `result` (subtype=`success` | error): terminal event with
  `total_cost_usd`, `usage`, `duration_ms`, `result` (final text),
  `terminal_reason`, `is_error`.

Phase-1 mcp_coverage = `external_mixed` per
`docs/contracts/mcp-coverage-detection.md` — the subprocess parses +
executes its OWN MCP via `.mcp.json`; agenteval observes via
stream-json post-hoc (NOT in-process span capture). Epic 5's
hosted-MCP observer changes this when applicable.

References:
    - PRD FR12, FR13b, FR17a, FR47
    - ADR-003 (SubprocessAdapter template-method)
    - ADR-002 (Tier-1 Adapter Ceiling Rule — "≤2 adapters per vendor + 1 generic
      escape hatch"; `claude-code-cli` + future Epic 10 SDK adapter; Story 4.2
      code-review Auditor HIGH-1 fix 2026-05-20: pre-edit cited ADR-005 which
      is conformance-suite fidelity oracles)
    - ADR-010 (Copilot CLI version-pin precedent)
    - Story 1b.4 `coding_agent/base.py:SubprocessAdapter` + `_assert_binary_version`
    - ADR-016 §Detection contract (ratifies `external_mixed` default for Claude
      Code; Story 4.2 code-review Auditor MED-2 fix 2026-05-20: pre-edit cited
      `docs/contracts/mcp-coverage-detection.md` which is currently a Phase-1
      skeleton deferring formal ratification to Epic 5 Story 5.2)
    - `docs/contracts/mcp-coverage-detection.md` — Phase-1 skeleton + Epic 5
      Story 5.2 publishable companion to ADR-016
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from AgentEval.coding_agent.base import SubprocessAdapter
from AgentEval.coding_agent.generic import _hash_prompt, _manifest_entries_from_servers
from AgentEval.mcp.observer import HostedMcpObserver
from AgentEval.types import (
    AgentRunMetadata,
    AgentRunResult,
    ToolCallTrace,
    Usage,
)

__all__ = ["ClaudeCodeCLIAdapter", "ClaudeCodeEvent"]


CLAUDE_BINARY = "claude"
MIN_VERSION = "2.0.0"
MAX_VERSION = "3.0.0"


@dataclass(frozen=True)
class ClaudeCodeEvent:
    """One parsed event from `claude --output-format=stream-json` (Story 4.2).

    Phase-1 captures the union of Claude Code CLI's stream-json event
    types as a single dataclass with a discriminator + raw payload.
    Convenience accessors handle the common nested paths without
    requiring downstream code to do `event.raw["message"]["content"][0]["text"]`
    dictionary descent at every call site.
    """

    event_type: str
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # M_R6 shallow-copy pattern: protect against caller mutating
        # the raw dict after construction.
        object.__setattr__(self, "raw", dict(self.raw))

    @property
    def text_content(self) -> str:
        """Extract the joined text content from an `assistant` event's message.

        Returns the empty string for non-assistant events OR assistant
        events with no text blocks (e.g., pure tool_use events).
        """
        if self.event_type != "assistant":
            return ""
        message = self.raw.get("message") or {}
        content_blocks = message.get("content") or []
        return "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")

    @property
    def tool_use_blocks(self) -> list[dict[str, Any]]:
        """List of tool_use content blocks from an `assistant` event.

        Each block has `id`, `name`, `input` keys per the Claude Code
        stream-json schema. Empty list for non-assistant events or
        assistant events without tool_use.
        """
        if self.event_type != "assistant":
            return []
        message = self.raw.get("message") or {}
        return [
            block
            for block in (message.get("content") or [])
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ]

    @property
    def is_terminal(self) -> bool:
        return self.event_type == "result"

    @property
    def total_cost_usd(self) -> float | None:
        """Total cost reported by terminal `result` event."""
        if self.event_type != "result":
            return None
        cost = self.raw.get("total_cost_usd")
        return float(cost) if cost is not None else None

    @property
    def is_error(self) -> bool:
        """True when the terminal `result` event indicates an error."""
        if self.event_type != "result":
            return False
        return bool(self.raw.get("is_error", False))

    @property
    def terminal_usage(self) -> Usage | None:
        """Extract a `Usage` record from the terminal `result` event's usage field."""
        if self.event_type != "result":
            return None
        usage_raw = self.raw.get("usage") or {}
        return Usage(
            input_tokens=int(usage_raw.get("input_tokens") or 0),
            output_tokens=int(usage_raw.get("output_tokens") or 0),
            cached_input_tokens=int(usage_raw.get("cache_read_input_tokens") or 0),
        )

    @property
    def duration_seconds(self) -> float | None:
        """Wall-clock duration reported by the terminal `result` event (ms → s)."""
        if self.event_type != "result":
            return None
        duration_ms = self.raw.get("duration_ms")
        return float(duration_ms) / 1000.0 if duration_ms is not None else None


class ClaudeCodeCLIAdapter(SubprocessAdapter):
    """`SubprocessAdapter` for the `claude` CLI (PRD FR13b)."""

    def __init__(self, *, discover_external_configs: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Story 1b.4 ratified helper validates the binary version at
        # construction. Raises `UnsupportedBinaryVersionError` on out-
        # of-range per FR47.
        self._assert_binary_version(CLAUDE_BINARY, min=MIN_VERSION, max=MAX_VERSION)
        # Story 5.2 DF-4.2-S1 absorption: per-run observer instance, set by
        # `run()` before delegating to base.run() so `_finalize` can read it.
        self._current_observer: HostedMcpObserver | None = None
        # Story 5.2 code-review 3-angle HIGH-D fix 2026-05-20 (Blind H4 +
        # Edge-cases H3 + H4): pre-edit `_detect_external_configs` read
        # `~/.claude.json` + `./.mcp.json` unconditionally → false-positive
        # external_mixed for any test running where the user happens to
        # have invoked Claude Code OR a CWD that contains `.mcp.json` (the
        # agenteval dogfood targets like rf-mcp + robotframework-agentskills
        # both ship `.mcp.json`). Detection is now OPT-IN via the
        # `discover_external_configs=True` constructor flag. Operators who
        # want the ambient-config scan must explicitly enable it; default
        # is False so in-repo testing isn't poisoned. Caller-provided
        # `mcp_servers=` handles still flow through normally — non-in_memory
        # handles still call `mark_external_mixed(reason)` for the
        # DF-5.2-S3 carry-over honesty.
        self._discover_external_configs = discover_external_configs

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Wraps `SubprocessAdapter.run` with per-call observer + external-config detection.

        Story 5.2 DF-4.2-S1 absorption (per Epic 4 retro Action #5):
        construct a `HostedMcpObserver` per run, detect external Claude
        configs (`~/.claude.json` + caller-provided `mcp_servers` handles),
        call `observer.mark_external_mixed(reason)` for each external
        source, then delegate to `SubprocessAdapter.run` which runs the
        template-method orchestration. `_finalize` reads the observer to
        resolve `metadata.mcp_coverage` honestly (instead of hardcoding
        `"external_mixed"` as pre-Story-5.2).
        """
        self._current_observer = HostedMcpObserver()
        # Story 5.2 code-review 1-way HIGH-C fix 2026-05-20 (Blind H2):
        # register the observer with the active RF Listener so `end_test`
        # calls `observer.clear()` for per-test cleanup per ADR-009.
        from AgentEval.telemetry.listener import (
            record_active_run_metadata,
            register_active_observer,
        )

        register_active_observer(self._current_observer)
        self._detect_external_configs(mcp_servers)
        try:
            result = super().run(prompt, tools=tools, mcp_servers=mcp_servers, **kwargs)
            # Story 5.3: record run metadata for the RunManifest sidecar.
            # `_finalize` already populated the result fields; we record
            # them post-run via the module-level helper.
            record_active_run_metadata(
                adapter_name=self.name,
                adapter_version=self.version,
                model=None,  # Claude Code CLI Phase-1: model is implicit in the binary; no per-call selection
                mcp_servers=_manifest_entries_from_servers(mcp_servers),
                total_cost_usd=result.cost_usd,
                completeness=result.metadata.completeness,
                mcp_coverage=result.metadata.mcp_coverage,
                prompt_hashes=[_hash_prompt(prompt)],
            )
            return result
        finally:
            self._current_observer = None

    def _detect_external_configs(self, mcp_servers: dict[str, Any] | None) -> None:
        """Detect external MCP configs + signal observer per ADR-016 D4.

        Sources scanned:

        - ``~/.claude.json`` — Claude Code CLI's user-level MCP config.
        - ``./.mcp.json`` — project-level MCP config.
        - Caller-provided ``mcp_servers`` handles whose transport is NOT
          ``"in_memory"`` (the only path Story 5.2 wires through). stdio +
          streamable_http transports defer to the subprocess wrapper +
          HTTP observer paths in Story 5.5 (DF-5.2-S3).

        Each detected external source produces one ``mark_external_mixed``
        signal with a human-readable reason. ``compute_coverage()`` will
        then resolve to ``"external_mixed"`` per ADR-016 D1.
        """
        if self._current_observer is None:
            return  # defensive — should never happen in the run() flow
        # Story 5.2 code-review HIGH-D fix 2026-05-20: ambient-config scan
        # is OPT-IN only — operators must pass `discover_external_configs=True`
        # to ClaudeCodeCLIAdapter.__init__ to enable. Avoids false-positive
        # `external_mixed` when the test happens to run in a CWD with
        # `.mcp.json` (agenteval's own dogfood targets ship one) or with
        # an unrelated `~/.claude.json` from a different Claude Code session.
        if self._discover_external_configs:
            # On-disk Claude Code configs — wrap each `expanduser()` call in
            # a try/except per Edge-cases H4 (HOME unset can raise on systems
            # without /etc/passwd entries for the current uid).
            for path_attr in ("~/.claude.json", "./.mcp.json"):
                try:
                    cfg_path = Path(path_attr).expanduser()
                except RuntimeError:
                    # `expanduser()` raises when $HOME is unset and the uid
                    # has no /etc/passwd entry; treat as "no config detected".
                    continue
                if cfg_path.exists():
                    self._current_observer.mark_external_mixed(
                        f"Claude Code CLI detected external MCP config at {cfg_path}"
                    )
        # Caller-provided handles whose transport doesn't get observer
        # attachment in Phase-1 (only in_memory does today via Story 5.5).
        if mcp_servers:
            for name, handle in mcp_servers.items():
                transport = getattr(handle, "transport", None)
                if transport != "in_memory":
                    self._current_observer.mark_external_mixed(
                        f"ClaudeCodeCLIAdapter handle {name!r} (transport="
                        f"{transport!r}) requires the subprocess wrapper "
                        "integration deferred to DF-5.2-S3 (Story 5.5 dogfood "
                        "port lands this); Phase-1 reports external_mixed"
                    )

    @property
    def name(self) -> str:
        return "claude-code-cli"

    def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:
        """Launch `claude` with the prompt as the positional argv argument.

        Story 4.2 code-review 3-way HIGH (Blind H1 + Edge-cases H1 +
        Codex Probe 5 2026-05-20): pre-edit opened `stdin=subprocess.PIPE`
        with the comment "Feed the prompt via stdin per AC-4.2.1" — but
        neither this method nor the base `run()` orchestration ever
        wrote to or closed `proc.stdin`. End-to-end probe with real
        claude 2.1.144: `adapter.run("Say hi")` returned in ~4s with
        `response_text=""`, `usage=zeros`, `cost_usd=0.0`,
        `completeness="truncated"`, exit_code dropped on the floor.
        ON SYSTEMS WITHOUT claude's 3s no-stdin heuristic the
        subprocess would have hung indefinitely (Edge-cases SIGALRM
        reproduction with `cat` stand-in confirmed deadlock).

        Fix: pass `prompt` as the positional CLI argument after `--`
        (Codex option a; avoids stdin buffering + pipe-deadlock
        pitfalls). Per `claude --help`: `claude [prompt]` accepts a
        prompt argument that replaces stdin input.

        Story 4.2 code-review 2-way HIGH (Edge-cases + Codex 2026-05-20):
        stderr pipe deadlock. Pre-edit `stderr=subprocess.PIPE` +
        `--verbose` flag could fill the ~64KB Linux pipe buffer; the
        base `run()` only drains `proc.stdout`, so a stderr-full child
        blocks on its stderr write → never finishes stdout → parent
        wedges in the for-loop or on wait(). Fix: `stderr=subprocess.STDOUT`
        multiplex stderr into stdout. The `_parse_event` already
        returns None on non-JSON lines (test_parse_event_returns_none_on_non_json_line
        verifies), so stderr diagnostics interleaved into stdout get
        skipped cleanly without parsing them as events.

        Required Popen flags per Story 1b.4 base.py L240-244:
        `stdout=PIPE`, `stderr=STDOUT`, `text=True`, `start_new_session=True`
        (process-group hygiene for cleanup-on-exception).

        Phase-1 carve-out: `tools` + `mcp_servers` kwargs are accepted
        per the base `run(prompt, tools, mcp_servers, **kwargs)`
        signature but Phase-1 Claude Code CLI integration relies on
        the operator providing `.mcp.json` discovery via the standard
        Claude Code cwd-search OR the `--mcp-config` flag (Story 4.2
        ships the surface; full `mcp_servers=` integration via temp
        `.mcp.json` generation is Story 4.3 orchestration scope —
        DF-4.2-S1).
        """
        # Phase-1: forward `tools` / `mcp_servers` as kwargs the base
        # passes in but don't act on them at this layer; Story 4.3
        # adds the temp `.mcp.json` generation step before `_spawn`.
        _ = kwargs

        cmd = [
            CLAUDE_BINARY,
            "--output-format=stream-json",
            "--verbose",
            "--print",
            "--",  # end-of-options sentinel so prompts starting with `-` aren't parsed as flags
            prompt,
        ]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            # Multiplex stderr into stdout per the 2-way HIGH fix;
            # `_parse_event` returns None on non-JSON lines so verbose
            # stderr chatter is silently skipped without deadlock risk.
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

    def _parse_event(self, line: str) -> ClaudeCodeEvent | None:
        """Parse one stdout JSONL line into a `ClaudeCodeEvent`, or None to skip."""
        stripped = line.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            # Non-JSON line (progress chatter, debug output). Skip per
            # Story 1b.4 `_parse_event` contract — returning None skips.
            return None
        if not isinstance(parsed, dict):
            return None
        event_type = str(parsed.get("type") or "unknown")
        return ClaudeCodeEvent(event_type=event_type, raw=parsed)

    def _finalize(self, events: list[ClaudeCodeEvent], exit_code: int) -> AgentRunResult:
        """Fold the event stream into an `AgentRunResult`."""
        terminal = next((e for e in reversed(events) if e.is_terminal), None)

        # Response text: prefer the terminal `result.result` field if
        # present (canonical final output); else fall back to the last
        # assistant event's joined text content; else surface a
        # diagnostic stub when the subprocess exited non-zero with no
        # terminal event (Story 4.2 code-review Codex MED-3 fix
        # 2026-05-20 — pre-edit silently returned `response_text=""`
        # which collided with "agent declined to respond" semantics).
        response_text = ""
        if terminal is not None:
            result_field = terminal.raw.get("result")
            if isinstance(result_field, str):
                response_text = result_field
        if not response_text:
            last_assistant = next(
                (e for e in reversed(events) if e.event_type == "assistant"),
                None,
            )
            if last_assistant is not None:
                response_text = last_assistant.text_content
        if not response_text and exit_code != 0 and terminal is None:
            # Phase-1 fail-loud diagnostic per Codex MED-3 + M_R11:
            # exit_code != 0 + no terminal event means the subprocess
            # exited abnormally (binary refused to run, OOM, signal,
            # etc.). Surface a structured marker so consumers can
            # distinguish "claude declined to respond" from "claude
            # never produced output". Full stderr-tail capture is
            # DF-4.2-S5 Phase-1.5 (requires base `run()` to expose
            # stderr; currently multiplexed into stdout).
            response_text = f"[SUBPROCESS_NONZERO_EXIT exit_code={exit_code}]"

        # Tool calls: synthesize ToolCallTrace records from every
        # `tool_use` content block across all assistant events. Phase-1
        # carve-out (DF-4.2-S1): full OTel-span correlation + latency
        # extraction lands in Epic 5 hosted-MCP observer; Story 4.2
        # ships the stream-json mapping only.
        tool_calls: list[ToolCallTrace] = []
        seq = 0
        for ev in events:
            for block in ev.tool_use_blocks:
                tool_calls.append(
                    ToolCallTrace(
                        name=str(block.get("name") or ""),
                        args=dict(block.get("input") or {}),
                        result=None,  # Phase-1: not yet correlated; Story 4.3 + Epic 5.
                        error=None,
                        latency_ms=0.0,  # Phase-1 placeholder; Epic 5 correlates per-call latency.
                        source="adapter",
                        gen_ai_tool_call_id=str(block.get("id") or ""),
                        sequence_index=seq,
                    )
                )
                seq += 1

        # Usage: from terminal `result` event's usage; fallback to zeros
        # if the run didn't reach a terminal event (truncated path).
        usage = (
            terminal.terminal_usage
            if terminal is not None and terminal.terminal_usage is not None
            else Usage(input_tokens=0, output_tokens=0)
        )

        # Cost: from terminal event's total_cost_usd; 0.0 fallback.
        cost_usd = 0.0
        if terminal is not None and terminal.total_cost_usd is not None:
            cost_usd = terminal.total_cost_usd

        # Latency: prefer the terminal duration_ms; fallback to a 0.0
        # placeholder when the run was truncated.
        latency_seconds = 0.0
        if terminal is not None and terminal.duration_seconds is not None:
            latency_seconds = terminal.duration_seconds

        # Completeness: "complete" when terminal event present AND
        # `is_error` is False AND `exit_code == 0`; else "truncated".
        completeness: str = (
            "complete" if terminal is not None and not terminal.is_error and exit_code == 0 else "truncated"
        )

        # Story 5.2 DF-4.2-S1 absorption: mcp_coverage now resolved from the
        # per-run observer (set by `run()` before delegating to base.run()).
        # When ANY external config was detected (`.mcp.json`, `~/.claude.json`,
        # or non-in_memory handles), observer.compute_coverage() → "external_mixed"
        # per ADR-016 D1. Phase-1 fallback when observer is None (direct
        # `_finalize` invocation outside `run()`): "external_mixed" — safer
        # default per ADR-016 detection-failure semantics.
        mcp_coverage = (
            self._current_observer.compute_coverage() if self._current_observer is not None else "external_mixed"
        )
        return AgentRunResult(
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            metadata=AgentRunMetadata(
                completeness=completeness,  # type: ignore[arg-type]
                mcp_coverage=mcp_coverage,
            ),
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
            trace_id=uuid.uuid4().hex,
        )
