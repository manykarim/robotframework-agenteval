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

"""`OpenCodeCLIAdapter` — `SubprocessAdapter` for the `opencode` CLI (PRD FR12 + FR47 + FR60).

Wraps the open-source SST `opencode` terminal coding agent invoked with
``opencode run --format json --dangerously-skip-permissions [--model
<provider/model>] "<prompt>"`` to produce a normalized `AgentRunResult`.
Implements the Story 1b.4 ratified 3-hook `SubprocessAdapter`
template-method pattern per ADR-003 — `opencode --format json` streams
JSONL events to **stdout** (Case A), so the base
`SubprocessAdapter.run()` orchestration is reused verbatim; only a thin
`run()` wrapper is added to record the Story 5.3 RunManifest sidecar
metadata (mirrors `codex_cli.py`, NOT the `copilot_cli.py` post-hoc
file-read override).

## Phase-1 pinned binary range

Per PRD FR47 + ADR-010 (Copilot CLI version-pinning precedent), this
adapter pins the `opencode` binary to ``>=1.15.0,<2.0``. Below `1.15.0`
predates the locally-probed ``--format json`` event schema this adapter
parses. Local probe at story-authoring: ``opencode 1.15.12`` — in range.
``opencode --version`` prints a bare ``1.15.12`` (no prefix); the base
`_assert_binary_version`'s default `_SEMVER_RE.search()` extracts it
without an override.

## Stream-json schema (empirical probe 2026-06-25)

Captured via behavioral probe BEFORE writing this adapter, per
`feedback_listener_hook_api_surface_empirical_check` (Epic 8 retro
norm — never assume the CLI shape). Each stdout line is a JSON object
with a top-level ``type`` discriminator + ``timestamp`` + ``sessionID``
+ a nested ``part`` payload. The 4 observed event types:

The top-level ``type`` field is the event discriminator (``_parse_event``
keys on it). The nested ``part.type`` is a sub-field, NOT the discriminator.

- ``step_start`` — discriminator ``type == "step_start"``; inner
  ``part.type == "step-start"`` (step boundary marker).
- ``text`` — ``part.text`` carries assistant text; ``part.time``
  has ``{start, end}``.
- ``tool_use`` — inner ``part.type == "tool"``; ``part.tool`` is the
  tool name, ``part.callID`` the call id (a top-level sibling of
  ``state`` inside ``part``), ``part.state`` carries
  ``{status, input, output, metadata{exit, ...}, title, time}``.
  ``status`` is ``"completed"`` on success, ``"error"`` on failure.
- ``step_finish`` — inner ``part.type == "step-finish"``; ``part.reason``
  ∈ ``{"tool-calls", "stop"}`` (``"stop"`` marks the terminal step);
  ``part.tokens`` carries ``{total, input, output, reasoning,
  cache{write, read}}`` PER STEP (NOT cumulative — verified across a
  2-step tool-use run); ``part.cost`` carries per-step ``cost_usd``
  (``0`` / absent for free-tier models). ``_finalize`` extracts the
  subset it needs (``input``/``output``/``reasoning``/``cache.read`` +
  ``cost``); ``total`` + ``cache.write`` are intentionally NOT folded
  into `Usage` (``total`` is derivable; ``cache.write`` isn't part of
  the `cached_input_tokens` semantics).

Unlike Codex, opencode **does** surface ``cost`` per ``step_finish`` —
``cost_usd`` is the sum of per-step costs (``0`` for free models). Token
usage is summed across every ``step_finish`` (each step is a distinct
billable LLM call). See DF-OPENCODE-S2 / C100 for the cost-catalog
cross-check carry-over.

## Phase-1 mcp_coverage

Per ADR-016 §Decision L33 safer-default rule: empty ``mcp_servers`` →
``hosted_in_process``; non-empty → ``external_mixed`` until observer
wiring lands (DF-OPENCODE-S1 / C99). opencode's ``--format json`` event
surface carries no MCP-attachment confirmation event, so
``external_mixed`` is the only honest default for requested servers.

References:
    - PRD FR12 (single `run()` Protocol method), FR47 (binary version gate), FR60 (drift warning).
    - ADR-003 (SubprocessAdapter template-method, 3 abstract hooks).
    - ADR-010 (per-CLI version-pin precedent).
    - ADR-016 §Decision L33 (`external_mixed` safer default).
    - Story 1b.4 `coding_agent/base.py:SubprocessAdapter` + `_assert_binary_version`.
    - Story 11.1 `codex_cli.py` precedent (streamed-JSONL Case A; closest analog).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any

from AgentEval.coding_agent.base import SubprocessAdapter
from AgentEval.coding_agent.generic import _hash_prompt, _manifest_entries_from_servers
from AgentEval.types import (
    AgentRunMetadata,
    AgentRunResult,
    ToolCallTrace,
    Usage,
)

__all__ = ["OpenCodeCLIAdapter", "OpenCodeEvent"]


def _as_dict(value: Any) -> dict[str, Any]:
    """Coerce a possibly-untyped nested JSON value into a dict (empty if not a dict).

    Keeps `_finalize`'s nested ``part.state.metadata`` descent both
    null-safe and mypy-clean (no `Any | None`-union `.get` calls).
    """
    return value if isinstance(value, dict) else {}


OPENCODE_BINARY = "opencode"
MIN_VERSION = "1.15.0"
MAX_VERSION = "2.0.0"
# Adapter's "tested-up-to" version for the FR60 `AdapterVersionDriftWarning`
# surface (Story 11.3 pattern). Bump in lockstep with future "tested
# against" updates. DF-OPENCODE-S3 tracks the automated upstream-probe.
_TESTED_UP_TO = "1.15.12"


@dataclass(frozen=True)
class OpenCodeEvent:
    """One parsed event from `opencode run --format json`.

    Phase-1 captures the union of opencode's JSONL event types as a
    single dataclass with a discriminator (``event_type``) + raw
    payload. Convenience accessors handle the common nested ``part.*``
    paths so downstream code doesn't dictionary-descend at every call
    site (mirrors `CodexEvent` / `CopilotEvent`).
    """

    event_type: str
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # M_R6 shallow-copy pattern: protect against caller mutation
        # after construction (mirrors Story 11.1's CodexEvent).
        object.__setattr__(self, "raw", dict(self.raw))

    @property
    def _part(self) -> dict[str, Any]:
        part = self.raw.get("part")
        return part if isinstance(part, dict) else {}

    @property
    def is_step_finish(self) -> bool:
        """True for ``step_finish`` step-boundary events."""
        return self.event_type == "step_finish"

    @property
    def finish_reason(self) -> str:
        """``part.reason`` for ``step_finish`` events (e.g. ``"stop"``, ``"tool-calls"``); empty otherwise."""
        if not self.is_step_finish:
            return ""
        return str(self._part.get("reason") or "")

    @property
    def is_terminal(self) -> bool:
        """True for the terminal ``step_finish`` whose ``reason == "stop"``."""
        return self.is_step_finish and self.finish_reason == "stop"

    @property
    def text_content(self) -> str:
        """Assistant text carried on a ``text`` event; empty otherwise."""
        if self.event_type != "text":
            return ""
        return str(self._part.get("text") or "")

    @property
    def tool_payload(self) -> dict[str, Any] | None:
        """Return the ``part`` dict for a ``tool_use`` event, else None.

        The returned dict's top-level keys are ``tool`` (name), ``callID``
        (the call id — a sibling of ``state``, NOT nested inside it), and
        ``state`` (``{status, input, output, metadata{exit}, ...}``).
        """
        if self.event_type != "tool_use":
            return None
        return dict(self._part)

    @property
    def step_tokens(self) -> dict[str, Any]:
        """Per-step ``part.tokens`` dict for ``step_finish`` events; empty otherwise."""
        if not self.is_step_finish:
            return {}
        tokens = self._part.get("tokens")
        return tokens if isinstance(tokens, dict) else {}

    @property
    def step_cost(self) -> float:
        """Per-step ``part.cost`` for ``step_finish`` events; 0.0 otherwise."""
        if not self.is_step_finish:
            return 0.0
        try:
            return float(self._part.get("cost") or 0.0)
        except (TypeError, ValueError):
            return 0.0


class OpenCodeCLIAdapter(SubprocessAdapter):
    """`SubprocessAdapter` for the `opencode` CLI (streamed-JSONL Case A).

    Implements the 3-hook template-method pattern per ADR-003. Calls
    ``_assert_binary_version(OPENCODE_BINARY, ">=1.15.0,<2.0")`` at
    construction; raises ``UnsupportedBinaryVersionError`` on
    out-of-range (FR47). Reuses the base ``run()`` orchestration because
    ``opencode --format json`` streams events to stdout.

    **Thread safety: NOT concurrent-safe.** ``run()`` uses
    ``self._last_mcp_servers`` instance state to thread ``mcp_servers``
    through to ``_finalize`` (the base ABC's
    ``_finalize(events, exit_code)`` signature doesn't receive
    ``mcp_servers``). **Do not call ``run()`` concurrently on the same
    ``OpenCodeCLIAdapter`` instance** — the second thread's
    ``mcp_servers`` overwrites the first's before ``_finalize`` reads it,
    silently corrupting ``mcp_coverage``. Construct one adapter per
    concurrent run. (Documented inline from the start per Story 11.1
    MED-3 UPSTREAM lesson.)
    """

    def __init__(self, *, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Story 1b.4 ratified helper validates the binary version at
        # construction. The default `_SEMVER_RE.search()` extracts
        # `1.15.12` from the bare `opencode --version` output — no
        # override needed.
        self._assert_binary_version(OPENCODE_BINARY, min=MIN_VERSION, max=MAX_VERSION)
        # Story 11.3 pattern (FR60): emit `AdapterVersionDriftWarning` if
        # the detected binary is >=2 minor versions behind `_TESTED_UP_TO`.
        # Helper is a no-op outside the drift window + dedupes per-session.
        from AgentEval._kernel.version_drift import (
            emit_adapter_version_drift_warning_if_applicable,
            parse_binary_version,
        )

        emit_adapter_version_drift_warning_if_applicable(
            adapter_name="opencode-cli",
            detected_version=parse_binary_version(OPENCODE_BINARY),
            tested_up_to=_TESTED_UP_TO,
            compat_min=MIN_VERSION,
            compat_max=MAX_VERSION,
        )
        self._model = model
        # See class docstring for thread-safety invariant.
        self._last_mcp_servers: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return "opencode-cli"

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Wraps `SubprocessAdapter.run` + records RunManifest sidecar metadata.

        Per Story 10.1 HIGH-4 lesson UPSTREAM (Story 11.1 D-6): every
        adapter run records `record_active_run_metadata` so the Story 5.3
        RunManifest sidecar captures the per-run identity. Mirrors
        `codex_cli.py:run` (streamed-JSONL Case A — no `HostedMcpObserver`
        wiring; DF-OPENCODE-S1 / C99 carry-over).
        """
        from AgentEval.telemetry.listener import record_active_run_metadata

        # Stash for `_finalize` mcp_coverage resolution (base ABC doesn't
        # thread `mcp_servers` into `_finalize`).
        self._last_mcp_servers = mcp_servers
        try:
            result = super().run(prompt, tools=tools, mcp_servers=mcp_servers, **kwargs)
        finally:
            self._last_mcp_servers = None
        record_active_run_metadata(
            adapter_name=self.name,
            # `self.version` is the AgentEval distribution/package version
            # (metadata), NOT the `opencode` binary version — the binary
            # version is gated/tracked via `_assert_binary_version` +
            # `_TESTED_UP_TO` (cross-LLM review 2026-06-25 kilo MED-5).
            adapter_version=self.version,
            model=self._model,
            mcp_servers=_manifest_entries_from_servers(mcp_servers),
            total_cost_usd=result.cost_usd,
            completeness=result.metadata.completeness,
            mcp_coverage=result.metadata.mcp_coverage,
            prompt_hashes=[_hash_prompt(prompt)],
        )
        return result

    def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:
        """Launch ``opencode run --format json`` with the prompt as positional argv.

        - ``--format json`` (probe-verified): stream raw JSON events to
          stdout for the base ``run()`` line-iteration to parse.
        - ``--dangerously-skip-permissions``: required for autonomous
          non-interactive tool use (per ``opencode run --help``:
          "auto-approve permissions that are not explicitly denied").
          Without it, tool dispatch blocks on an interactive prompt.
        - prompt passed as the trailing positional ``message`` argument
          AFTER a ``--`` end-of-options sentinel (Story 4.2 HIGH-A /
          Story 11.1 D-1 UPSTREAM lesson: positional argv, not stdin).
          The ``--`` guard (cross-LLM review 2026-06-25 Claude MED-4,
          probe-verified that ``opencode run ... -- "<prompt>"`` honors
          the sentinel) prevents an adversarial / dataset-supplied prompt
          beginning with ``-`` (e.g. ``--help``, ``--model x``) from being
          parsed as a flag — a real argv-injection surface in an eval
          harness where prompts are often dataset-controlled.
        - ``stderr=subprocess.STDOUT`` multiplex (Story 4.2 HIGH-B /
          Story 11.1 D-2 UPSTREAM): the base ``run()`` only drains
          ``proc.stdout``; multiplexing prevents a stderr-buffer-full
          child from wedging the parent. ``_parse_event`` returns
          ``None`` on the non-JSON log chatter that lands on stdout.
        - ``stdin=subprocess.DEVNULL`` (cross-LLM review 2026-06-25 Claude
          LOW-5): the child should never read stdin under
          ``--dangerously-skip-permissions`` + a positional message;
          DEVNULL removes any chance of a non-TTY stdin read blocking
          under pabot/CI.

        Required Popen flags per Story 1b.4 base.py: ``stdout=PIPE``,
        ``stderr=STDOUT``, ``text=True``, ``start_new_session=True``
        (process-group hygiene for cleanup-on-exception).
        """
        # Phase-1: forward `tools` / `mcp_servers` but don't act on them
        # at this layer (DF-OPENCODE-S1 carry-over).
        _ = kwargs

        cmd = [
            OPENCODE_BINARY,
            "run",
            "--format",
            "json",
            "--dangerously-skip-permissions",
        ]
        if self._model is not None:
            cmd.extend(["--model", self._model])
        # `--` end-of-options sentinel then the positional `message`
        # argument (probe-verified 2026-06-25 — guards leading-dash
        # prompts; Claude cross-LLM MED-4).
        cmd.append("--")
        cmd.append(prompt)
        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

    def _parse_event(self, line: str) -> OpenCodeEvent | None:
        """Parse one stdout JSONL line into an `OpenCodeEvent`, or None to skip.

        Returns ``None`` for: empty lines, non-JSON lines (log chatter
        multiplexed in via stderr), non-dict JSON, and dicts missing a
        string ``type`` discriminator (forward-compat).
        """
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
        return OpenCodeEvent(event_type=event_type, raw=parsed)

    def _finalize(self, events: list[OpenCodeEvent], exit_code: int) -> AgentRunResult:
        """Fold the event stream into an `AgentRunResult`.

        Story 4.2 MED-3 / Story 11.1 D-3 UPSTREAM: when ``exit_code != 0``
        AND no terminal ``step_finish reason=stop`` event AND
        ``response_text`` is empty (no ``text`` events, or all of them
        empty), surface a ``[SUBPROCESS_NONZERO_EXIT exit_code=<N>]``
        diagnostic marker so consumers distinguish "agent declined" (empty
        text, clean exit) from "binary refused to run" (subprocess
        failure). M_R11 fail-loud. (Condition precisely stated per
        cross-LLM review 2026-06-25 kilo MED-4 — the trigger is empty
        ``response_text``, which is stricter than "no assistant text".)
        """
        terminal = next((e for e in reversed(events) if e.is_terminal), None)

        # Response text: concatenate every `text` event in chronological
        # order (intermediate narration + final response).
        texts = [e.text_content for e in events if e.text_content]
        response_text = "\n".join(texts) if texts else ""

        # Fail-loud diagnostic when the subprocess failed silently.
        if not response_text and exit_code != 0 and terminal is None:
            response_text = f"[SUBPROCESS_NONZERO_EXIT exit_code={exit_code}]"

        # Tool calls: synthesize a `ToolCallTrace` from every `tool_use`
        # event. A non-"completed" state status OR non-zero command exit
        # surfaces as `ToolCallTrace.error`.
        #
        # Single-emission assumption (cross-LLM review 2026-06-25 Claude
        # LOW-3): the empirical probe shows opencode emits exactly ONE
        # `tool_use` event per `callID`, already carrying the terminal
        # `state` (status ∈ {"completed","error"}). If a future opencode
        # version streams an interim `tool_use` on dispatch + another on
        # completion, this loop would double-count the `callID`. Phase-1
        # accepts the single-emission assumption; observer-based
        # correlation (DF-OPENCODE-S1 / C99) is the upgrade path.
        tool_calls: list[ToolCallTrace] = []
        seq = 0
        for ev in events:
            payload = ev.tool_payload
            if payload is None:
                continue
            state = _as_dict(payload.get("state"))
            status = state.get("status")
            metadata = _as_dict(state.get("metadata"))
            cmd_exit = metadata.get("exit")
            error_marker: str | None = None
            if status not in (None, "completed"):
                error_marker = str(state.get("error") or status)
            elif isinstance(cmd_exit, int) and cmd_exit != 0:
                error_marker = f"exit_code={cmd_exit}"
            tool_calls.append(
                ToolCallTrace(
                    name=str(payload.get("tool") or ""),
                    args=_as_dict(state.get("input")),
                    result=state.get("output"),
                    error=error_marker,
                    latency_ms=0.0,  # Phase-1 placeholder; observer wiring is DF-OPENCODE-S1.
                    source="adapter",
                    gen_ai_tool_call_id=str(payload.get("callID") or ""),
                    sequence_index=seq,
                )
            )
            seq += 1

        # Usage: sum per-step `step_finish.tokens` across every step (each
        # step is a distinct billable LLM call; tokens are per-step, NOT
        # cumulative — empirically verified 2026-06-25). Cross-check is
        # DF-OPENCODE-S2 / C100.
        input_tokens = 0
        output_tokens = 0
        reasoning_tokens = 0
        cached_tokens = 0
        cost_usd = 0.0
        for ev in events:
            if not ev.is_step_finish:
                continue
            tokens = ev.step_tokens
            input_tokens += int(tokens.get("input") or 0)
            output_tokens += int(tokens.get("output") or 0)
            reasoning_tokens += int(tokens.get("reasoning") or 0)
            cache = _as_dict(tokens.get("cache"))
            cached_tokens += int(cache.get("read") or 0)
            cost_usd += ev.step_cost
        usage = Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_tokens,
            reasoning_output_tokens=reasoning_tokens,
        )

        # Latency: opencode carries no aggregate-duration field. Phase-1
        # placeholder 0.0; observer wiring would correlate wall-clock
        # latency in DF-OPENCODE-S1.
        latency_seconds = 0.0

        # Completeness: "complete" when a terminal `step_finish reason=stop`
        # event is present + exit_code 0; else "truncated".
        #
        # Cross-LLM review 2026-06-25 kilo MED-3 (REJECTED with rationale):
        # kilo proposed downgrading completeness to "truncated" when any
        # `tool_call.error` is set. Rejected — `completeness` means "did the
        # agent run reach its terminal turn vs get cut off", NOT "did every
        # tool succeed". A tool erroring while the agent still reaches
        # `reason=stop` is normal agent behavior; the failure is faithfully
        # surfaced on `ToolCallTrace.error`, not by mislabeling the run as
        # truncated. Conflating the two would also DIVERGE from the
        # codex/copilot sibling precedent (both gate completeness on
        # terminal+exit_code only). Kept consistent on purpose.
        completeness: str = "complete" if terminal is not None and exit_code == 0 else "truncated"

        mcp_coverage = self._detect_mcp_coverage(getattr(self, "_last_mcp_servers", None))

        return AgentRunResult(
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            metadata=AgentRunMetadata(
                completeness=completeness,  # type: ignore[arg-type]
                mcp_coverage=mcp_coverage,  # type: ignore[arg-type]
            ),
            cost_usd=cost_usd,
            # Phase-1 placeholder; Story 5.3 / Epic 5 wires the real
            # trace-id (mirrors `codex_cli.py` / `copilot_cli.py`).
            # opencode surfaces a `sessionID` per event — a future
            # enhancement could thread it here (DF-OPENCODE-S1).
            latency_seconds=latency_seconds,
            trace_id="",
        )

    def _detect_mcp_coverage(self, mcp_servers: dict[str, Any] | None) -> str:
        """Detection-contract per ADR-016 §Decision L33.

        - Empty / None ``mcp_servers``: ``"hosted_in_process"``
          (trivially honest — nothing to cover).
        - Non-empty ``mcp_servers`` without verified hosted-attachment:
          ``"external_mixed"`` per ADR-016 §Decision L33 safer-default
          rule. The optimistic ``"hosted_in_process"`` branch is deferred
          to DF-OPENCODE-S1 / C99 — opencode's JSON event surface doesn't
          confirm MCP attachment, so observer-based detection is the only
          honest upgrade path.
        """
        if not mcp_servers:
            return "hosted_in_process"
        return "external_mixed"
