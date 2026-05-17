"""Per-test MCP cleanup primitive — Story 0.2 spike prototype.

THIS IS SCRATCH CODE. Discarded after Story 0.3 ratifies ADR-A6 + ADR-A8.
Epic 1b Story 1b.1 implements the production version at `src/AgentEval/_kernel/context.py`
using the API surface drafted here.

Lifecycle model:
    scope="test"    — one MCP server subprocess per RF test; spawned on start_test,
                      terminated on end_test (Listener v3) or atexit (fallback if
                      end_test does not fire, e.g. test timeout per architecture.md L710).
    scope="suite"   — one MCP server subprocess per RF suite; spawned on the FIRST
                      start_test of the suite, terminated on end_suite (or atexit).
    scope="process" — one MCP server subprocess per pabot worker process; spawned
                      lazily on the first start_test, terminated on close (or atexit).

Architect-facing API surface (load-bearing for Story 1b.1):
    class ServerSpec(BaseModel):
        command: Sequence[str]
        marker: str
        startup_timeout_s: float = 10.0
        shutdown_timeout_s: float = 2.0  # NFR-PERF-03d / architecture.md L709

    class MCPLifecycleManager:
        def __init__(self, scope: Scope, *, default_spec: ServerSpec | None = None) -> None: ...
        def acquire(self, *, test_id: str, suite_id: str, spec: ServerSpec | None = None) -> ServerHandle: ...
        def release_test(self, test_id: str) -> ReleaseResult: ...
        def release_suite(self, suite_id: str) -> ReleaseResult: ...
        def shutdown_all(self) -> list[ReleaseResult]: ...

Guarantees on cleanup:
    - release_test (scope="test"): SIGTERM with shutdown_timeout_s; SIGKILL on timeout.
      Returns ReleaseResult with start_unix, stop_unix, signaled_with, killed_by_timeout.
    - shutdown_all: invoked at end_suite (suite scope), close (process scope), AND
      registered with atexit as the failsafe (architecture.md L710 fallback path).
    - All cleanups are idempotent: re-releasing an already-dead server is a no-op.
"""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal, Sequence

Scope = Literal["test", "suite", "process"]


@dataclass(frozen=True)
class ServerSpec:
    command: Sequence[str]
    marker: str  # embedded in argv tail so ps can identify leaks
    # `startup_timeout_s` is currently CALLER-TRACKED, not enforced inside acquire().
    # The lifecycle manager does NOT block on subprocess readiness — it returns immediately
    # after Popen returns. The MCP handshake (initialize) is the caller's responsibility
    # (Epic 3 Story 3.1 mcp/transport.py territory). Production Story 1b.1 should
    # either implement a readiness wait here, or remove this field from the API.
    startup_timeout_s: float = 10.0
    shutdown_timeout_s: float = 2.0  # NFR-PERF-03d ceiling per architecture.md L709
    # NOTE on `env` mutability: frozen=True freezes attribute rebinding (`spec.env = ...`)
    # but does NOT freeze the dict itself. Callers mutating `spec.env` after construction
    # silently change future spawns using the same spec. Production Story 1b.1 should use
    # MappingProxyType or copy on construction. (P2.15 from Story 0.2 code review.)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ServerHandle:
    handle_id: str
    spec: ServerSpec
    process: subprocess.Popen
    spawned_at_unix: float
    test_id: str | None
    suite_id: str | None


@dataclass
class ReleaseResult:
    handle_id: str
    pid: int
    spawned_at_unix: float
    released_at_unix: float
    # P2.2 from review: this field name lies. It measures the entire process lifetime
    # (spawn-to-terminate-start), NOT startup latency. There is no MCP-handshake liveness
    # probe in this prototype. Production Story 1b.1 should rename to `process_lifetime_ms`
    # OR add a real startup probe and measure spawn-to-first-MCP-message.
    process_lifetime_ms: float  # renamed from startup_latency_ms (P2.2 review fix)
    # P-edge-6 from review: `shutdown_latency_ms` measures terminate_start → released_at
    # INCLUDING `Popen.wait()` reap time. It conflates: (a) kernel signal delivery,
    # (b) child's response to SIGTERM, (c) `wait()` reap latency. Production Story 1b.1
    # should split into `terminate_to_signal_delivered_ms` + `signal_to_reaped_ms` to
    # disambiguate. For the spike, the current single measurement matches the architecture's
    # ≤500ms median / ≤2s max gates well enough.
    shutdown_latency_ms: float
    signaled_with: str  # "SIGTERM" | "SIGKILL" | "already-dead" | "failed-EPERM"
    killed_by_timeout: bool


class MCPLifecycleManager:
    """Spawns + cleans up MCP server subprocesses per the configured scope.

    Lock-guarded state transitions. RF Listener v3 callbacks in RF 7.4.2 dispatch on a
    single thread per worker process; lock guards against future RF versions or async
    listener variants. (P2.13 review note: thread-safety is defensive, not measured.)

    The lock is `threading.RLock` (P2.8 review fix) because `_atexit_failsafe` can be
    triggered while `close()` is still holding the lock — a non-reentrant Lock would
    deadlock in that scenario.

    atexit IMPORTANT GAPS (D2.2 review decision 2026-05-17):
    - Python atexit handlers do NOT run on SIGKILL. SIGKILL-of-worker leaves
      MCP grandchildren orphaned to PID 1 (init/systemd). The lifecycle layer
      cannot recover from this; operators must teardown via systemd cgroup or
      container-level mitigation. This is documented in findings doc §AC-0.2.5.
    - atexit ALSO does not run on `os._exit()`, SIGSTOP, or other signals that
      bypass userspace.
    """

    def __init__(self, scope: Scope, *, default_spec: ServerSpec | None = None, install_sigterm_handler: bool = True) -> None:
        if scope not in ("test", "suite", "process"):
            raise ValueError(f"invalid scope {scope!r}; expected 'test'|'suite'|'process'")
        self.scope: Scope = scope
        self.default_spec = default_spec
        # RLock (not Lock) per P2.8: atexit failsafe can re-enter shutdown_all while close()
        # is still holding the lock; non-reentrant Lock would deadlock.
        self._lock = threading.RLock()
        self._by_test: dict[str, ServerHandle] = {}
        self._by_suite: dict[str, ServerHandle] = {}
        self._process_handle: ServerHandle | None = None
        self._released: list[ReleaseResult] = []
        # atexit failsafe per architecture.md L710. NOTE: does NOT run on SIGKILL
        # of the parent — see class docstring atexit IMPORTANT GAPS.
        atexit.register(self._atexit_failsafe)
        # D2.4 review finding (LOAD-BEARING): Python's default SIGTERM handler does NOT
        # invoke atexit — the process dies without running cleanup. Atexit-probe scenario B
        # demonstrated this empirically (3/3 iters leaked 3 MCP grandchildren when SIGTERM
        # hit the parent with default handler installed). The fix is to install a SIGTERM
        # handler that calls sys.exit(0), which DOES run atexit.
        # Caller can disable via install_sigterm_handler=False if they manage signals
        # themselves (e.g., pabot or a parent framework handles SIGTERM differently).
        if install_sigterm_handler:
            self._prior_sigterm_handler = signal.signal(signal.SIGTERM, self._on_sigterm)

    @staticmethod
    def _on_sigterm(signum, frame):  # type: ignore[no-untyped-def]
        """Convert SIGTERM into sys.exit so atexit handlers run.

        Without this, default Python SIGTERM behavior is to die immediately without
        running atexit — empirically validated by `measurements/atexit_probe/`.
        See D2.4 + D2.2 review findings.
        """
        sys.exit(0)

    # ---- spawn ----

    def acquire(
        self,
        *,
        test_id: str,
        suite_id: str,
        spec: ServerSpec | None = None,
    ) -> ServerHandle:
        """Acquire a server handle per the configured scope.

        Returns immediately after `subprocess.Popen` — MCP handshake readiness is
        the caller's responsibility (Epic 3 Story 3.1 mcp/transport.py territory).
        See ServerSpec.startup_timeout_s docstring.

        Raises ValueError if neither `spec` nor `default_spec` provides a ServerSpec.

        Idempotency: if a handle exists AND is alive for the relevant key, returns
        the existing handle. If it exists but is DEAD, the dead handle is recorded
        (P2.19 review fix) as an "already-dead" ReleaseResult before being replaced.
        """
        chosen_spec = spec or self.default_spec
        if chosen_spec is None:
            raise ValueError("ServerSpec required (no default_spec configured)")

        with self._lock:
            if self.scope == "test":
                existing = self._by_test.get(test_id)
                if existing is not None:
                    if self._is_alive(existing):
                        return existing
                    # P2.19 fix: dead handle being replaced — record the kill event so
                    # the audit trail captures the lifecycle transition rather than dropping it.
                    self._released.append(self._kill(existing))
                handle = self._spawn(chosen_spec, test_id=test_id, suite_id=suite_id)
                self._by_test[test_id] = handle
                return handle

            if self.scope == "suite":
                existing = self._by_suite.get(suite_id)
                if existing is not None:
                    if self._is_alive(existing):
                        return existing
                    self._released.append(self._kill(existing))
                handle = self._spawn(chosen_spec, test_id=None, suite_id=suite_id)
                self._by_suite[suite_id] = handle
                return handle

            # scope == "process"
            if self._process_handle is not None:
                if self._is_alive(self._process_handle):
                    return self._process_handle
                self._released.append(self._kill(self._process_handle))
            handle = self._spawn(chosen_spec, test_id=None, suite_id=None)
            self._process_handle = handle
            return handle

    def _spawn(self, spec: ServerSpec, *, test_id: str | None, suite_id: str | None) -> ServerHandle:
        # Append the spec.marker as an argv tail element so `ps -eo args` shows it.
        cmd = list(spec.command) + [spec.marker]
        env = os.environ.copy()
        env.update(spec.env)
        spawned_at = time.time()
        # start_new_session=True gives killpg semantics so we can clean up child trees on
        # terminate. Since start_new_session=True makes the child's pid == pgid, we can
        # safely use handle.process.pid directly as the pgid argument to killpg() —
        # NO need to call os.getpgid (P2.7 review fix: getpgid races against pid recycling).
        # stdin/stdout/stderr are DEVNULL — there is NO MCP-handshake liveness probe here.
        # Production Story 1b.1 should add a real readiness wait if needed.
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
        handle = ServerHandle(
            handle_id=str(uuid.uuid4()),
            spec=spec,
            process=process,
            spawned_at_unix=spawned_at,
            test_id=test_id,
            suite_id=suite_id,
        )
        return handle

    @staticmethod
    def _is_alive(handle: ServerHandle) -> bool:
        return handle.process.poll() is None

    # ---- release ----

    def release_test(self, test_id: str) -> ReleaseResult | None:
        """Release the test-scoped handle. No-op for suite/process scopes."""
        if self.scope != "test":
            return None
        with self._lock:
            handle = self._by_test.pop(test_id, None)
        if handle is None:
            return None
        return self._kill(handle)

    def release_suite(self, suite_id: str) -> ReleaseResult | None:
        """Release the suite-scoped handle. Also releases any test-scoped handles
        whose suite_id matches — defensive cleanup if end_test missed them."""
        with self._lock:
            handle = self._by_suite.pop(suite_id, None)
            # Defensive: any test-scoped handles for tests in this suite
            stragglers = [
                self._by_test.pop(tid)
                for tid, h in list(self._by_test.items())
                if h.suite_id == suite_id
            ]
        results = [self._kill(h) for h in stragglers]
        if handle is not None:
            results.append(self._kill(handle))
        # Return the suite-scoped one's result if present, else the last straggler.
        return results[-1] if results else None

    def shutdown_all(self) -> list[ReleaseResult]:
        """Kill every tracked handle. Called by end_suite for suite scope, by close
        for process scope, and by atexit as the load-bearing failsafe."""
        with self._lock:
            handles = list(self._by_test.values()) + list(self._by_suite.values())
            if self._process_handle is not None:
                handles.append(self._process_handle)
            self._by_test.clear()
            self._by_suite.clear()
            self._process_handle = None
        return [self._kill(h) for h in handles]

    def _kill(self, handle: ServerHandle) -> ReleaseResult:
        terminate_start = time.time()
        # P2.2 review fix: rename field but keep semantic — this measures process lifetime
        # (spawn-to-terminate-start), NOT startup latency. No handshake probe exists.
        process_lifetime_ms = (terminate_start - handle.spawned_at_unix) * 1000

        if handle.process.poll() is not None:
            # Already dead — record as such and return early.
            result = ReleaseResult(
                handle_id=handle.handle_id,
                pid=handle.process.pid,
                spawned_at_unix=handle.spawned_at_unix,
                released_at_unix=terminate_start,
                process_lifetime_ms=process_lifetime_ms,
                shutdown_latency_ms=0.0,
                signaled_with="already-dead",
                killed_by_timeout=False,
            )
            self._released.append(result)
            return result

        signaled_with = "SIGTERM"
        killed_by_timeout = False
        # P2.7 review fix: use handle.process.pid DIRECTLY as the pgid argument.
        # `start_new_session=True` made the child its own session/process-group leader,
        # so pid == pgid. Calling os.getpgid(pid) added a pid-recycle race window.
        pgid = handle.process.pid
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            # Race: process exited between poll() and killpg(). Acceptable.
            pass
        except PermissionError:
            # P2.9 review fix: EPERM ≠ ESRCH. EPERM means we lack permission to signal —
            # the process is genuinely alive but unreachable. Distinguish honestly.
            signaled_with = "failed-EPERM"

        try:
            handle.process.wait(timeout=handle.spec.shutdown_timeout_s)
        except subprocess.TimeoutExpired:
            # Hard kill — SIGKILL the process group.
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                signaled_with = "failed-EPERM"
            try:
                handle.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                # P-edge-5 review: a D-state (uninterruptible-sleep) process will not be
                # reaped here. We record signaled_with=SIGKILL anyway BUT the operator's
                # ps-based leak detector will still see the process. Two signals will
                # disagree; the ps detector is the ground truth.
                pass
            if signaled_with != "failed-EPERM":
                signaled_with = "SIGKILL"
                killed_by_timeout = True

        released_at = time.time()
        result = ReleaseResult(
            handle_id=handle.handle_id,
            pid=handle.process.pid,
            spawned_at_unix=handle.spawned_at_unix,
            released_at_unix=released_at,
            process_lifetime_ms=process_lifetime_ms,
            shutdown_latency_ms=(released_at - terminate_start) * 1000,
            signaled_with=signaled_with,
            killed_by_timeout=killed_by_timeout,
        )
        self._released.append(result)
        return result

    def _atexit_failsafe(self) -> None:
        """Last-resort cleanup at process exit.

        IMPORTANT: This does NOT run on SIGKILL of the parent process. Python atexit
        handlers only fire on normal exit, sys.exit(), or signals whose handler
        invokes sys.exit. SIGKILL bypasses userspace entirely — orphaned MCP
        grandchildren reparent to init/systemd. See D2.2 review decision + class
        docstring atexit IMPORTANT GAPS.

        This handler covers: normal interpreter exit, sys.exit() in caller, caught
        signals (SIGTERM, SIGINT) where the handler invokes sys.exit. It does NOT
        cover: SIGKILL, os._exit(), SIGSTOP, kernel OOM-killer.
        """
        try:
            results = self.shutdown_all()
            # Use os.write(2, ...) directly because by atexit time, sys.stderr may have been
            # closed by an earlier-registered atexit handler (e.g., logging shutdown).
            for r in results:
                msg = (
                    f"[context_prototype:atexit_failsafe] released handle_id={r.handle_id} "
                    f"pid={r.pid} via={r.signaled_with} (post-test/suite cleanup missed)\n"
                )
                try:
                    os.write(2, msg.encode("utf-8"))
                except OSError:
                    pass  # fd closed; nothing we can do
        except Exception:
            # Never propagate exceptions out of atexit — the interpreter is shutting down
            # and a raise here would mask whatever the real exit reason was.
            pass

    # ---- inspection helpers (used by tests + measurement code) ----

    def released_results(self) -> list[ReleaseResult]:
        return list(self._released)

    def in_flight_count(self) -> int:
        with self._lock:
            n = len(self._by_test) + len(self._by_suite)
            if self._process_handle is not None:
                n += 1
            return n
