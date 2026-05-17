"""Robot Framework Listener v3 wrapper around context_prototype.MCPLifecycleManager.

Drives the cleanup primitive from RF lifecycle events:
    - start_test → manager.acquire(test_id, suite_id)
    - end_test   → manager.release_test(test_id)   [scope="test" only]
    - end_suite  → manager.release_suite(suite_id) [scope="suite" only]
    - close      → manager.shutdown_all()          [scope="process" only]

Plus atexit failsafe (registered inside MCPLifecycleManager itself per architecture.md L710).

Usage in pabot:
    pabot --listener "mcp_listener:MCPCleanupListener:<scope>:<server_module>" \
        --testlevelsplit --processes 8 suites/pabot_test_scope.robot

Listener args (positional, colon-separated per RF Listener API):
    scope            — 'test' | 'suite' | 'process'
    server_module    — 'echo_server' | 'slow_server' | 'rf_mcp_substitute'
    measurements_dir — optional path; defaults to ./measurements (relative to listener cwd)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

LISTENER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(LISTENER_DIR))

from context_prototype import MCPLifecycleManager, ServerSpec  # noqa: E402

ROBOT_LISTENER_API_VERSION = 3


SERVER_MODULES = {
    "echo_server": ("servers.echo_server", "SPIKE-0-2-ECHO"),
    "slow_server": ("servers.slow_server", "SPIKE-0-2-SLOW"),
    "rf_mcp_substitute": ("servers.rf_mcp_substitute", "SPIKE-0-2-RFMCPSUB"),
}


class MCPCleanupListener:
    """RF Listener v3 wiring the cleanup primitive to RF lifecycle events.

    Per-pabot-worker instance (one per worker process). All measurements append
    to a per-worker JSON file in measurements_dir for later aggregation.
    """

    def __init__(self, scope: str, server_module: str, measurements_dir: str | None = None) -> None:
        if scope not in ("test", "suite", "process"):
            raise ValueError(f"scope must be 'test'|'suite'|'process'; got {scope!r}")
        if server_module not in SERVER_MODULES:
            raise ValueError(f"unknown server_module {server_module!r}; pick from {list(SERVER_MODULES)}")
        self.scope = scope
        self.server_module = server_module
        module_path, marker = SERVER_MODULES[server_module]
        # Build the python -m invocation for the server. Use the venv's python.
        self.spec = ServerSpec(
            command=[sys.executable, "-m", module_path],
            marker=marker,
            startup_timeout_s=10.0,
            shutdown_timeout_s=2.0,
        )
        self.manager = MCPLifecycleManager(scope=scope, default_spec=self.spec)  # type: ignore[arg-type]
        self.measurements_dir = Path(measurements_dir or (LISTENER_DIR / "measurements"))
        self.measurements_dir.mkdir(parents=True, exist_ok=True)
        self._out_path = self.measurements_dir / f"raw_pid{os.getpid()}_scope-{scope}_server-{server_module}.jsonl"

    # ---- RF Listener v3 callbacks ----

    def start_test(self, data, result):  # noqa: D401
        test_id = data.id
        suite_id = data.parent.id if data.parent else "unknown-suite"
        # P2.11 review fix: log start_test events even on success so we can disambiguate
        # "acquire never happened" from "acquire happened but release didn't fire."
        # On acquire failure, emit a diagnostic record so a failed cell is distinguishable
        # from a successful no-op in the JSONL.
        try:
            handle = self.manager.acquire(test_id=test_id, suite_id=suite_id)
            self._append({
                "event": "acquire",
                "test_id": test_id,
                "suite_id": suite_id,
                "scope": self.scope,
                "server_module": self.server_module,
                "handle_id": handle.handle_id,
                "pid": handle.process.pid,
                "spawned_at_unix": handle.spawned_at_unix,
            })
        except Exception as exc:
            self._append({
                "event": "acquire_failed",
                "test_id": test_id,
                "suite_id": suite_id,
                "scope": self.scope,
                "server_module": self.server_module,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            })
            raise

    def end_test(self, data, result):  # noqa: D401
        if self.scope == "test":
            release = self.manager.release_test(data.id)
            if release is not None:
                self._append(self._release_record("release_test", release, test_id=data.id))

    def end_suite(self, data, result):  # noqa: D401
        # P2.12 review fix: always call release_suite regardless of scope, so the
        # defensive straggler-cleanup code can actually run if end_test missed.
        release = self.manager.release_suite(data.id)
        if release is not None:
            self._append(self._release_record("release_suite", release, suite_id=data.id))

    def close(self):  # noqa: D401
        results = self.manager.shutdown_all()
        for r in results:
            self._append(self._release_record("shutdown_all", r))

    def _release_record(self, event: str, r, *, test_id=None, suite_id=None) -> dict:
        """Build a JSONL record from a ReleaseResult. Uses the renamed
        `process_lifetime_ms` field (P2.2 review) instead of the misleading
        `startup_latency_ms` name."""
        record = {
            "event": event,
            "scope": self.scope,
            "server_module": self.server_module,
            "handle_id": r.handle_id,
            "pid": r.pid,
            "spawned_at_unix": r.spawned_at_unix,
            "released_at_unix": r.released_at_unix,
            "process_lifetime_ms": r.process_lifetime_ms,
            "shutdown_latency_ms": r.shutdown_latency_ms,
            "signaled_with": r.signaled_with,
            "killed_by_timeout": r.killed_by_timeout,
        }
        if test_id is not None:
            record["test_id"] = test_id
        if suite_id is not None:
            record["suite_id"] = suite_id
        return record

    # ---- helpers ----

    def _append(self, record: dict) -> None:
        with open(self._out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
