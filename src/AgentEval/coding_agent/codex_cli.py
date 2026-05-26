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

"""`CodexCLIAdapter` — `SubprocessAdapter` for the `codex` CLI (Story 11.1 / PRD FR12 + FR13c).

Wraps the OpenAI Codex CLI binary (`codex` v0.100.0–v1.0) invoked with
`codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check
--json "<prompt>"` to produce a normalized `AgentRunResult`. Implements
the Story 1b.4 ratified 3-hook `SubprocessAdapter` template-method
pattern per ADR-003.

## Phase-1 pinned binary range

Per PRD FR47 + ADR-010 (Copilot CLI per-CLI version-pinning precedent) +
Story 4.2 ClaudeCodeCLIAdapter precedent, this adapter pins the `codex`
binary to `>=0.100.0,<1.0`. Below `0.100.0` predates the documented
`--json` JSONL stream-output flag. The local probe at story-authoring
time was `codex-cli 0.133.0` (in range).

Note the `codex --version` output format is ``codex-cli <semver>``;
the base ``_assert_binary_version`` helper's default ``_SEMVER_RE.search()``
extracts ``0.133.0`` from ``codex-cli 0.133.0`` via substring search —
no per-adapter regex override is required (D-10 is a documentation
note only). *Patched 2026-05-26 per kilo M-1 + copilot MED-1: the
pre-edit text claimed `_VERSION_RE` was used; that constant was dead
code and is now removed.*

## Stream-json schema (empirical probe 2026-05-26)

Captured via behavioral probe BEFORE writing this adapter (per
`feedback_listener_hook_api_surface_empirical_check` Epic 8 retro
NEW norm + Story 10.1 HIGH-1 lesson — never assume the SDK shape).
The 4 event types:

- ``thread.started`` — carries ``thread_id`` (session metadata).
- ``turn.started`` — no payload (turn boundary marker).
- ``item.started`` / ``item.completed`` — carries
  ``item: {id, type, ...}`` where ``type`` ∈ ``{"agent_message",
  "command_execution"}``. ``agent_message`` items carry ``text``;
  ``command_execution`` items carry ``command``, ``aggregated_output``,
  ``exit_code``, ``status``.
- ``turn.completed`` — terminal event; carries
  ``usage: {input_tokens, cached_input_tokens, output_tokens,
  reasoning_output_tokens}``. **No ``cost_usd`` field** — Codex pricing
  is `gpt-5-codex`-tier; cost-catalog integration is DF-11.1-S2 carry-
  over. Phase-1 `cost_usd=0.0` placeholder.

Phase-1 ``mcp_coverage`` = ``external_mixed`` for non-empty
``mcp_servers`` per ADR-016 §Decision L33 safer-default rule. Codex JSONL events
do NOT surface MCP-attachment confirmation, so detection-failure path is
the only honest default until ``HostedMcpObserver`` wiring lands
(DF-11.1-S1; mirrors Story 10.1's DF-10.1-S2 + Story 10.2's DF-10.2-S1).

## Cross-story UPSTREAM lessons applied (first use of `feedback_cross_story_upstream_lesson_propagation`)

This adapter ships with **9 cross-story lessons from Stories 4.2 + 10.1 +
10.2 applied UPSTREAM** — see Story 11.1 spec drift-check D-1 through
D-11. The most load-bearing:

- D-1 (Story 4.2 HIGH-A): prompt passed as positional argv after ``--``,
  NOT via stdin (stdin caused 4-second indefinite hang on Claude Code).
- D-2 (Story 4.2 HIGH-B): ``stderr=subprocess.STDOUT`` multiplex to
  avoid pipe-deadlock under verbose output.
- D-3 (Story 4.2 MED-3): ``[SUBPROCESS_NONZERO_EXIT exit_code=<N>]``
  diagnostic when subprocess exits non-zero with no terminal event.
- D-7 (Stories 10.1 + 10.2): ``external_mixed`` default on non-empty
  ``mcp_servers`` per ADR-016 §Decision L33 (NOT optimistic ``hosted_in_process``).
- D-9 (empirical probe): ``cost_usd=0.0`` placeholder (Codex events
  carry no cost field).

References:
    - PRD FR12, FR13c (Codex adapter scope), FR17a (entry-points), FR47 (binary version gate).
    - ADR-003 (SubprocessAdapter template-method, 3 abstract hooks).
    - ADR-002 (Tier-1 Adapter Ceiling Rule — ≤2 adapters per vendor +
      generic escape hatch; Codex CLI (Story 11.1) covers OpenAI). [Per
      Story 4.2 code-review Auditor HIGH-1: NOT ADR-005, which is
      conformance-suite fidelity oracles.]
    - ADR-010 (Copilot CLI version-pin precedent; per-CLI pinning pattern).
    - ADR-016 §Decision L33 (ratifies ``external_mixed`` as the catch-all
      safe default when no instrumented servers were attached during the
      run). The §Alternatives section L59 cites the rejected
      ``"library_only"`` default — historical context only. (ADR-016
      supersedes the pre-renumbered ADR-A6 per Epic 10 Story 10.1 kilo
      MED-2 catch; §Decision L33 supersedes the original L59 citation
      per Story 11.1 copilot MED-2 catch — L59 was in the rejected-
      alternatives section, not the ratified Decision.)
    - Story 1b.4 `coding_agent/base.py:SubprocessAdapter` +
      `_assert_binary_version` helper.
    - Story 4.2 ClaudeCodeCLIAdapter precedent (`claude_code_cli.py`).
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

__all__ = ["CodexCLIAdapter", "CodexEvent"]


CODEX_BINARY = "codex"
MIN_VERSION = "0.100.0"
MAX_VERSION = "1.0.0"

# `codex --version` prints e.g. ``codex-cli 0.133.0`` (Story 11.1 D-10).
# The base `_assert_binary_version` helper's default `_SEMVER_RE.search()`
# extracts the semver substring without an override — no module-level
# regex constant is needed. (Removed 2026-05-26 per kilo M-1 + copilot
# MED-1 cross-LLM review — pre-edit declared `_VERSION_RE` as dead code.)


@dataclass(frozen=True)
class CodexEvent:
    """One parsed event from `codex exec --json` (Story 11.1).

    Phase-1 captures the union of Codex CLI's JSONL event types as a
    single dataclass with a discriminator (``event_type``) + raw payload.
    Convenience accessors handle the common nested paths so downstream
    code doesn't dictionary-descend at every call site.
    """

    event_type: str
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # M_R6 shallow-copy pattern: protect against caller mutation
        # after construction (mirrors Story 4.2's ClaudeCodeEvent).
        object.__setattr__(self, "raw", dict(self.raw))

    @property
    def is_terminal(self) -> bool:
        """True when this is the ``turn.completed`` terminal event."""
        return self.event_type == "turn.completed"

    @property
    def item_type(self) -> str:
        """Extract the inner ``item.type`` for ``item.*`` events; empty otherwise.

        Codex emits ``item.type`` ∈ ``{"agent_message", "command_execution"}``
        as of v0.133.0.
        """
        if not self.event_type.startswith("item."):
            return ""
        item = self.raw.get("item") or {}
        return str(item.get("type") or "")

    @property
    def agent_message_text(self) -> str:
        """Extract joined text from an ``item.completed`` agent_message event."""
        if self.event_type != "item.completed" or self.item_type != "agent_message":
            return ""
        item = self.raw.get("item") or {}
        return str(item.get("text") or "")

    @property
    def command_execution_payload(self) -> dict[str, Any] | None:
        """Return the ``item`` dict for a completed command_execution, else None.

        Only completed (``item.completed``) command executions surface
        here — in-progress (``item.started``) ones are skipped because
        their ``aggregated_output`` is empty + ``exit_code`` is ``null``.
        """
        if self.event_type != "item.completed" or self.item_type != "command_execution":
            return None
        item = self.raw.get("item") or {}
        return dict(item)

    @property
    def terminal_usage(self) -> Usage | None:
        """Extract a `Usage` record from a ``turn.completed`` event.

        Story 11.1 kilo cross-LLM review HIGH-1 fix 2026-05-26: pre-edit
        dropped ``reasoning_output_tokens`` silently — Codex emits all 4
        usage fields verbatim and downstream cost-catalog integration
        (DF-11.1-S2 / C74) requires the reasoning-tokens field. The
        ``Usage`` dataclass was extended to carry the 4th field at the
        same commit (`AgentEval/types.py:Usage`).
        """
        if not self.is_terminal:
            return None
        usage_raw = self.raw.get("usage") or {}
        return Usage(
            input_tokens=int(usage_raw.get("input_tokens") or 0),
            output_tokens=int(usage_raw.get("output_tokens") or 0),
            cached_input_tokens=int(usage_raw.get("cached_input_tokens") or 0),
            reasoning_output_tokens=int(usage_raw.get("reasoning_output_tokens") or 0),
        )


class CodexCLIAdapter(SubprocessAdapter):
    """`SubprocessAdapter` for the `codex` CLI (Story 11.1 / PRD FR13c).

    Implements the 3-hook template-method pattern per ADR-003. Calls
    ``_assert_binary_version(CODEX_BINARY, ">=0.100.0,<1.0")`` at
    construction; raises ``UnsupportedBinaryVersionError`` on out-of-range.

    **Thread safety: NOT concurrent-safe.** ``run()`` uses
    ``self._last_mcp_servers`` instance state to thread ``mcp_servers``
    through to ``_finalize`` (Phase-1 single-threaded-per-instance
    design; see DF-11.1-S1 / C73 for the Phase-2 observer-based path
    that eliminates this limitation). **Do not call ``run()``
    concurrently on the same ``CodexCLIAdapter`` instance** — the
    second thread's ``mcp_servers`` will overwrite the first's before
    ``_finalize`` reads it, silently corrupting ``mcp_coverage``.
    Construct one adapter per concurrent run if you need parallelism.
    *Documented inline 2026-05-26 per kilo M-2 + copilot MED-3 review.*
    """

    def __init__(self, *, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Story 1b.4 ratified helper validates the binary version at
        # construction. Raises `UnsupportedBinaryVersionError` on out-
        # of-range per FR47. The default `_SEMVER_RE.search()` in the
        # base helper extracts `0.133.0` from `codex-cli 0.133.0` via
        # substring search — no override needed (D-10 prefix is a
        # documentation note only, not a code requirement).
        self._assert_binary_version(CODEX_BINARY, min=MIN_VERSION, max=MAX_VERSION)
        self._model = model
        # Phase-1 single-threaded per-instance: stash the most recent
        # `mcp_servers` argument so `_finalize` can resolve mcp_coverage
        # honestly (the base ABC's `_finalize(events, exit_code)`
        # signature doesn't receive `mcp_servers`). Set by the `run()`
        # wrapper override below before delegating to `super().run()`.
        self._last_mcp_servers: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return "codex-cli"

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Wraps `SubprocessAdapter.run` + records RunManifest sidecar metadata.

        Per Story 10.1 HIGH-4 lesson UPSTREAM (Story 11.1 D-6): every
        adapter run records `_record_run_metadata` so the Story 5.3
        RunManifest sidecar captures the per-run identity. Mirrors
        `claude_code_cli.py:run` pattern but WITHOUT the `HostedMcpObserver`
        wiring (Phase-1 carve-out per DF-11.1-S1 — Codex JSONL surface
        doesn't expose MCP-attachment confirmation, so the observer
        integration is the Phase-2 path).
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
        """Launch `codex exec --json` with the prompt as positional argv.

        Story 11.1 D-1 (cross-story UPSTREAM from Story 4.2 HIGH-A): the
        prompt is passed as positional argv, NOT via stdin. Per
        ``codex exec --help``: "Initial instructions for the agent. If
        not provided as an argument (or if ``-`` is used), instructions
        are read from stdin." Positional argv avoids the stdin-buffering
        + pipe-deadlock class Story 4.2 caught against Claude Code.

        Story 11.1 D-2 (cross-story UPSTREAM from Story 4.2 HIGH-B):
        ``stderr=subprocess.STDOUT`` multiplex into stdout. The base
        ``run()`` only drains ``proc.stdout``, so a stderr-buffer-full
        child blocks → parent wedges. Multiplexing makes stderr
        diagnostic chatter cleanly ignored (``_parse_event`` returns
        ``None`` on non-JSON lines per its contract).

        Required Popen flags per Story 1b.4 base.py L240-244:
        ``stdout=PIPE``, ``stderr=STDOUT``, ``text=True``,
        ``start_new_session=True`` (process-group hygiene for
        cleanup-on-exception).

        Phase-1 carve-out: ``tools`` + ``mcp_servers`` kwargs are accepted
        per the base ``run(prompt, tools, mcp_servers, **kwargs)``
        signature but Phase-1 Codex CLI integration relies on the
        operator providing MCP via the standard ``codex mcp`` subcommand
        + ``~/.codex/config.toml``. Full ``mcp_servers=`` integration via
        observer is DF-11.1-S1 (mirrors Story 4.2's DF-4.2-S1 +
        Story 10.1's DF-10.1-S2 + Story 10.2's DF-10.2-S1).
        """
        # Phase-1: forward `tools` / `mcp_servers` but don't act on them
        # at this layer (DF-11.1-S1 carry-over).
        _ = kwargs

        cmd = [
            CODEX_BINARY,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--json",
            # No end-of-options sentinel here — `codex exec` takes the
            # prompt as the trailing positional argument; the `--json`
            # flag must precede it.
            prompt,
        ]
        # Story 11.1 D-1 + D-2 wiring (cross-story UPSTREAM from Story 4.2).
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

    def _parse_event(self, line: str) -> CodexEvent | None:
        """Parse one stdout JSONL line into a `CodexEvent`, or None to skip.

        Returns ``None`` for: empty lines, non-JSON lines (stderr chatter
        multiplexed in per D-2), non-dict JSON, and dicts missing a
        ``type`` discriminator (forward-compat).
        """
        stripped = line.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            # Non-JSON line (progress chatter, debug output, stderr
            # interleaved per D-2). Skip per Story 1b.4 contract.
            return None
        if not isinstance(parsed, dict):
            return None
        event_type = parsed.get("type")
        if not isinstance(event_type, str):
            return None
        return CodexEvent(event_type=event_type, raw=parsed)

    def _finalize(self, events: list[CodexEvent], exit_code: int) -> AgentRunResult:
        """Fold the event stream into an `AgentRunResult`.

        Story 11.1 D-3 (cross-story UPSTREAM from Story 4.2 MED-3):
        when ``exit_code != 0`` AND no terminal ``turn.completed`` event
        was observed AND no agent_message text was produced, surface a
        ``[SUBPROCESS_NONZERO_EXIT exit_code=<N>]`` diagnostic marker so
        consumers can distinguish "agent declined to respond" (empty
        ``response_text`` on a clean exit) from "binary refused to run"
        (subprocess failure). M_R11 fail-loud.
        """
        terminal = next((e for e in reversed(events) if e.is_terminal), None)

        # Response text: concatenate every `agent_message` item.completed
        # text in chronological order. Codex emits multiple agent_message
        # items per turn (intermediate narration + final response — see
        # the `tool_use` empirical probe at /tmp/codex_tool_probe.jsonl).
        agent_texts = [e.agent_message_text for e in events if e.agent_message_text]
        response_text = "\n".join(agent_texts) if agent_texts else ""

        # D-3 cross-story UPSTREAM diagnostic when subprocess failed
        # silently. Mirrors Story 4.2 `claude_code_cli.py:_finalize` MED-3
        # patch verbatim modulo the event-type names.
        if not response_text and exit_code != 0 and terminal is None:
            response_text = f"[SUBPROCESS_NONZERO_EXIT exit_code={exit_code}]"

        # Tool calls: synthesize `ToolCallTrace` from every completed
        # command_execution item. Phase-1 carve-out (DF-11.1-S1): full
        # OTel-span correlation + latency extraction lands in the
        # observer wiring (mirrors Story 4.2 DF-4.2-S1 + Story 10.1
        # DF-10.1-S2). ``command_execution`` items don't have a
        # standard tool name; we use ``"command_execution"`` literal so
        # downstream `Get Tool Call Names` keywords surface a stable key.
        tool_calls: list[ToolCallTrace] = []
        seq = 0
        for ev in events:
            payload = ev.command_execution_payload
            if payload is None:
                continue
            cmd_exit_code = payload.get("exit_code")
            error_marker: str | None = None
            if isinstance(cmd_exit_code, int) and cmd_exit_code != 0:
                error_marker = f"exit_code={cmd_exit_code}"
            tool_calls.append(
                ToolCallTrace(
                    name="command_execution",
                    args={"command": str(payload.get("command") or "")},
                    result=str(payload.get("aggregated_output") or ""),
                    error=error_marker,
                    latency_ms=0.0,  # Phase-1 placeholder; observer wiring is DF-11.1-S1.
                    source="adapter",
                    gen_ai_tool_call_id=str(payload.get("id") or ""),
                    sequence_index=seq,
                )
            )
            seq += 1

        # Usage: from terminal `turn.completed.usage`; zeros fallback on
        # truncated runs.
        usage = (
            terminal.terminal_usage
            if terminal is not None and terminal.terminal_usage is not None
            else Usage(input_tokens=0, output_tokens=0)
        )

        # Cost: Codex events carry NO cost field (D-9 empirical probe).
        # Phase-1 placeholder 0.0; DF-11.1-S2 tracks cost-catalog
        # integration for `gpt-5-codex`-tier pricing.
        cost_usd = 0.0

        # Latency: Codex events carry no per-turn duration field either.
        # Phase-1 placeholder 0.0; observer wiring would correlate wall-
        # clock latency in DF-11.1-S1.
        latency_seconds = 0.0

        # Completeness: "complete" when terminal event present + exit_code 0;
        # else "truncated".
        completeness: str = "complete" if terminal is not None and exit_code == 0 else "truncated"

        # MCP coverage per Story 11.1 D-7 (cross-story UPSTREAM from
        # Stories 10.1 + 10.2 post-HIGH-2 contract): we can't inspect
        # `mcp_servers` from `_finalize`, so the contract is keyed in
        # `run()` and `_detect_mcp_coverage` — but Phase-1's
        # observer-less detection means we default to `"external_mixed"`
        # whenever any MCP integration is requested at the run layer.
        # `_finalize` doesn't see `mcp_servers`; the keying is via
        # `run()` calling `_detect_mcp_coverage(mcp_servers)` and
        # storing the result on the instance. Phase-1 carve-out for
        # this story: the helper isn't wired through `_finalize` (the
        # base `run()` doesn't pass `mcp_servers` to `_finalize`) — so
        # this method returns the safer default `external_mixed` when
        # `mcp_servers` was non-empty, else `hosted_in_process`. The
        # base run() stores mcp_servers as `self._last_mcp_servers` for
        # this read (set by the wrapped run() override above).
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
            latency_seconds=latency_seconds,
            trace_id="",  # Story 11.1 Phase-1 placeholder; Story 5.3 + Epic 5 wire real trace-id.
        )

    def _detect_mcp_coverage(self, mcp_servers: dict[str, Any] | None) -> str:
        """Detection-contract per ADR-016 §Decision L33 (Story 11.1 D-7).

        - Empty / None ``mcp_servers``: ``"hosted_in_process"``
          (trivially honest — nothing to cover).
        - Non-empty ``mcp_servers`` without verified hosted-attachment:
          ``"external_mixed"`` per ADR-016 §Decision L33 safer-default rule.

        The optimistic ``"hosted_in_process"`` branch on non-empty MCP
        is deferred to DF-11.1-S1 (mirrors Story 10.1 DF-10.1-S2 +
        Story 10.2 DF-10.2-S1) — Codex JSONL events don't surface MCP-
        attachment confirmation, so observer-based detection is the
        only honest upgrade path.
        """
        if not mcp_servers:
            return "hosted_in_process"
        return "external_mixed"
