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

"""Coding-agent adapter base classes — `InProcessAdapter` + `SubprocessAdapter`.

Per ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md`)
L22-29 + architecture L1226-1228:

- `InProcessAdapter` — base class for SDK-driven adapters. Direct
  method-override pattern; NO abstract hooks. SDK behavior is structured
  enough to populate `AgentRunResult` directly (per ADR-003 L22-23).
  Subclasses override `run()` directly. Examples (Epic 4 + Epic 10):
  Generic LiteLLM (`GenericAdapter(InProcessAdapter)`), Claude Agent SDK,
  OpenAI Agents SDK.

- `SubprocessAdapter(ABC)` — base class for CLI-driven adapters. Abstract
  template-method pattern with EXACTLY 3 `@abstractmethod` hooks subclasses
  MUST implement (per ADR-003 L24-29 + architecture L1228):
    * `_spawn(prompt, **kwargs) -> subprocess.Popen[str]`
    * `_parse_event(line) -> ParsedEvent | None`
    * `_finalize(events, exit_code) -> AgentRunResult`
  The base implements `run()` itself as a template method orchestrating
  spawn → JSONL-line iteration through `_parse_event` (collecting non-None
  events) → `_finalize`. Plus the concrete `_assert_binary_version`
  helper raising `UnsupportedBinaryVersionError` per FR47.

The `CodingAgentAdapter` Protocol itself lives at `src/AgentEval/types.py`
(re-exported through this module) per architecture L853 cross-sub-library
import discipline + Story 1b.3 `_kernel/discovery.py` L102 TYPE_CHECKING
forward-ref. This module re-exports the Protocol + `AgentRunResult`
dataclass for contributor-facing import ergonomics:

    from AgentEval.coding_agent import (
        CodingAgentAdapter, InProcessAdapter, SubprocessAdapter, AgentRunResult,
    )

`ParsedEvent` is `TypeAlias = Any` in Story 1b.4. Concrete CLI adapters in
Epic 4 (Story 4.2 Claude Code CLI) + Epic 11 (Codex CLI + Copilot CLI)
declare per-adapter concrete intermediate event types (`ClaudeCodeEvent`,
`CodexEvent`, `CopilotEvent`) per architecture L1228's per-adapter pattern.

Phase-1 scope boundary (Story 1b.4 code-review D14 ratification):
    Sandbox integration is OUT-OF-SCOPE for adapters per architecture
    L1523 — sandbox routes through `scenarios/` + `security/policy.py`.
    Adapters do NOT directly invoke sandboxed code execution.

References:
    - ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md`)
    - ADR-005 — ≤2 adapters per vendor + 1 universal escape hatch
    - ADR-010 — Copilot CLI version pin `>=1.0.9,<2.0` (exemplar)
    - PRD FR12 (single `run()` Protocol method)
    - PRD FR47 (`<binary> version <X> outside tested range <range>` format)
    - PRD FR51 (`trace_id=<uuid>` RF-report-line attribute)
    - Architecture L885-889 (`AgentRunResult` shape example)
    - Architecture L1226-1228 (location + hook names)
    - Story 1b.1 `_kernel/context.py` (`ServerHandle` + process-group hygiene)
    - Story 1b.3 `_kernel/discovery.py` (TYPE_CHECKING forward-ref consumer)
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import logging
import os
import re
import signal
import subprocess
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from AgentEval.errors import UnsupportedBinaryVersionError
from AgentEval.types import (
    AgentRunResult,
)
from AgentEval.types import (
    CodingAgentAdapter as CodingAgentAdapter,
)

if TYPE_CHECKING:
    from AgentEval._kernel.context import ServerHandle

_log = logging.getLogger(__name__)

__all__ = [
    "CodingAgentAdapter",
    "InProcessAdapter",
    "SubprocessAdapter",
    "AgentRunResult",
    "ParsedEvent",
]


# Story 1b.4 placeholder per AC-1b.4.4. Concrete adapters in Epic 4 / Epic 11
# declare per-adapter concrete intermediate event types per architecture
# L1228; until then, `Any` keeps the template-method `run()` orchestration
# fully typeable while leaving the event shape adapter-specific.
type ParsedEvent = Any


# Semver-ish regex used by the default `_assert_binary_version` implementation
# to extract a `MAJOR.MINOR[.PATCH]` substring from arbitrary `<binary>
# --version` output. CLIs with non-standard version-output formats (e.g.,
# `npm-style "Claude Code 1.0.9 (build abc)"`) work because the regex
# captures the first matching substring. Subclasses MAY override
# `_assert_binary_version` if their CLI uses a different version-extraction
# pattern.
_SEMVER_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


def _default_version(module_name: str) -> str:
    """Resolve the installed-distribution version for the given module's top-level package.

    Story 1b.4 code-review D5 ratification (Codex STAR catch): the pre-edit
    implementation used `importlib.metadata.version(top_level_pkg)` directly,
    which falls back to `"unknown"` for in-tree adapter modules where the
    module's top-level package name (e.g., `AgentEval`) differs from the
    installed distribution name (e.g., `robotframework-agenteval`). The
    fixed implementation first consults `importlib.metadata.packages_distributions()`
    to map module → distribution; if exactly one distribution matches it
    uses that one, otherwise falls back to the top-level module-name
    heuristic, then finally to `"unknown"` on any metadata-resolution
    failure.

    Broader exception catch (P3): swallows `(PackageNotFoundError, OSError,
    KeyError)` so corrupt metadata + race conditions on the metadata
    filesystem don't propagate from an adapter's `.version` property read.
    """
    top_level = module_name.split(".")[0]
    try:
        distributions_map = importlib.metadata.packages_distributions()
        candidates = distributions_map.get(top_level, [])
        if len(candidates) == 1:
            return importlib.metadata.version(candidates[0])
        # Multiple-distribution or zero-distribution cases fall through to
        # the top-level-name lookup. Concrete adapters SHOULD override
        # `version` explicitly when their module / distribution mapping is
        # ambiguous (per deferred-work.md DF2).
        return importlib.metadata.version(top_level)
    except (importlib.metadata.PackageNotFoundError, OSError, KeyError):
        return "unknown"


def _parse_version_tuple(version: str) -> tuple[int, int, int]:
    """Parse a `MAJOR.MINOR[.PATCH]` string into a fixed-arity (M, m, p) tuple.

    Story 1b.4 code-review D3 ratification (3-WAY HIGH bug): the pre-edit
    implementation returned a variable-length tuple (e.g., `(1, 0)` for
    `"1.0"` vs `(1, 0, 0)` for `"1.0.0"`), causing Python lexicographic
    comparison `(1, 0) < (1, 0, 0)` to evaluate True — so `"1.0"` was
    incorrectly flagged below the `"1.0.0"` floor. The fix pads to
    fixed-arity 3 by zero-extending so `"1.0"` and `"1.0.0"` compare equal.

    Prerelease handling: the pre-edit `if part.isdigit()` filter silently
    dropped non-digit parts, so `"1.0.0a1"` collapsed to `(1, 0)`. The
    fixed implementation raises `ValueError` on prerelease-style strings
    (any non-purely-digit component); concrete adapters that need
    prerelease support should switch to `packaging.version.Version` per
    deferred-work.md DF8.

    Args:
        version: `MAJOR.MINOR[.PATCH]` string (e.g., `"1.0"`, `"2.0.0"`).

    Returns:
        Fixed-arity 3-tuple `(major, minor, patch)` of non-negative ints.

    Raises:
        ValueError: any component is not purely numeric (e.g., `"1.0.0a1"`,
            `"1.0.0-rc1"`).
    """
    parts = version.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(
            f"version {version!r} must be a purely-numeric MAJOR.MINOR[.PATCH] "
            "string; prerelease + build metadata not supported by the Phase-1 "
            "parser (see deferred-work.md DF8 for packaging.version migration)"
        )
    nums = [int(part) for part in parts]
    while len(nums) < 3:
        nums.append(0)
    if len(nums) > 3:
        raise ValueError(f"version {version!r} has more than 3 components; expected MAJOR.MINOR[.PATCH]")
    return (nums[0], nums[1], nums[2])


class InProcessAdapter:
    """Concrete-by-default base class for SDK-driven `CodingAgentAdapter` implementations.

    Per ADR-003 L22-23: direct method-override pattern; NO abstract hooks; SDK
    behavior is structured enough to populate `AgentRunResult` directly.

    Subclasses MUST override `run()` to deliver the agent's normalized result.
    The base provides:

    - `__init__(**kwargs)` capturing adapter-side config into
      `self._adapter_config: dict[str, Any]`.
    - `name` property returning `type(self).__name__` (overridable).
    - `version` property returning `importlib.metadata.version(top_level_pkg)`
      with `"unknown"` fallback on `PackageNotFoundError` (overridable).

    Story 1b.4 ships zero `@abstractmethod`-decorated members on this class
    — the duck-typed Protocol conformance check is via `CodingAgentAdapter`
    `@runtime_checkable` at registration time.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._adapter_config: dict[str, Any] = dict(kwargs)

    @property
    def name(self) -> str:
        return type(self).__name__

    @property
    def version(self) -> str:
        return _default_version(type(self).__module__)


class SubprocessAdapter(ABC):
    """Abstract template-method base class for CLI-driven `CodingAgentAdapter` implementations.

    Per ADR-003 L24-29 + architecture L1228: abstract template-method pattern
    with EXACTLY 3 hooks subclasses MUST implement. The base implements `run()`
    itself as the orchestration template + provides the concrete
    `_assert_binary_version` helper.

    Subclass contract:

    - `_spawn(prompt, **kwargs) -> subprocess.Popen[str]` — launch the CLI
      subprocess with proper env injection. The base's `run()` expects
      `stdout=subprocess.PIPE` + `stderr=subprocess.PIPE` + `text=True` +
      `start_new_session=True` (per Story 1b.1 `MCPLifecycleManager`
      process-group hygiene precedent) so cleanup-on-exception can call
      `os.killpg(os.getpgid(proc.pid), signal.SIGTERM)` if needed.

    - `_parse_event(line) -> ParsedEvent | None` — parse one JSONL event
      line into the adapter's per-adapter intermediate event type. Return
      `None` to skip non-event lines (progress chatter, blank lines).

    - `_finalize(events, exit_code) -> AgentRunResult` — fold the event
      stream into the final result. Receives the chronological list of
      non-None `_parse_event` returns + the subprocess exit code.

    The base `run()` orchestrates: `_spawn` → iterate `proc.stdout`
    line-by-line through `_parse_event` (collecting non-None events) →
    `proc.wait()` → `_finalize(events, proc.returncode)`. On exception in
    the body, the subprocess is terminated via `proc.terminate()` to honor
    process-group hygiene.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._adapter_config: dict[str, Any] = dict(kwargs)

    @property
    def name(self) -> str:
        return type(self).__name__

    @property
    def version(self) -> str:
        return _default_version(type(self).__module__)

    @abstractmethod
    def _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]:
        """Launch the CLI subprocess. See class docstring for required Popen flags."""
        ...

    @abstractmethod
    def _parse_event(self, line: str) -> ParsedEvent | None:
        """Parse one stdout line into the adapter's intermediate event type, or None to skip."""
        ...

    @abstractmethod
    def _finalize(self, events: list[ParsedEvent], exit_code: int) -> AgentRunResult:
        """Fold the parsed event stream into the final `AgentRunResult`."""
        ...

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, ServerHandle] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Template-method orchestration: spawn → iterate events → finalize.

        Phase-1 scope: `tools` + `mcp_servers` are forwarded to `_spawn(...)`
        as kwargs; concrete adapters in Epic 4/11 wire them into the CLI's
        env / args / config-file as appropriate for the specific binary.

        Process-group cleanup-on-exception (Story 1b.4 code-review D1 patch):
        on any exception in the body, the subprocess is terminated via
        `os.killpg(os.getpgid(proc.pid), SIGTERM)` (NOT `proc.terminate()`)
        so the whole process group is signaled — matching Story 1b.1
        `MCPLifecycleManager` precedent. If the group doesn't exit within
        the escalation window, sends `SIGKILL`. Subclasses MUST set
        `start_new_session=True` on the `_spawn` Popen for this to work
        correctly; absent `start_new_session=True`, `os.getpgid(proc.pid)`
        may return the parent process's group + SIGTERM the test runner
        itself — a hard failure documented in the `_spawn` docstring.
        """
        proc = self._spawn(prompt, tools=tools, mcp_servers=mcp_servers, **kwargs)
        events: list[ParsedEvent] = []
        if proc.stdout is None:
            # Explicit raise (NOT assert — assertions are stripped under
            # python -O per Story 1b.4 code-review P1 patch).
            raise TypeError(
                f"{type(self).__name__}._spawn() must return a Popen with stdout=subprocess.PIPE; got stdout=None"
            )
        try:
            for line in proc.stdout:
                parsed = self._parse_event(line)
                if parsed is not None:
                    events.append(parsed)
            exit_code = proc.wait()
        except BaseException:
            # Process-group hygiene (D1 + Story 1b.1 precedent):
            #   1. SIGTERM the whole process group.
            #   2. Wait up to escalation_seconds for graceful exit.
            #   3. Escalate to SIGKILL if still alive.
            # Suppresses (OSError, ProcessLookupError, PermissionError) so
            # cleanup never raises a secondary exception that would mask
            # the original.
            self._terminate_process_group(proc)
            raise
        finally:
            # Always close PIPE fds to prevent leaks on the success path.
            with contextlib.suppress(OSError):
                if proc.stdout is not None:
                    proc.stdout.close()
            with contextlib.suppress(OSError):
                if proc.stderr is not None:
                    proc.stderr.close()
        return self._finalize(events, exit_code)

    def _terminate_process_group(
        self,
        proc: subprocess.Popen[str],
        *,
        escalation_seconds: float = 5.0,
    ) -> None:
        """Send SIGTERM to the process group, escalating to SIGKILL on timeout.

        Story 1b.4 code-review D1 patch: matches Story 1b.1
        `MCPLifecycleManager` cleanup pattern. Requires the subprocess to
        have been spawned with `start_new_session=True` so it's the leader
        of its own process group; absent that flag, `os.getpgid(proc.pid)`
        may return the parent process's group + accidentally SIGTERM the
        test runner.

        Suppresses (OSError, ProcessLookupError, PermissionError) on all
        signal-delivery + reap operations so cleanup never raises a
        secondary exception that would mask the caller's original.
        """
        with contextlib.suppress(OSError, ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        try:
            proc.wait(timeout=escalation_seconds)
            return
        except subprocess.TimeoutExpired:
            _log.warning(
                "Subprocess %s did not exit within %.1fs after SIGTERM; escalating to SIGKILL",
                proc.pid,
                escalation_seconds,
            )
        except (OSError, ProcessLookupError):
            return
        with contextlib.suppress(OSError, ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            proc.wait(timeout=escalation_seconds)

    def _assert_binary_version(self, binary: str, min: str, max: str | None) -> None:
        """Validate the binary's version is within the pinned range, raising on mismatch.

        Invokes `<binary> --version`, extracts a semver-ish substring via
        `_SEMVER_RE`, then compares against `min` (inclusive) + `max`
        (exclusive when set). Composes `<range>` per AC-1b.4.7:
        `">={min}, <{max}"` when both bounds set, `">={min}"` when
        `max=None`.

        Story 1b.4 code-review D6+D7 patches: raises `UnsupportedBinaryVersionError`
        with the FR47-exact message format ON `str(exc)` (the leaf overrides
        `__str__` to skip the H_R7 prefix). Structured attrs (`binary`,
        `detected`, `min_version`, `max_version`) are exposed alongside the
        message for programmatic-response patterns. Returncode check (P4):
        non-zero exit from `<binary> --version` raises with `<exit-status-N>`
        placeholder so failure-mode is preserved. Broader OSError catch (P5):
        also handles `PermissionError` (executable bit missing) + generic
        `OSError`.

        Raises:
            UnsupportedBinaryVersionError: version below `min` OR
                (when `max` is set) at-or-above `max` OR unparseable
                `<binary> --version` output OR non-zero exit from
                `<binary> --version` invocation. FR47-exact message format
                `"<binary> version <X> outside tested range <range>"`.

        Subclasses MAY override if their CLI uses a non-`--version`
        invocation or non-semver output.
        """
        range_str = f">={min}, <{max}" if max is not None else f">={min}"
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError) as exc:
            raise UnsupportedBinaryVersionError(
                f"{binary} version <unavailable> outside tested range {range_str}",
                binary=binary,
                detected=None,
                min_version=min,
                max_version=max,
            ) from exc

        if result.returncode != 0:
            raise UnsupportedBinaryVersionError(
                f"{binary} version <exit-status-{result.returncode}> outside tested range {range_str}",
                binary=binary,
                detected=None,
                min_version=min,
                max_version=max,
            )

        match = _SEMVER_RE.search(result.stdout) or _SEMVER_RE.search(result.stderr)
        if match is None:
            raise UnsupportedBinaryVersionError(
                f"{binary} version <unparseable> outside tested range {range_str}",
                binary=binary,
                detected=None,
                min_version=min,
                max_version=max,
            )
        detected = match.group(1)
        try:
            detected_tuple = _parse_version_tuple(detected)
            min_tuple = _parse_version_tuple(min)
            max_tuple = _parse_version_tuple(max) if max is not None else None
        except ValueError as exc:
            # Either detected or min/max is a non-numeric / prerelease string;
            # surface as a typed UnsupportedBinaryVersionError per FR47.
            raise UnsupportedBinaryVersionError(
                f"{binary} version {detected} outside tested range {range_str}",
                binary=binary,
                detected=detected,
                min_version=min,
                max_version=max,
            ) from exc

        if detected_tuple < min_tuple or (max_tuple is not None and detected_tuple >= max_tuple):
            raise UnsupportedBinaryVersionError(
                f"{binary} version {detected} outside tested range {range_str}",
                binary=binary,
                detected=detected,
                min_version=min,
                max_version=max,
            )
