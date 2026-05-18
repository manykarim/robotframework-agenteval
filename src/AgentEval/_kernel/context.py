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

"""Per-test scope, MCP server lifecycle, and FR41 config precedence for agenteval.

This module hosts five concerns that share a per-pabot-worker lifecycle:

1. **Internal Scope vocabulary + translator** — `Scope` is the internal enum
   used by `MCPLifecycleManager`; `_resolve_scope()` is the SINGLE canonical
   translator from the user-facing Library kwarg (`bool | Literal["suite"]`
   per FR42 + ADR-009 + Story 1a.6) into Scope.
2. **Listener v3 `test_id` propagation** — `TestContext` dataclass + a
   `ContextVar`-backed `current_context()`/`bind_context()`/`unbind_context()`
   accessor trio. `set_current_test_id()` is the convenience wrapper called by
   the OTel listener (Epic 5 Story 5.1) at `start_test` / `end_test`.
3. **`MCPLifecycleManager`** — per-pabot-worker MCP-server-subprocess lifecycle
   per Story 0.2 spike findings §`_kernel/context.py` draft (load-bearing).
   Re-implements the patterns validated by the spike with all 18 review
   patches (P2.1-P2.18) + the D2.4 auto-installed SIGTERM handler integrated.
4. **atexit + auto-installed SIGTERM handler** — defense-in-depth cleanup so
   leaks don't accumulate when a pabot worker terminates. Python's default
   SIGTERM handler does NOT run atexit (D2.4 LOAD-BEARING finding); the
   handler installed here converts SIGTERM into `sys.exit(0)`, which does.
5. **FR41 config precedence** — `resolve_config()` resolves the AgentEval
   Library kwargs against the precedence chain `kwarg > env-var > .env > defaults`.
   Story 1a.6's `__init__.py` integrates with this for `Get Effective Config`.

Lifecycle guarantees (verified by Story 0.2 spike):
    - 45/45 smoke-matrix iters, zero leaks (Linux, mcp 1.27.1, RF 7.4.2, pabot 5.2.2)
    - SIGTERM-during-MCP-handshake: clean release (D2.3 probe, 5/5 iters)
    - SIGTERM-of-parent + auto-installed handler: clean release (D2.4 probe, 3/3 iters)
    - SIGKILL-of-parent: UNRECOVERABLE at listener layer (D2.4 probe scenario C).
      Operator must teardown via systemd cgroup / container-level mitigation.

Citation index for code-review re-derivation (per `feedback_citation_drift_first_class`):
    - architecture L314 / L410 / L1659 — user `mcp_per_test` 3-mode vocabulary
    - architecture L620 — `_agenteval_tier` single-underscore attribute convention (cited in tier.py, not here)
    - architecture L1198 — `context.py # Listener v3 test_id propagation context helpers`
    - architecture L1502 — Per-test scope routing table
    - architecture L1534-1587 — Listener v3 lifecycle flow
    - ADR-009 — `mcp_per_test: bool = True` ratified default
    - Story 0.2 spike findings §`_kernel/context.py` draft (L273-414) — LOAD-BEARING source for MCPLifecycleManager
    - deferred-work.md L40-47 — 12+ Story 0.2 review fixes applied
    - PRD FR41 — kwarg → env-var → `.env` → defaults precedence
    - `.env.example` — canonical AGENTEVAL_* env-var names
"""

from __future__ import annotations

import atexit
import contextlib
import errno
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType, MappingProxyType
from typing import Any, ClassVar, Literal

__all__ = [
    "Scope",
    "_resolve_scope",
    "TestContext",
    "current_context",
    "bind_context",
    "unbind_context",
    "set_current_test_id",
    "ServerSpec",
    "ServerHandle",
    "ReleaseResult",
    "MCPLifecycleManager",
    "resolve_config",
]


# --------------------------------------------------------------------------- #
# Internal Scope vocabulary + user-kwarg translator                           #
# --------------------------------------------------------------------------- #

Scope = Literal["test", "suite", "process"]
"""Internal scope enum used by MCPLifecycleManager.

Matches Story 0.2 spike's `MCPLifecycleManager.scope` vocabulary:
    - "test"     — one MCP server per test (corresponds to user kwarg True)
    - "suite"    — one MCP server per suite (corresponds to user kwarg "suite")
    - "process"  — one MCP server per pabot worker (corresponds to user kwarg False)
"""


def _resolve_scope(mcp_per_test: bool | Literal["suite"]) -> Scope:
    """Translate the user-facing `mcp_per_test` kwarg into the internal Scope enum.

    This is the SINGLE canonical mapping point between the two vocabularies in
    the project. All other code paths consume the resolved Scope, never the
    raw user kwarg.

    Args:
        mcp_per_test: User-facing kwarg per FR42 + ADR-009 + Story 1a.6.
            Valid values: True / False / "suite".

    Returns:
        Internal Scope:
            - True   → "test"
            - False  → "process"
            - "suite" → "suite"

    Raises:
        ValueError: If the input is not True/False/"suite".

    Truth table:
        | input    | output    |
        |----------|-----------|
        | True     | "test"    |
        | False    | "process" |
        | "suite"  | "suite"   |
    """
    if mcp_per_test is True:
        return "test"
    if mcp_per_test is False:
        return "process"
    if mcp_per_test == "suite":
        return "suite"
    raise ValueError(f"mcp_per_test must be True, False, or 'suite'; got {mcp_per_test!r}")


# --------------------------------------------------------------------------- #
# Listener v3 test_id propagation (TestContext + ContextVar)                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TestContext:
    """Per-test scope information stored in the current ContextVar."""

    # Pytest sentinel: prevents pytest from auto-collecting this dataclass as a
    # test class. The name happens to start with "Test" — convention here is
    # "TestContext = Listener v3 test scope", not "test case".
    __test__: ClassVar[bool] = False

    test_id: str
    suite_id: str
    scope: Scope


_current_context_var: ContextVar[TestContext | None] = ContextVar("agenteval_current_context", default=None)


def current_context() -> TestContext | None:
    """Return the TestContext bound to the current ContextVar, or None."""
    return _current_context_var.get()


def bind_context(ctx: TestContext) -> None:
    """Bind a TestContext to the current ContextVar.

    Notes:
        ContextVar Token is intentionally discarded for Phase-1 simplicity;
        callers clear via `unbind_context()`.
    """
    _current_context_var.set(ctx)


def unbind_context() -> None:
    """Clear the current ContextVar back to None."""
    _current_context_var.set(None)


def set_current_test_id(test_id: str, suite_id: str = "", scope: Scope = "test") -> None:
    """Convenience wrapper that builds a TestContext and binds it.

    Honors architecture L1554's `_kernel/context.set_current_test_id(test_id)`
    flow; the OTel listener (Epic 5 Story 5.1) is the primary caller.
    """
    bind_context(TestContext(test_id=test_id, suite_id=suite_id, scope=scope))


# --------------------------------------------------------------------------- #
# MCPLifecycleManager dataclasses (per Story 0.2 spike findings)              #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ServerSpec:
    """How to spawn an MCP server subprocess.

    Note on `env`: `frozen=True` does NOT freeze the dict; production uses
    `MappingProxyType` for true immutability (P2.15 review fix).

    Note on `startup_timeout_s`: caller-tracked, not enforced by `acquire()`
    (P2.4 — documented, not implemented). `MCPLifecycleManager.acquire`
    returns immediately after `subprocess.Popen`; MCP handshake is the
    caller's responsibility (Epic 3 Story 3.1's `mcp/transport.py`).
    """

    command: Sequence[str]
    marker: str  # embedded in argv tail so ps can identify leaks
    startup_timeout_s: float = 10.0
    shutdown_timeout_s: float = 2.0  # NFR-PERF-03d ceiling per architecture L709
    env: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def create(
        cls,
        command: Sequence[str],
        marker: str,
        *,
        startup_timeout_s: float = 10.0,
        shutdown_timeout_s: float = 2.0,
        env: dict[str, str] | None = None,
    ) -> ServerSpec:
        """Caller-ergonomic constructor that wraps `env` in `MappingProxyType`."""
        return cls(
            command=command,
            marker=marker,
            startup_timeout_s=startup_timeout_s,
            shutdown_timeout_s=shutdown_timeout_s,
            env=MappingProxyType(dict(env or {})),
        )


@dataclass
class ServerHandle:
    """Live MCP server subprocess. Returned by `MCPLifecycleManager.acquire()`."""

    handle_id: str
    spec: ServerSpec
    process: subprocess.Popen[bytes]
    spawned_at_unix: float
    test_id: str | None
    suite_id: str | None


@dataclass
class ReleaseResult:
    """Audit record for a single release_*/shutdown_all() call.

    Field notes (P2.2 + P-edge-6 review fixes):
        - `process_lifetime_ms` (NOT `startup_latency_ms`) — spawn-to-terminate-start,
          i.e., the entire lifetime of the process. There is NO startup probe.
        - `shutdown_latency_ms` — terminate_start → `Popen.wait()` returns. Includes
          both signal delivery and kernel reap. A future story may split into
          `terminate_to_signal_delivered_ms` + `signal_to_reaped_ms`.
    """

    handle_id: str
    pid: int
    spawned_at_unix: float
    released_at_unix: float
    process_lifetime_ms: float
    shutdown_latency_ms: float
    signaled_with: Literal["SIGTERM", "SIGKILL", "already-dead", "failed-EPERM"]
    killed_by_timeout: bool


# --------------------------------------------------------------------------- #
# Per-test/suite/process MCP server lifecycle manager                         #
# --------------------------------------------------------------------------- #


# Whitelist of env vars passed to child MCP server subprocesses.
# `os.environ.copy()` would leak credentials (LITELLM_*, ANTHROPIC_API_KEY, ...)
# to third-party MCP servers; the deferred-work review fix (L46) mandates a
# minimal whitelist instead. Callers add server-specific keys via `ServerSpec.env`.
_DEFAULT_ENV_WHITELIST: tuple[str, ...] = ("PATH", "HOME", "LANG", "LC_ALL")


class MCPLifecycleManager:
    """Per-pabot-worker lifecycle manager for MCP server subprocesses.

    Concurrency:
        Uses `threading.RLock` (NOT `Lock`) per P2.8 — the `atexit` failsafe
        can re-enter `shutdown_all()` while a `release_*` call is still
        holding the lock.

    SIGTERM-handler auto-installed (D2.4 LOAD-BEARING finding):
        Python's default SIGTERM handler does NOT run atexit. The handler
        installed by `__init__` converts SIGTERM → `sys.exit(0)`, which DOES
        run atexit, which runs `shutdown_all()`. Override via
        `install_sigterm_handler=False` if the caller manages signals itself
        (e.g., a parent framework that already has its own SIGTERM handler).

    atexit gaps (D2.2 known limitations):
        - SIGKILL of parent: atexit cannot run. Orphans reparent to init/systemd.
          Operator must teardown via systemd cgroup / container-level mitigation.
        - `os._exit()`: atexit not run.
        - SIGSTOP: process suspended; atexit only runs when later killed.

    Verified by Story 0.2 spike:
        - 45/45 smoke-matrix iters, zero leaks (Linux, all 3 scopes × 3 server types)
        - SIGTERM-during-MCP-handshake: clean (D2.3 probe, 5/5 iters)
        - SIGTERM + auto-handler: clean (D2.4 probe scenario A, 3/3 iters)
        - SIGTERM + no handler: leaks (D2.4 probe scenario B — proves handler is mandatory)
        - SIGKILL: leaks (D2.4 probe scenario C — unrecoverable; operator mitigation)
    """

    def __init__(
        self,
        scope: Scope,
        *,
        default_spec: ServerSpec | None = None,
        install_sigterm_handler: bool = True,
    ) -> None:
        self._scope: Scope = scope
        self._default_spec: ServerSpec | None = default_spec
        self._lock = threading.RLock()  # P2.8: RLock, not Lock
        self._handles: dict[str, ServerHandle] = {}
        self._handles_by_test: dict[str, list[str]] = {}
        self._handles_by_suite: dict[str, list[str]] = {}

        # P2.16 acknowledgement: atexit.unregister(self.shutdown_all) is the
        # caller's responsibility for long-lived processes (multiple manager
        # instantiations accumulate on the atexit stack).
        atexit.register(self.shutdown_all)

        if install_sigterm_handler:
            # D2.4 LOAD-BEARING: convert SIGTERM → sys.exit(0) so atexit fires.
            signal.signal(signal.SIGTERM, _sigterm_to_sysexit)

    # ---- public API ----------------------------------------------------- #

    def acquire(
        self,
        *,
        test_id: str,
        suite_id: str,
        spec: ServerSpec | None = None,
    ) -> ServerHandle:
        """Acquire a server handle per the configured scope.

        Returns immediately after `subprocess.Popen` — MCP handshake is the
        caller's responsibility (Epic 3 Story 3.1).

        Args:
            test_id: Listener v3 test identifier (used for "test" scope release).
            suite_id: Listener v3 suite identifier (used for "suite" scope release).
            spec: ServerSpec override; falls back to `self._default_spec` if None.

        Returns:
            Live ServerHandle.

        Raises:
            ValueError: If neither `spec` nor `self._default_spec` provides a spec (P2.14).
        """
        resolved_spec = spec or self._default_spec
        if resolved_spec is None:
            raise ValueError("acquire() requires either an explicit spec or a manager-level default_spec")

        child_env = self._build_minimized_env(resolved_spec.env)

        # P-edge: spawn OUTSIDE the lock so Popen doesn't serialize all acquires
        # behind one another, and so the child doesn't inherit the parent's
        # atexit state under lock.
        popen = subprocess.Popen(
            [*resolved_spec.command, resolved_spec.marker],
            start_new_session=True,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        handle = ServerHandle(
            handle_id=str(uuid.uuid4()),
            spec=resolved_spec,
            process=popen,
            spawned_at_unix=time.time(),
            test_id=test_id,
            suite_id=suite_id,
        )

        with self._lock:
            self._handles[handle.handle_id] = handle
            self._handles_by_test.setdefault(test_id, []).append(handle.handle_id)
            self._handles_by_suite.setdefault(suite_id, []).append(handle.handle_id)

        return handle

    def release_test(self, test_id: str) -> list[ReleaseResult]:
        """Release all handles bound to a test_id; return audit records."""
        with self._lock:
            handle_ids = self._handles_by_test.pop(test_id, [])
            handles = [self._handles.pop(h, None) for h in handle_ids]
            # Also remove from per-suite reverse index.
            for hid in handle_ids:
                for suite_ids in self._handles_by_suite.values():
                    if hid in suite_ids:
                        suite_ids.remove(hid)
        return [self._kill_and_record(h) for h in handles if h is not None]

    def release_suite(self, suite_id: str) -> list[ReleaseResult]:
        """Release all handles bound to a suite_id; return audit records."""
        with self._lock:
            handle_ids = self._handles_by_suite.pop(suite_id, [])
            handles = [self._handles.pop(h, None) for h in handle_ids]
            for hid in handle_ids:
                for test_ids in self._handles_by_test.values():
                    if hid in test_ids:
                        test_ids.remove(hid)
        return [self._kill_and_record(h) for h in handles if h is not None]

    def shutdown_all(self) -> list[ReleaseResult]:
        """Release every outstanding handle; return audit records.

        Called by the atexit failsafe; also safe to call directly.
        """
        with self._lock:
            handles = list(self._handles.values())
            self._handles.clear()
            self._handles_by_test.clear()
            self._handles_by_suite.clear()
        return [self._kill_and_record(h) for h in handles]

    # ---- internals ------------------------------------------------------ #

    @staticmethod
    def _build_minimized_env(spec_env: MappingProxyType[str, str]) -> dict[str, str]:
        """Build the child env: whitelist from os.environ + spec_env overlay.

        Mitigates the credential-leak risk from `os.environ.copy()` per
        deferred-work.md L46. The spec_env overlay lets callers add
        server-specific keys explicitly.
        """
        env: dict[str, str] = {}
        for key in _DEFAULT_ENV_WHITELIST:
            value = os.environ.get(key)
            if value is not None:
                env[key] = value
        env.update(dict(spec_env))
        return env

    def _kill_and_record(self, handle: ServerHandle) -> ReleaseResult:
        """Terminate a single handle's process; emit a ReleaseResult.

        Always emits a ReleaseResult (P-edge: dead-and-replaced handles don't
        drop silently). EPERM vs ESRCH distinguished. SIGTERM → SIGKILL
        escalation on shutdown_timeout_s. Post-kill liveness verified.
        """
        terminate_start = time.monotonic()
        spawned_at_unix = handle.spawned_at_unix
        pid = handle.process.pid

        if handle.process.poll() is not None:
            # Already dead — emit ReleaseResult and return.
            released_at_unix = time.time()
            return ReleaseResult(
                handle_id=handle.handle_id,
                pid=pid,
                spawned_at_unix=spawned_at_unix,
                released_at_unix=released_at_unix,
                process_lifetime_ms=(terminate_start - spawned_at_unix) * 1000.0,
                shutdown_latency_ms=0.0,
                signaled_with="already-dead",
                killed_by_timeout=False,
            )

        signaled_with: Literal["SIGTERM", "SIGKILL", "already-dead", "failed-EPERM"]
        killed_by_timeout = False

        try:
            # P-edge: use `pid` directly as pgid since start_new_session=True
            # makes pid == pgid. Avoids the os.getpgid race.
            os.killpg(pid, signal.SIGTERM)
            signaled_with = "SIGTERM"
        except ProcessLookupError:
            # ESRCH — process already gone between poll() and killpg.
            released_at_unix = time.time()
            return ReleaseResult(
                handle_id=handle.handle_id,
                pid=pid,
                spawned_at_unix=spawned_at_unix,
                released_at_unix=released_at_unix,
                process_lifetime_ms=(terminate_start - spawned_at_unix) * 1000.0,
                shutdown_latency_ms=(time.monotonic() - terminate_start) * 1000.0,
                signaled_with="already-dead",
                killed_by_timeout=False,
            )
        except PermissionError as exc:
            # P-edge: distinguish EPERM from ESRCH. EPERM means we can't signal
            # the process group — do NOT report as success.
            if exc.errno == errno.EPERM:
                released_at_unix = time.time()
                return ReleaseResult(
                    handle_id=handle.handle_id,
                    pid=pid,
                    spawned_at_unix=spawned_at_unix,
                    released_at_unix=released_at_unix,
                    process_lifetime_ms=(terminate_start - spawned_at_unix) * 1000.0,
                    shutdown_latency_ms=(time.monotonic() - terminate_start) * 1000.0,
                    signaled_with="failed-EPERM",
                    killed_by_timeout=False,
                )
            raise

        # Wait for graceful exit; escalate to SIGKILL on timeout.
        try:
            handle.process.wait(timeout=handle.spec.shutdown_timeout_s)
        except subprocess.TimeoutExpired:
            # Race-safe SIGKILL: process may have died between SIGTERM timeout
            # and SIGKILL attempt — treat ProcessLookupError/PermissionError as
            # "already gone" (subsequent wait() will confirm).
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGKILL)
            signaled_with = "SIGKILL"
            killed_by_timeout = True
            handle.process.wait()

        # Post-kill liveness verification (deferred-work fix). D-state survivors
        # would still have poll() == None; we treat that as a runtime error.
        if handle.process.poll() is None:
            raise RuntimeError(
                f"MCP server pid={pid} survived shutdown signal {signaled_with} "
                "(possible D-state hang); operator intervention required."
            )

        released_at_unix = time.time()
        return ReleaseResult(
            handle_id=handle.handle_id,
            pid=pid,
            spawned_at_unix=spawned_at_unix,
            released_at_unix=released_at_unix,
            process_lifetime_ms=(terminate_start - spawned_at_unix) * 1000.0,
            shutdown_latency_ms=(time.monotonic() - terminate_start) * 1000.0,
            signaled_with=signaled_with,
            killed_by_timeout=killed_by_timeout,
        )


def _sigterm_to_sysexit(signum: int, frame: FrameType | None) -> None:  # noqa: ARG001
    """SIGTERM handler that converts the signal into `sys.exit(0)`.

    This is the D2.4 LOAD-BEARING shim: Python's default SIGTERM handler does
    NOT run atexit; `sys.exit(0)` does. The lifecycle manager's atexit
    failsafe then cleans up any outstanding handles.
    """
    sys.exit(0)


# --------------------------------------------------------------------------- #
# FR41 config precedence (kwarg → env-var → .env → defaults)                  #
# --------------------------------------------------------------------------- #


# PRD FR42 + FR11b defaults — the floor of the precedence chain.
# Order matches `AgentEval.__init__` parameter order for the
# `Get Effective Config` keyword's dict-return ordering.
_FR42_DEFAULTS: dict[str, Any] = {
    "provider": "litellm",
    "telemetry": True,
    "trace_backend": "memory",
    "allow_validate_operator": False,
    "default_temperature": 0.0,
    "mcp_per_test": True,
    "allow_external_mcp_blind": False,
    "max_cost_usd": 5.00,
    "max_runtime_seconds": None,
}

# Mapping from FR42 + FR11b kwarg names to `AGENTEVAL_*` env-var names per
# architecture.md §Configuration Parameter Naming + `.env.example`.
_ENV_VAR_NAMES: dict[str, str] = {
    "provider": "AGENTEVAL_PROVIDER",
    "telemetry": "AGENTEVAL_TELEMETRY",
    "trace_backend": "AGENTEVAL_TRACE_BACKEND",
    "allow_validate_operator": "AGENTEVAL_ALLOW_VALIDATE_OPERATOR",
    "default_temperature": "AGENTEVAL_DEFAULT_TEMPERATURE",
    "mcp_per_test": "AGENTEVAL_MCP_PER_TEST",
    "allow_external_mcp_blind": "AGENTEVAL_ALLOW_EXTERNAL_MCP_BLIND",
    "max_cost_usd": "AGENTEVAL_MAX_COST_USD",
    "max_runtime_seconds": "AGENTEVAL_MAX_RUNTIME_SECONDS",
}


def _parse_bool(raw: str, *, key: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in ("true", "1", "yes", "on"):
        return True
    if lowered in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"{key}: expected bool-like value (true/false/1/0/yes/no/on/off); got {raw!r}")


def _parse_mcp_per_test(raw: str, *, key: str) -> bool | Literal["suite"]:
    lowered = raw.strip().lower()
    if lowered == "suite":
        return "suite"
    return _parse_bool(raw, key=key)


def _parse_optional_float(raw: str, *, key: str) -> float | None:
    stripped = raw.strip()
    if stripped == "":
        return None
    try:
        return float(stripped)
    except ValueError as exc:
        raise ValueError(f"{key}: expected float or empty string; got {raw!r}") from exc


def _coerce_env_value(key: str, raw: str) -> Any:
    """Coerce an env-var string to the target type for the given config key."""
    if key in ("telemetry", "allow_validate_operator", "allow_external_mcp_blind"):
        return _parse_bool(raw, key=key)
    if key == "mcp_per_test":
        return _parse_mcp_per_test(raw, key=key)
    if key == "default_temperature":
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"{key}: expected float; got {raw!r}") from exc
    if key == "max_cost_usd":
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"{key}: expected float; got {raw!r}") from exc
    if key == "max_runtime_seconds":
        return _parse_optional_float(raw, key=key)
    # provider, trace_backend — strings; pass through.
    return raw


def _load_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    """Minimal `.env` parser (no third-party dependency for Phase-1).

    Reads `KEY=VALUE` lines; skips blank lines and `#` comments. Returns a
    `dict` mapping AGENTEVAL_* keys → raw string values. Missing file returns
    an empty dict.
    """
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip()
    return result


def resolve_config(
    kwarg_overrides: dict[str, Any],
    *,
    dotenv_path: Path = Path(".env"),
) -> dict[str, Any]:
    """Resolve the AgentEval Library kwargs against the FR41 precedence chain.

    Precedence (highest wins):
        kwarg_overrides > os.environ["AGENTEVAL_*"] > .env file > FR42 defaults

    Args:
        kwarg_overrides: User-supplied kwargs passed to `AgentEval.__init__`.
            Only non-None values count as overrides; None falls through to
            lower precedence layers.
        dotenv_path: Path to the `.env` file. Defaults to `.env` in cwd.

    Returns:
        Dict with all 9 FR42 + FR11b keys, in declared order, with values
        coerced to their target types.

    Raises:
        ValueError: If an env-var or `.env` value fails type coercion.

    Notes on the `mcp_per_test` translation:
        The user-vocab value (True / False / "suite") is returned as-is.
        Internal Scope translation via `_resolve_scope()` happens at the
        consumer boundary (e.g., `AgentEval.__init__` calls it for
        `self._scope`).
    """
    dotenv_values = _load_dotenv(dotenv_path)
    resolved: dict[str, Any] = {}

    for key, default_value in _FR42_DEFAULTS.items():
        # Layer 1 — kwarg override (only if explicitly non-None; None means
        # "fall through" so consumers can opt into env-var resolution).
        if key in kwarg_overrides and kwarg_overrides[key] is not None:
            resolved[key] = kwarg_overrides[key]
            continue
        # Layer 2 — environment variable.
        env_name = _ENV_VAR_NAMES[key]
        env_raw = os.environ.get(env_name)
        if env_raw is not None:
            resolved[key] = _coerce_env_value(key, env_raw)
            continue
        # Layer 3 — .env file.
        if env_name in dotenv_values:
            resolved[key] = _coerce_env_value(key, dotenv_values[env_name])
            continue
        # Layer 4 — FR42 default.
        resolved[key] = default_value

    return resolved
