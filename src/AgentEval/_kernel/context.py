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
   patches (P2.1-P2.18) + the P2.19 scope-aware idempotent acquire + the D2.4
   auto-installed SIGTERM handler integrated.
4. **atexit + auto-installed SIGTERM handler** — defense-in-depth cleanup so
   leaks don't accumulate when a pabot worker terminates. Python's default
   SIGTERM handler does NOT run atexit (D2.4 LOAD-BEARING finding); the
   handler installed here converts SIGTERM into `sys.exit(0)`, which does.
   `signal.signal()` install is guarded to the main thread (per Python's
   thread-safety contract); `close()` restores the prior handler + atexit
   registration on instance disposal.
5. **FR41 config precedence** — `resolve_config()` resolves the AgentEval
   Library kwargs against the precedence chain `kwarg > env-var > .env > defaults`.
   Story 1a.6's `__init__.py` integrates with this for `Get Effective Config`.
   Explicit `None` kwargs DO win over env-vars (FR41 invariant — "kwarg wins"
   has no `None` carve-out); only kwargs absent from the dict fall through.

Scope semantics (Story 0.2 spike §_kernel/context.py draft + P2.19):
    - `Scope = "test"`: one MCP server per test_id; per-test isolation; correct
      under `pabot --processes N`. Idempotent `acquire(test_id=X, ...)` returns
      the existing live handle when X has already-acquired; dead handles are
      reaped + replaced.
    - `Scope = "suite"`: one MCP server per suite_id, reused across tests in the
      same suite. `release_test()` is a no-op; `release_suite()` releases.
      Recipe-5 dogfood-CI ergonomics override per architecture L410.
    - `Scope = "process"`: single shared MCP server across all tests in the
      pabot worker. Both `release_test()` and `release_suite()` are no-ops;
      only `shutdown_all()` (or `close()`) releases.

Lifecycle guarantees (verified by Story 0.2 spike):
    - 45/45 smoke-matrix iters, zero leaks (Linux, mcp 1.27.1, RF 7.4.2, pabot 5.2.2)
    - SIGTERM-during-MCP-handshake: clean release (D2.3 probe, 5/5 iters)
    - SIGTERM-of-parent + auto-installed handler: clean release (D2.4 probe, 3/3 iters)
    - SIGKILL-of-parent: UNRECOVERABLE at listener layer (D2.4 probe scenario C).
      Operator must teardown via systemd cgroup / container-level mitigation.

Citation index for code-review re-derivation (per `feedback_citation_drift_first_class`):
    - architecture L314 / L410 / L1659 — user `mcp_per_test` 3-mode vocabulary
    - architecture L620 — `_agenteval_tier` single-underscore attribute convention (cited in tier.py)
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
import warnings
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
    "resolve_config_with_provenance",
    "ConfigValue",
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
    `MappingProxyType` for true immutability (P2.15 review fix). `__post_init__`
    defensively re-wraps to seal against direct-constructor leakage.

    Note on `startup_timeout_s`: caller-tracked, not enforced by `acquire()`
    (P2.4 — documented, not implemented). `MCPLifecycleManager.acquire`
    returns immediately after `subprocess.Popen`; MCP handshake is the
    caller's responsibility (Epic 3 Story 3.1's `mcp/transport.py`).

    Note on `shutdown_timeout_s`: MUST be > 0 (validated in `__post_init__`).
    `Popen.wait(timeout=0)` raises `TimeoutExpired` immediately, so a zero or
    negative value would skip the graceful SIGTERM grace period and always
    escalate to SIGKILL.
    """

    command: Sequence[str]
    marker: str  # embedded in argv tail so ps can identify leaks
    startup_timeout_s: float = 10.0
    shutdown_timeout_s: float = 2.0  # NFR-PERF-03d ceiling per architecture L709
    env: MappingProxyType[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        # M6: guard shutdown_timeout_s > 0; zero/negative would skip graceful wait.
        if self.shutdown_timeout_s <= 0:
            raise ValueError(
                f"shutdown_timeout_s must be > 0 (got {self.shutdown_timeout_s!r}); "
                "zero/negative would skip the graceful SIGTERM grace period"
            )
        # L5: defensively re-wrap env so direct-constructor `ServerSpec(env=MappingProxyType(d))`
        # can't be mutated through the source dict after construction. `object.__setattr__`
        # is necessary because dataclass is frozen=True.
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))

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
    """Live MCP server subprocess. Returned by `MCPLifecycleManager.acquire()`.

    Field notes:
        - `spawned_at_unix` (wall-clock): used for `released_at_unix` audit math.
        - `spawned_at_monotonic` (monotonic): used for `process_lifetime_ms`
          computation. Mixing `time.time()` with `time.monotonic()` produces
          garbage values (H2 review finding); always pair the two clocks
          deliberately.
    """

    handle_id: str
    spec: ServerSpec
    process: subprocess.Popen[bytes]
    spawned_at_unix: float
    spawned_at_monotonic: float
    test_id: str | None
    suite_id: str | None


@dataclass
class ReleaseResult:
    """Audit record for a single release_*/shutdown_all() call.

    Field notes (P2.2 + P-edge-6 review fixes):
        - `process_lifetime_ms` (NOT `startup_latency_ms`) — spawn-to-terminate-start,
          measured in the monotonic clock domain. There is NO startup probe.
        - `shutdown_latency_ms` — terminate_start → `Popen.wait()` returns. Includes
          both signal delivery and kernel reap. A future story may split into
          `terminate_to_signal_delivered_ms` + `signal_to_reaped_ms`.
        - `signaled_with="survived"` — H7: a D-state hang or otherwise stuck
          process that did not respond to SIGTERM + SIGKILL escalation. The
          atexit failsafe records this and continues with remaining handles
          rather than raising mid-loop.
    """

    handle_id: str
    pid: int
    spawned_at_unix: float
    released_at_unix: float
    process_lifetime_ms: float
    shutdown_latency_ms: float
    signaled_with: Literal["SIGTERM", "SIGKILL", "already-dead", "failed-EPERM", "survived"]
    killed_by_timeout: bool


# --------------------------------------------------------------------------- #
# Per-test/suite/process MCP server lifecycle manager                         #
# --------------------------------------------------------------------------- #


# Whitelist of env vars passed to child MCP server subprocesses.
# `os.environ.copy()` would leak credentials (LITELLM_*, ANTHROPIC_API_KEY, ...)
# to third-party MCP servers; the deferred-work review fix (L46) mandates a
# minimal whitelist instead. Callers add server-specific keys via `ServerSpec.env`.
_DEFAULT_ENV_WHITELIST: tuple[str, ...] = ("PATH", "HOME", "LANG", "LC_ALL")

# Sentinel scope key for "process"-mode handle storage. The single shared
# handle is keyed under this constant in `_handles_by_test` + `_handles_by_suite`.
_PROCESS_SCOPE_KEY = "__process_scope__"


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
        `install_sigterm_handler=False` if the caller manages signals itself.
        Install is guarded to the main thread (Python `signal.signal` raises
        `ValueError` from non-main threads); from worker threads, the manager
        warns + skips the install, relying on atexit alone.

    Lifecycle management:
        `close()` unregisters the atexit hook + restores the prior SIGTERM
        handler. Long-lived processes that instantiate multiple managers MUST
        call `close()` on disposal to prevent atexit-stack accumulation +
        SIGTERM-handler clobbering.

    Scope semantics (P2.19 idempotent acquire):
        - "test": acquire idempotent per test_id; release_test releases; release_suite no-op
        - "suite": acquire idempotent per suite_id; release_test no-op; release_suite releases
        - "process": single shared handle; release_test + release_suite both no-op; only
          shutdown_all/close releases

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
        self._closed = False

        # Capture prior SIGTERM handler so close() can restore it (M2 fix).
        self._prior_sigterm_handler: Any = None

        # Register atexit failsafe. close() unregisters; instance disposal without
        # close() leaves a stale callable on the atexit stack (manager is dead but
        # the callable points at it — still safe because shutdown_all on empty state
        # is a no-op).
        atexit.register(self.shutdown_all)

        if install_sigterm_handler:
            # H4: signal.signal() raises ValueError from non-main threads. Guard +
            # warn so embedded-framework callers don't crash.
            if threading.current_thread() is threading.main_thread():
                self._prior_sigterm_handler = signal.getsignal(signal.SIGTERM)
                # D2.4 LOAD-BEARING: convert SIGTERM → sys.exit(0) so atexit fires.
                signal.signal(signal.SIGTERM, _sigterm_to_sysexit)
            else:
                warnings.warn(
                    "MCPLifecycleManager: skipping SIGTERM auto-install (not on main thread); "
                    "atexit failsafe will still fire on normal exit",
                    UserWarning,
                    stacklevel=2,
                )

    # ---- public API ----------------------------------------------------- #

    def close(self) -> list[ReleaseResult]:
        """Release all handles, unregister atexit, restore prior SIGTERM handler.

        Long-lived processes that instantiate multiple managers MUST call this
        on disposal to prevent atexit-stack accumulation + SIGTERM-handler
        clobbering (M2 fix). Safe to call multiple times.
        """
        if self._closed:
            return []
        results = self.shutdown_all()
        with contextlib.suppress(Exception):
            atexit.unregister(self.shutdown_all)
        if self._prior_sigterm_handler is not None and threading.current_thread() is threading.main_thread():
            with contextlib.suppress(Exception):
                signal.signal(signal.SIGTERM, self._prior_sigterm_handler)
        self._closed = True
        return results

    def acquire(
        self,
        *,
        test_id: str,
        suite_id: str,
        spec: ServerSpec | None = None,
    ) -> ServerHandle:
        """Acquire a server handle per the configured scope (P2.19 idempotent).

        Scope-dependent reuse semantics:
            - "test": one handle per test_id. Idempotent — repeat acquire with same
              test_id returns the live handle (or reaps dead one + replaces).
            - "suite": one handle per suite_id. Idempotent — repeat acquire with same
              suite_id returns the live handle.
            - "process": one handle total. Idempotent — repeat acquire always returns
              the live handle.

        Returns immediately after `subprocess.Popen` — MCP handshake is the
        caller's responsibility (Epic 3 Story 3.1).

        Args:
            test_id: Listener v3 test identifier.
            suite_id: Listener v3 suite identifier.
            spec: ServerSpec override; falls back to `self._default_spec` if None.

        Returns:
            Live ServerHandle.

        Raises:
            ValueError: If neither `spec` nor `self._default_spec` provides a spec (P2.14).
        """
        resolved_spec = spec or self._default_spec
        if resolved_spec is None:
            raise ValueError("acquire() requires either an explicit spec or a manager-level default_spec")

        # P2.19 idempotent acquire: scope-aware lookup, reuse live or reap-and-replace dead.
        with self._lock:
            existing = self._lookup_existing(test_id, suite_id)
            if existing is not None:
                if existing.process.poll() is None:
                    # Alive — return existing handle (idempotent).
                    return existing
                # Dead — record the kill, fall through to spawn replacement.
                with contextlib.suppress(Exception):
                    self._kill_and_record(existing)
                self._evict_handle(existing.handle_id)

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
        # H2: capture BOTH wall-clock + monotonic at spawn so process_lifetime_ms
        # is computed from a consistent monotonic pair.
        handle = ServerHandle(
            handle_id=str(uuid.uuid4()),
            spec=resolved_spec,
            process=popen,
            spawned_at_unix=time.time(),
            spawned_at_monotonic=time.monotonic(),
            test_id=test_id,
            suite_id=suite_id,
        )

        with self._lock:
            self._register_handle(handle, test_id, suite_id)

        return handle

    def release_test(self, test_id: str) -> list[ReleaseResult]:
        """Release handles bound to a test_id; no-op outside `"test"` scope.

        Per spike findings §`_kernel/context.py` draft scope semantics: only
        `"test"` scope releases on per-test boundary. `"suite"` reuses across
        tests in the suite; `"process"` reuses across the worker process.
        """
        if self._scope != "test":
            return []
        with self._lock:
            handle_ids = self._handles_by_test.pop(test_id, [])
            handles = [self._handles.pop(h, None) for h in handle_ids]
            # M9: O(1) reverse-index cleanup via ServerHandle.suite_id, no full scan.
            for h in handles:
                if h is not None and h.suite_id is not None:
                    suite_list = self._handles_by_suite.get(h.suite_id, [])
                    if h.handle_id in suite_list:
                        suite_list.remove(h.handle_id)
                    if not suite_list and h.suite_id in self._handles_by_suite:
                        del self._handles_by_suite[h.suite_id]
        return self._drain_handles(handles)

    def release_suite(self, suite_id: str) -> list[ReleaseResult]:
        """Release handles bound to a suite_id; no-op in `"process"` scope.

        In `"test"` scope, called when a suite ends to clean up any per-test
        handles still bound to that suite (defensive). In `"suite"` scope,
        this is the primary release path. In `"process"` scope, no-op.
        """
        if self._scope == "process":
            return []
        with self._lock:
            handle_ids = self._handles_by_suite.pop(suite_id, [])
            handles = [self._handles.pop(h, None) for h in handle_ids]
            # M9: O(1) reverse-index cleanup via ServerHandle.test_id.
            for h in handles:
                if h is not None and h.test_id is not None:
                    test_list = self._handles_by_test.get(h.test_id, [])
                    if h.handle_id in test_list:
                        test_list.remove(h.handle_id)
                    if not test_list and h.test_id in self._handles_by_test:
                        del self._handles_by_test[h.test_id]
        return self._drain_handles(handles)

    def shutdown_all(self) -> list[ReleaseResult]:
        """Release every outstanding handle; return audit records.

        Called by the atexit failsafe; also safe to call directly. H7: per-handle
        errors are absorbed into ReleaseResult so a single stuck process doesn't
        abandon the rest mid-loop.
        """
        with self._lock:
            handles: list[ServerHandle | None] = list(self._handles.values())
            self._handles.clear()
            self._handles_by_test.clear()
            self._handles_by_suite.clear()
        return self._drain_handles(handles)

    # ---- internals ------------------------------------------------------ #

    def _lookup_existing(self, test_id: str, suite_id: str) -> ServerHandle | None:
        """Scope-aware lookup of an existing handle for the given test/suite_id.

        - "test": match by test_id
        - "suite": match by suite_id
        - "process": single shared handle keyed under _PROCESS_SCOPE_KEY
        """
        if self._scope == "test":
            hids = self._handles_by_test.get(test_id, [])
        elif self._scope == "suite":
            hids = self._handles_by_suite.get(suite_id, [])
        else:  # process
            hids = self._handles_by_test.get(_PROCESS_SCOPE_KEY, [])
        if hids:
            return self._handles.get(hids[0])
        return None

    def _register_handle(self, handle: ServerHandle, test_id: str, suite_id: str) -> None:
        """Index a newly-spawned handle in the scope-appropriate maps."""
        self._handles[handle.handle_id] = handle
        if self._scope == "process":
            # Single-shared-handle case — index under sentinel keys so lookup is O(1).
            self._handles_by_test.setdefault(_PROCESS_SCOPE_KEY, []).append(handle.handle_id)
            self._handles_by_suite.setdefault(_PROCESS_SCOPE_KEY, []).append(handle.handle_id)
        else:
            self._handles_by_test.setdefault(test_id, []).append(handle.handle_id)
            self._handles_by_suite.setdefault(suite_id, []).append(handle.handle_id)

    def _evict_handle(self, handle_id: str) -> None:
        """Remove a handle from all indexes. Used by the dead-handle replace path."""
        handle = self._handles.pop(handle_id, None)
        if handle is None:
            return
        for index in (self._handles_by_test, self._handles_by_suite):
            for key, hids in list(index.items()):
                if handle_id in hids:
                    hids.remove(handle_id)
                    if not hids:
                        del index[key]

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

    def _drain_handles(self, handles: list[ServerHandle | None]) -> list[ReleaseResult]:
        """Kill+record each handle, absorbing per-handle errors into ReleaseResult.

        H7: a stuck process (D-state, EPERM, etc.) MUST NOT abort the loop —
        defense-in-depth shutdown_all() should reap as many handles as
        possible. Errors that don't fit the documented ReleaseResult literals
        are recorded as `signaled_with="survived"`.
        """
        results: list[ReleaseResult] = []
        for h in handles:
            if h is None:
                continue
            try:
                results.append(self._kill_and_record(h))
            except Exception as exc:  # noqa: BLE001 — defense-in-depth: log + continue
                warnings.warn(
                    f"MCPLifecycleManager: unexpected error reaping pid={h.process.pid}: {exc!r}",
                    UserWarning,
                    stacklevel=2,
                )
                released_at_unix = time.time()
                terminate_start_monotonic = time.monotonic()
                results.append(
                    ReleaseResult(
                        handle_id=h.handle_id,
                        pid=h.process.pid,
                        spawned_at_unix=h.spawned_at_unix,
                        released_at_unix=released_at_unix,
                        process_lifetime_ms=(terminate_start_monotonic - h.spawned_at_monotonic) * 1000.0,
                        shutdown_latency_ms=0.0,
                        signaled_with="survived",
                        killed_by_timeout=False,
                    )
                )
        return results

    def _kill_and_record(self, handle: ServerHandle) -> ReleaseResult:
        """Terminate a single handle's process; emit a ReleaseResult.

        Always emits a ReleaseResult (P-edge: dead-and-replaced handles don't
        drop silently). EPERM vs ESRCH distinguished. SIGTERM → SIGKILL
        escalation on shutdown_timeout_s. Post-kill liveness verified.

        M1: PID-race-safe — calls `Popen.wait(timeout=0)` to reap before
        signaling, so we never `os.killpg()` against a recycled PID.

        H7: survived processes are recorded as ReleaseResult("survived") and
        bubbled up via `_drain_handles`; do NOT raise RuntimeError from this
        method (would abandon remaining handles in atexit context).
        """
        terminate_start_monotonic = time.monotonic()
        spawned_at_monotonic = handle.spawned_at_monotonic
        spawned_at_unix = handle.spawned_at_unix
        pid = handle.process.pid

        # M1: reap-first to close the poll() → killpg() race window. If the
        # process has already exited but Popen hasn't been notified, wait(0)
        # reaps the zombie and marks returncode; subsequent killpg won't
        # signal a recycled PID.
        with contextlib.suppress(subprocess.TimeoutExpired):
            handle.process.wait(timeout=0)

        if handle.process.poll() is not None:
            # Already dead — emit ReleaseResult and return.
            released_at_unix = time.time()
            return ReleaseResult(
                handle_id=handle.handle_id,
                pid=pid,
                spawned_at_unix=spawned_at_unix,
                released_at_unix=released_at_unix,
                # H2: monotonic-only subtraction.
                process_lifetime_ms=(terminate_start_monotonic - spawned_at_monotonic) * 1000.0,
                shutdown_latency_ms=0.0,
                signaled_with="already-dead",
                killed_by_timeout=False,
            )

        signaled_with: Literal["SIGTERM", "SIGKILL", "already-dead", "failed-EPERM", "survived"]
        killed_by_timeout = False

        try:
            # P-edge: use `pid` directly as pgid since start_new_session=True
            # makes pid == pgid. Avoids the os.getpgid race.
            os.killpg(pid, signal.SIGTERM)
            signaled_with = "SIGTERM"
        except ProcessLookupError:
            # ESRCH — process already gone between reap-attempt and killpg.
            released_at_unix = time.time()
            return ReleaseResult(
                handle_id=handle.handle_id,
                pid=pid,
                spawned_at_unix=spawned_at_unix,
                released_at_unix=released_at_unix,
                process_lifetime_ms=(terminate_start_monotonic - spawned_at_monotonic) * 1000.0,
                shutdown_latency_ms=(time.monotonic() - terminate_start_monotonic) * 1000.0,
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
                    process_lifetime_ms=(terminate_start_monotonic - spawned_at_monotonic) * 1000.0,
                    shutdown_latency_ms=(time.monotonic() - terminate_start_monotonic) * 1000.0,
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
        # would still have poll() == None — record as "survived" + return (do NOT
        # raise; _drain_handles needs to continue with remaining handles in
        # atexit context per H7).
        # TODO(Story 1b.5): once _kernel/errors.py lands, emit a typed
        # MCPShutdownFailed warning alongside the ReleaseResult.
        if handle.process.poll() is None:
            released_at_unix = time.time()
            return ReleaseResult(
                handle_id=handle.handle_id,
                pid=pid,
                spawned_at_unix=spawned_at_unix,
                released_at_unix=released_at_unix,
                process_lifetime_ms=(terminate_start_monotonic - spawned_at_monotonic) * 1000.0,
                shutdown_latency_ms=(time.monotonic() - terminate_start_monotonic) * 1000.0,
                signaled_with="survived",
                killed_by_timeout=killed_by_timeout,
            )

        released_at_unix = time.time()
        return ReleaseResult(
            handle_id=handle.handle_id,
            pid=pid,
            spawned_at_unix=spawned_at_unix,
            released_at_unix=released_at_unix,
            process_lifetime_ms=(terminate_start_monotonic - spawned_at_monotonic) * 1000.0,
            shutdown_latency_ms=(time.monotonic() - terminate_start_monotonic) * 1000.0,
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

# Reverse map for M8 unknown-env-var warning.
_KNOWN_ENV_VAR_NAMES: frozenset[str] = frozenset(_ENV_VAR_NAMES.values())


def _parse_bool(raw: str, *, key: str) -> bool:
    """Parse a string to bool. Accepts true/false/1/0/yes/no/on/off (case-insensitive).

    Documented in `.env.example` per L4 review finding.
    """
    lowered = raw.strip().lower()
    if lowered in ("true", "1", "yes", "on"):
        return True
    if lowered in ("false", "0", "no", "off"):
        return False
    # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
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
        # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
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
            # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
            raise ValueError(f"{key}: expected float; got {raw!r}") from exc
    if key == "max_cost_usd":
        try:
            return float(raw)
        except ValueError as exc:
            # TODO(Story 1b.5): once _kernel/errors.py lands, raise ConfigParseError.
            raise ValueError(f"{key}: expected float; got {raw!r}") from exc
    if key == "max_runtime_seconds":
        return _parse_optional_float(raw, key=key)
    # provider, trace_backend — strings; pass through.
    return raw


def _strip_dotenv_value(value: str) -> str:
    """Strip surrounding matching quotes from a .env value (M7 review fix)."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _load_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    """Minimal `.env` parser (no third-party dependency for Phase-1).

    Reads `KEY=VALUE` lines; skips blank lines and `#` comments. Returns a
    `dict` mapping AGENTEVAL_* keys → raw string values. Missing file returns
    an empty dict.

    M7 review fixes:
        - Optional `export ` prefix is stripped from the key (common in
          shell-sourced .env files).
        - Surrounding matching quotes (`"..."` or `'...'`) are stripped from
          the value (standard dotenv convention).
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
        key = key.strip()
        # M7: handle `export KEY=VALUE` shell-sourcing convention.
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = _strip_dotenv_value(value.strip())
        result[key] = value
    return result


@dataclass(frozen=True)
class ConfigValue:
    """Story 4.3 / PRD FR41: per-setting resolved value + provenance.

    Returned by `resolve_config_with_provenance()` + the AgentEval
    Library's `Get Effective Config setting=<key>` / `Get Effective
    Config With Provenance` keywords. The `source` field names which
    precedence-chain level "won" for that setting per PRD FR41 L1563
    enum: `init_arg` / `env` / `dotenv` / `default`.
    """

    value: Any
    source: Literal["init_arg", "env", "dotenv", "default"]


def resolve_config_with_provenance(
    kwarg_overrides: dict[str, Any],
    *,
    dotenv_path: Path = Path(".env"),
) -> dict[str, ConfigValue]:
    """Story 4.3 / PRD FR41: resolve config + track per-setting source.

    Same precedence chain as `resolve_config()`; returns `ConfigValue`
    instead of bare value so consumers can audit which level "won"
    for each setting (debugging "why isn't my .env value applied?").
    """
    dotenv_values = _load_dotenv(dotenv_path)
    _warn_on_unknown_agenteval_keys(dotenv_values, source=str(dotenv_path))
    _warn_on_unknown_agenteval_keys(os.environ, source="os.environ")
    resolved: dict[str, ConfigValue] = {}

    for key, default_value in _FR42_DEFAULTS.items():
        if key in kwarg_overrides:
            resolved[key] = ConfigValue(value=kwarg_overrides[key], source="init_arg")
            continue
        env_name = _ENV_VAR_NAMES[key]
        env_raw = os.environ.get(env_name)
        if env_raw is not None:
            resolved[key] = ConfigValue(value=_coerce_env_value(key, env_raw), source="env")
            continue
        if env_name in dotenv_values:
            resolved[key] = ConfigValue(value=_coerce_env_value(key, dotenv_values[env_name]), source="dotenv")
            continue
        resolved[key] = ConfigValue(value=default_value, source="default")

    return resolved


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
            **Key presence — not non-None-ness — signals "user passed this kwarg"**
            (H3 review fix). Callers wishing to fall through to env-var resolution
            must omit the key entirely from this dict (e.g., by stripping
            `_UNSET` sentinels at `__init__` time).
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

    Notes on unknown env-vars (M8 review fix):
        Any `AGENTEVAL_*` key in the .env file (or `os.environ`) that is NOT
        in `_ENV_VAR_NAMES.values()` is flagged via `warnings.warn` with
        `UserWarning` so typos like `AGENTEVAL_PROVDER` surface visibly
        instead of silently falling back to defaults.
    """
    dotenv_values = _load_dotenv(dotenv_path)
    _warn_on_unknown_agenteval_keys(dotenv_values, source=str(dotenv_path))
    _warn_on_unknown_agenteval_keys(os.environ, source="os.environ")
    resolved: dict[str, Any] = {}

    for key, default_value in _FR42_DEFAULTS.items():
        # Layer 1 — kwarg override. H3: presence in the dict is the override
        # signal; explicit None IS a real user value (e.g., max_runtime_seconds=None
        # disables a wall-clock cap). Callers strip _UNSET sentinels before
        # passing; absence from this dict means "not passed".
        if key in kwarg_overrides:
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


def _warn_on_unknown_agenteval_keys(env_like: Any, *, source: str) -> None:
    """Emit UserWarning for any AGENTEVAL_* key not in the known set (M8)."""
    for k in env_like:
        if k.startswith("AGENTEVAL_") and k not in _KNOWN_ENV_VAR_NAMES:
            warnings.warn(
                f"Unknown agenteval env-var {k!r} in {source}; ignored. Known: {sorted(_KNOWN_ENV_VAR_NAMES)}.",
                UserWarning,
                stacklevel=3,
            )
