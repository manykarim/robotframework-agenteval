"""Unit tests for _kernel/context.py (AC-1b.1.1 → AC-1b.1.5).

Coverage:
- Scope + _resolve_scope translator (AC-1b.1.1)
- TestContext + ContextVar bind/unbind + thread isolation (AC-1b.1.2)
- ServerSpec / ServerHandle / ReleaseResult dataclass shape (AC-1b.1.3)
- MCPLifecycleManager acquire/release_test/release_suite/shutdown_all
  with fake-subprocess (AC-1b.1.3 + AC-1b.1.4)
- atexit failsafe registered (AC-1b.1.4)
- SIGTERM auto-handler installed (AC-1b.1.4)
- minimize-env whitelist verified (AC-1b.1.4)
- resolve_config 4-layer precedence + type coercion + invalid coercion (AC-1b.1.5)
- _load_dotenv parses key=value, skips comments + blanks (AC-1b.1.5)
"""

from __future__ import annotations

import errno
import signal
import subprocess
import threading
import time
import warnings
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest import mock

import pytest

from AgentEval._kernel import context as ctx
from AgentEval._kernel.context import (
    MCPLifecycleManager,
    ReleaseResult,
    ServerHandle,
    ServerSpec,
    TestContext,
    _resolve_scope,
    bind_context,
    current_context,
    resolve_config,
    set_current_test_id,
    unbind_context,
)

# ========================================================================= #
# AC-1b.1.1: Scope + _resolve_scope translator                              #
# ========================================================================= #


def test_resolve_scope_true_maps_to_test() -> None:
    assert _resolve_scope(True) == "test"


def test_resolve_scope_false_maps_to_process() -> None:
    assert _resolve_scope(False) == "process"


def test_resolve_scope_suite_passes_through() -> None:
    assert _resolve_scope("suite") == "suite"


def test_resolve_scope_raises_on_invalid_string() -> None:
    with pytest.raises(ValueError, match="must be True, False, or 'suite'"):
        _resolve_scope("test")  # type: ignore[arg-type]


def test_resolve_scope_raises_on_invalid_type() -> None:
    with pytest.raises(ValueError, match="must be True, False, or 'suite'"):
        _resolve_scope(1)  # type: ignore[arg-type]


# ========================================================================= #
# AC-1b.1.2: TestContext + ContextVar bind/unbind/current/thread-isolation  #
# ========================================================================= #


@pytest.fixture(autouse=True)
def _clear_context_between_tests() -> Any:
    """Ensure ContextVar is reset between tests to avoid leakage."""
    yield
    unbind_context()


def test_current_context_returns_none_by_default() -> None:
    assert current_context() is None


def test_bind_context_and_current_round_trip() -> None:
    ctx_obj = TestContext(test_id="t1", suite_id="s1", scope="test")
    bind_context(ctx_obj)
    assert current_context() == ctx_obj


def test_unbind_context_clears_to_none() -> None:
    bind_context(TestContext(test_id="t1", suite_id="s1", scope="test"))
    assert current_context() is not None
    unbind_context()
    assert current_context() is None


def test_set_current_test_id_convenience_wrapper() -> None:
    set_current_test_id("t42", suite_id="s7", scope="suite")
    got = current_context()
    assert got is not None
    assert got.test_id == "t42"
    assert got.suite_id == "s7"
    assert got.scope == "suite"


def test_set_current_test_id_defaults() -> None:
    set_current_test_id("t1")
    got = current_context()
    assert got is not None
    assert got.test_id == "t1"
    assert got.suite_id == ""
    assert got.scope == "test"


def test_context_isolated_across_threads() -> None:
    """ContextVar must NOT leak across threads — test A's binding is invisible
    to test B running in another thread.
    """
    bind_context(TestContext(test_id="main-thread", suite_id="s", scope="test"))

    seen_in_other_thread: list[TestContext | None] = []

    def worker() -> None:
        # Fresh thread → fresh ContextVar copy with default=None.
        seen_in_other_thread.append(current_context())

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    # Other thread saw the default (None) — no cross-thread leak.
    assert seen_in_other_thread == [None]
    # Main thread still sees its binding.
    main_ctx = current_context()
    assert main_ctx is not None
    assert main_ctx.test_id == "main-thread"


# ========================================================================= #
# AC-1b.1.3: ServerSpec / ServerHandle / ReleaseResult dataclass shape      #
# ========================================================================= #


def test_serverspec_create_wraps_env_in_mappingproxytype() -> None:
    spec = ServerSpec.create(
        command=["python", "-m", "fake_mcp"],
        marker="agenteval-test-marker",
        env={"FAKE_KEY": "fake_value"},
    )
    assert isinstance(spec.env, MappingProxyType)
    assert spec.env["FAKE_KEY"] == "fake_value"
    # MappingProxyType blocks mutation.
    with pytest.raises(TypeError):
        spec.env["other"] = "x"  # type: ignore[index]


def test_serverspec_create_empty_env_default() -> None:
    spec = ServerSpec.create(command=["x"], marker="m")
    assert isinstance(spec.env, MappingProxyType)
    assert dict(spec.env) == {}


def test_releaseresult_field_named_process_lifetime_ms_not_startup_latency() -> None:
    """P2.2 review fix: spike's `startup_latency_ms` was misnamed; renamed to
    `process_lifetime_ms` in production API. ReleaseResult MUST have the
    correct name to prevent the bug from reappearing.
    """
    rr = ReleaseResult(
        handle_id="h1",
        pid=12345,
        spawned_at_unix=1000.0,
        released_at_unix=1001.0,
        process_lifetime_ms=1000.0,
        shutdown_latency_ms=10.0,
        signaled_with="SIGTERM",
        killed_by_timeout=False,
    )
    assert rr.process_lifetime_ms == 1000.0
    assert not hasattr(rr, "startup_latency_ms")


# ========================================================================= #
# AC-1b.1.3 + AC-1b.1.4: MCPLifecycleManager — fake-subprocess based tests  #
# ========================================================================= #


class _FakePopen:
    """Stand-in for subprocess.Popen used by MCPLifecycleManager tests.

    Tracks pid, poll() state, wait() invocations, and signal delivery via the
    monkey-patched `os.killpg`.
    """

    _next_pid = 9000

    def __init__(self, args: list[str], **_kwargs: Any) -> None:
        type(self)._next_pid += 1
        self.pid = type(self)._next_pid
        self.args = args
        self._returncode: int | None = None  # None = alive
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self._returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        if self._returncode is not None:
            return self._returncode
        # Match real subprocess.Popen.wait semantics: timeout=0 against a live
        # process raises TimeoutExpired immediately (used by M1 reap-first race
        # check); positive/None timeout synthesizes clean exit for test scenarios.
        if timeout == 0:
            import subprocess as _sp

            raise _sp.TimeoutExpired(cmd=self.args, timeout=0)
        self._returncode = 0
        return self._returncode


@pytest.fixture
def _patched_subprocess(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch subprocess.Popen + os.killpg + signal.signal so MCPLifecycleManager
    tests don't actually spawn processes or install signal handlers.
    """
    killpg_calls: list[tuple[int, int]] = []
    signal_calls: list[tuple[int, Any]] = []

    def fake_killpg(pid: int, sig: int) -> None:
        killpg_calls.append((pid, sig))

    def fake_signal(sig: int, handler: Any) -> Any:
        signal_calls.append((sig, handler))
        return signal.SIG_DFL  # any old handler is fine for the return slot

    monkeypatch.setattr(ctx.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(ctx.os, "killpg", fake_killpg)
    monkeypatch.setattr(ctx.signal, "signal", fake_signal)
    return {"killpg_calls": killpg_calls, "signal_calls": signal_calls}


def _default_spec() -> ServerSpec:
    return ServerSpec.create(
        command=["python", "-m", "fake_mcp"],
        marker="agenteval-test-marker",
        shutdown_timeout_s=0.05,  # tiny for tests
    )


def test_mcplifecyclemanager_acquire_returns_serverhandle(
    _patched_subprocess: dict[str, Any],
) -> None:
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    handle = mgr.acquire(test_id="t1", suite_id="s1")
    assert isinstance(handle, ServerHandle)
    assert handle.test_id == "t1"
    assert handle.suite_id == "s1"


def test_mcplifecyclemanager_acquire_raises_without_any_spec(
    _patched_subprocess: dict[str, Any],
) -> None:
    """P2.14 review fix: acquire() without a spec OR a default_spec must raise."""
    mgr = MCPLifecycleManager("test")
    with pytest.raises(ValueError, match="requires either an explicit spec"):
        mgr.acquire(test_id="t1", suite_id="s1")


def test_mcplifecyclemanager_release_test_returns_releaseresult(
    _patched_subprocess: dict[str, Any],
) -> None:
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    mgr.acquire(test_id="t1", suite_id="s1")
    results = mgr.release_test("t1")
    assert len(results) == 1
    assert isinstance(results[0], ReleaseResult)
    # killpg was called with SIGTERM (success path).
    killpg_calls = _patched_subprocess["killpg_calls"]
    assert any(sig == signal.SIGTERM for _, sig in killpg_calls)


def test_mcplifecyclemanager_release_suite_collects_all_handles_in_suite(
    _patched_subprocess: dict[str, Any],
) -> None:
    """H1 review fix: in 'suite' scope, acquire is idempotent per suite_id.
    Two acquires for the same suite return the same handle; two suites = 2 handles.
    """
    mgr = MCPLifecycleManager("suite", default_spec=_default_spec())
    h1 = mgr.acquire(test_id="t1", suite_id="s1")
    h1_reuse = mgr.acquire(test_id="t2", suite_id="s1")
    mgr.acquire(test_id="t3", suite_id="s2")
    assert h1 is h1_reuse  # idempotent reuse within same suite
    results = mgr.release_suite("s1")
    assert len(results) == 1  # one handle released for s1; s2 still alive
    results = mgr.release_suite("s2")
    assert len(results) == 1


def test_mcplifecyclemanager_shutdown_all_drains_everything(_patched_subprocess: dict[str, Any]) -> None:
    """In 'test' scope, multiple acquires for different test_ids → multiple handles.
    shutdown_all drains all of them.
    """
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    mgr.acquire(test_id="t1", suite_id="s1")
    mgr.acquire(test_id="t2", suite_id="s1")
    results = mgr.shutdown_all()
    assert len(results) == 2
    # Subsequent shutdown_all is idempotent → empty.
    assert mgr.shutdown_all() == []


def test_mcplifecyclemanager_emits_already_dead_when_process_pre_exits(
    _patched_subprocess: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """P-edge fix: dead-and-replaced handles must NOT silently drop; they
    must emit a ReleaseResult with `signaled_with="already-dead"`.
    """
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    handle = mgr.acquire(test_id="t1", suite_id="s1")
    # Simulate the process dying before release_test() is called.
    handle.process._returncode = 0  # type: ignore[attr-defined]
    results = mgr.release_test("t1")
    assert len(results) == 1
    assert results[0].signaled_with == "already-dead"


def test_mcplifecyclemanager_distinguishes_eperm_from_esrch(
    _patched_subprocess: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """P-edge fix: EPERM means we can't signal the process group — must report
    failed-EPERM, NOT silently treat as success.
    """
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    mgr.acquire(test_id="t1", suite_id="s1")

    # Override killpg to raise PermissionError with errno=EPERM.
    def killpg_eperm(pid: int, sig: int) -> None:
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(ctx.os, "killpg", killpg_eperm)
    results = mgr.release_test("t1")
    assert len(results) == 1
    assert results[0].signaled_with == "failed-EPERM"


def test_mcplifecyclemanager_esrch_treated_as_already_dead(
    _patched_subprocess: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    mgr.acquire(test_id="t1", suite_id="s1")

    def killpg_esrch(pid: int, sig: int) -> None:
        raise ProcessLookupError(errno.ESRCH, "No such process")

    monkeypatch.setattr(ctx.os, "killpg", killpg_esrch)
    results = mgr.release_test("t1")
    assert results[0].signaled_with == "already-dead"


def test_mcplifecyclemanager_installs_sigterm_handler_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """D2.4 LOAD-BEARING: __init__ MUST install a SIGTERM→sys.exit handler by
    default. Verifies via `signal.getsignal(SIGTERM)` per AC-1b.1.8 + L2
    review fix (was checking the mocked signal.signal call list).
    """
    from AgentEval._kernel.context import _sigterm_to_sysexit

    monkeypatch.setattr(ctx.subprocess, "Popen", _FakePopen)
    prior = signal.getsignal(signal.SIGTERM)
    try:
        mgr = MCPLifecycleManager("test", install_sigterm_handler=True)
        assert signal.getsignal(signal.SIGTERM) is _sigterm_to_sysexit
        mgr.close()  # restores prior handler
    finally:
        # Defensive: even if mgr.close() failed, ensure prior handler is restored.
        signal.signal(signal.SIGTERM, prior)


def test_mcplifecyclemanager_install_sigterm_handler_false_skips_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When install_sigterm_handler=False, the SIGTERM handler must remain
    unchanged from the prior state.
    """
    monkeypatch.setattr(ctx.subprocess, "Popen", _FakePopen)
    prior = signal.getsignal(signal.SIGTERM)
    try:
        mgr = MCPLifecycleManager("test", install_sigterm_handler=False)
        assert signal.getsignal(signal.SIGTERM) is prior
        mgr.close()
    finally:
        signal.signal(signal.SIGTERM, prior)


def test_mcplifecyclemanager_uses_rlock_not_lock() -> None:
    """P2.8 review fix: atexit failsafe can re-enter shutdown_all while a
    release_* call is still holding the lock — so RLock is mandatory.
    """
    # Inspect class-level state after __init__ on a no-arg manager.
    with mock.patch("AgentEval._kernel.context.subprocess.Popen", _FakePopen):
        mgr = MCPLifecycleManager("test", install_sigterm_handler=False)
    # RLock instances are of type `_thread.RLock`; Lock is `_thread.lock`.
    # We assert the class repr matches RLock.
    assert "RLock" in repr(type(mgr._lock))


def test_mcplifecyclemanager_registers_atexit_failsafe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """atexit.register(self.shutdown_all) must be called by __init__."""
    atexit_registered: list[Any] = []

    def fake_register(func: Any) -> Any:
        atexit_registered.append(func)
        return func

    monkeypatch.setattr(ctx.atexit, "register", fake_register)
    monkeypatch.setattr(ctx.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(ctx.signal, "signal", lambda sig, handler: None)

    mgr = MCPLifecycleManager("test", install_sigterm_handler=False)
    # The registered callable must be the manager's bound shutdown_all method.
    assert any(callable(f) and f.__self__ is mgr for f in atexit_registered)  # type: ignore[attr-defined]


# ========================================================================= #
# AC-1b.1.4: minimize-env whitelist (credential leak mitigation)            #
# ========================================================================= #


def test_build_minimized_env_only_whitelists_default_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify _DEFAULT_ENV_WHITELIST is the only os.environ subset passed to
    child MCP server subprocesses. os.environ.copy() would leak credentials.
    """
    monkeypatch.setenv("PATH", "/fake/path")
    monkeypatch.setenv("HOME", "/fake/home")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leaked-credential")
    monkeypatch.setenv("LITELLM_PROXY_KEY", "sk-also-leaked")

    env = MCPLifecycleManager._build_minimized_env(MappingProxyType({}))

    assert env["PATH"] == "/fake/path"
    assert env["HOME"] == "/fake/home"
    # Credentials MUST NOT appear.
    assert "ANTHROPIC_API_KEY" not in env
    assert "LITELLM_PROXY_KEY" not in env


def test_build_minimized_env_overlays_spec_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/fake/path")
    spec_env = MappingProxyType({"MCP_SPECIFIC_KEY": "x", "PATH": "/override/path"})

    env = MCPLifecycleManager._build_minimized_env(spec_env)

    # spec_env overlays over the whitelist.
    assert env["PATH"] == "/override/path"
    assert env["MCP_SPECIFIC_KEY"] == "x"


# ========================================================================= #
# AC-1b.1.5: resolve_config — FR41 4-layer precedence                       #
# ========================================================================= #


def test_resolve_config_returns_all_9_fr42_fr11b_keys() -> None:
    """Story 5.1 added `trace_path` (10th key) to support the JSONL backend.

    Test name preserved for git-blame continuity; the key count is now 10
    after Story 5.1's `trace_path` addition (PRD FR33b JSONL backend + AC-5.1.6).
    """
    cfg = resolve_config({}, dotenv_path=Path("/nonexistent/.env"))
    expected_keys = {
        "provider",
        "telemetry",
        "trace_backend",
        "trace_path",
        "allow_validate_operator",
        "default_temperature",
        "mcp_per_test",
        "allow_external_mcp_blind",
        "max_cost_usd",
        "max_runtime_seconds",
    }
    assert set(cfg.keys()) == expected_keys


def test_resolve_config_layer4_defaults_match_fr42(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No kwargs, no env, no .env → FR42 + FR11b defaults across the board."""
    for env_name in (
        "AGENTEVAL_PROVIDER",
        "AGENTEVAL_TELEMETRY",
        "AGENTEVAL_TRACE_BACKEND",
        "AGENTEVAL_TRACE_PATH",
        "AGENTEVAL_ALLOW_VALIDATE_OPERATOR",
        "AGENTEVAL_DEFAULT_TEMPERATURE",
        "AGENTEVAL_MCP_PER_TEST",
        "AGENTEVAL_ALLOW_EXTERNAL_MCP_BLIND",
        "AGENTEVAL_MAX_COST_USD",
        "AGENTEVAL_MAX_RUNTIME_SECONDS",
    ):
        monkeypatch.delenv(env_name, raising=False)

    cfg = resolve_config({}, dotenv_path=tmp_path / "nonexistent.env")
    assert cfg == {
        "provider": "litellm",
        "telemetry": True,
        "trace_backend": "memory",
        "trace_path": None,
        "allow_validate_operator": False,
        "default_temperature": 0.0,
        "mcp_per_test": True,
        "allow_external_mcp_blind": False,
        "max_cost_usd": 5.00,
        "max_runtime_seconds": None,
    }


def test_resolve_config_layer3_dotenv_overrides_defaults(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("# a comment\n\nAGENTEVAL_PROVIDER=custom-provider\nAGENTEVAL_TELEMETRY=false\n")
    cfg = resolve_config({}, dotenv_path=dotenv)
    assert cfg["provider"] == "custom-provider"
    assert cfg["telemetry"] is False
    # Unspecified keys still use defaults.
    assert cfg["trace_backend"] == "memory"


def test_resolve_config_layer2_env_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("AGENTEVAL_PROVIDER=from-dotenv\n")
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "from-env")
    cfg = resolve_config({}, dotenv_path=dotenv)
    assert cfg["provider"] == "from-env"


def test_resolve_config_layer1_kwarg_overrides_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "from-env")
    cfg = resolve_config({"provider": "from-kwarg"}, dotenv_path=tmp_path / "absent.env")
    assert cfg["provider"] == "from-kwarg"


def test_resolve_config_explicit_none_wins_over_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Story 1b.1 code review H3 fix: explicit None IS a user-passed value and
    wins over env-vars per FR41 'kwarg wins' invariant. This is load-bearing
    for max_runtime_seconds=None (meaning 'no cap') overriding a stale env-var.
    """
    monkeypatch.setenv("AGENTEVAL_MAX_RUNTIME_SECONDS", "60.0")
    cfg = resolve_config({"max_runtime_seconds": None}, dotenv_path=tmp_path / "absent.env")
    assert cfg["max_runtime_seconds"] is None

    # Same invariant for provider (where None isn't semantically meaningful but
    # the precedence rule is the same).
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "from-env")
    cfg = resolve_config({"provider": None}, dotenv_path=tmp_path / "absent.env")
    assert cfg["provider"] is None


# ---- AC-1b.1.5: type coercion per param --------------------------------- #


def test_resolve_config_coerces_telemetry_true_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTEVAL_TELEMETRY", "false")
    cfg = resolve_config({}, dotenv_path=tmp_path / "absent.env")
    assert cfg["telemetry"] is False

    monkeypatch.setenv("AGENTEVAL_TELEMETRY", "true")
    cfg = resolve_config({}, dotenv_path=tmp_path / "absent.env")
    assert cfg["telemetry"] is True


def test_resolve_config_coerces_mcp_per_test_all_three_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTEVAL_MCP_PER_TEST", "true")
    assert resolve_config({}, dotenv_path=tmp_path / "absent.env")["mcp_per_test"] is True

    monkeypatch.setenv("AGENTEVAL_MCP_PER_TEST", "false")
    assert resolve_config({}, dotenv_path=tmp_path / "absent.env")["mcp_per_test"] is False

    monkeypatch.setenv("AGENTEVAL_MCP_PER_TEST", "suite")
    assert resolve_config({}, dotenv_path=tmp_path / "absent.env")["mcp_per_test"] == "suite"


def test_resolve_config_coerces_floats(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTEVAL_DEFAULT_TEMPERATURE", "0.7")
    monkeypatch.setenv("AGENTEVAL_MAX_COST_USD", "2.5")
    cfg = resolve_config({}, dotenv_path=tmp_path / "absent.env")
    assert cfg["default_temperature"] == 0.7
    assert cfg["max_cost_usd"] == 2.5


def test_resolve_config_coerces_max_runtime_seconds_empty_to_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AGENTEVAL_MAX_RUNTIME_SECONDS", "")
    cfg = resolve_config({}, dotenv_path=tmp_path / "absent.env")
    assert cfg["max_runtime_seconds"] is None

    monkeypatch.setenv("AGENTEVAL_MAX_RUNTIME_SECONDS", "60.0")
    cfg = resolve_config({}, dotenv_path=tmp_path / "absent.env")
    assert cfg["max_runtime_seconds"] == 60.0


def test_resolve_config_invalid_bool_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTEVAL_TELEMETRY", "not-a-bool")
    with pytest.raises(ValueError, match="telemetry"):
        resolve_config({}, dotenv_path=tmp_path / "absent.env")


def test_resolve_config_invalid_float_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENTEVAL_MAX_COST_USD", "not-a-float")
    with pytest.raises(ValueError, match="max_cost_usd"):
        resolve_config({}, dotenv_path=tmp_path / "absent.env")


# ---- AC-1b.1.5: _load_dotenv parser ------------------------------------- #


def test_load_dotenv_skips_comments_and_blanks(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# header comment\n"
        "\n"
        "AGENTEVAL_PROVIDER=litellm\n"
        "  # indented comment\n"
        "AGENTEVAL_TELEMETRY=true\n"
        "MALFORMED_LINE_NO_EQUALS\n"
    )
    parsed = ctx._load_dotenv(dotenv)
    assert parsed == {
        "AGENTEVAL_PROVIDER": "litellm",
        "AGENTEVAL_TELEMETRY": "true",
    }


def test_load_dotenv_missing_file_returns_empty(tmp_path: Path) -> None:
    assert ctx._load_dotenv(tmp_path / "nonexistent.env") == {}


# ========================================================================= #
# Story 1b.1 code-review patches — new test coverage                        #
# ========================================================================= #


# ---- H1 P2.19 scope-aware idempotent acquire ---------------------------- #


def test_acquire_test_scope_idempotent_per_test_id(_patched_subprocess: dict[str, Any]) -> None:
    """H1: 'test' scope acquire is idempotent for the same test_id."""
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    h1 = mgr.acquire(test_id="t1", suite_id="s1")
    h2 = mgr.acquire(test_id="t1", suite_id="s1")
    assert h1 is h2  # same handle returned
    # Different test_id → different handle.
    h3 = mgr.acquire(test_id="t2", suite_id="s1")
    assert h3 is not h1


def test_acquire_process_scope_returns_single_shared_handle(_patched_subprocess: dict[str, Any]) -> None:
    """H1: 'process' scope acquire always returns the same handle regardless of test_id/suite_id."""
    mgr = MCPLifecycleManager("process", default_spec=_default_spec())
    h1 = mgr.acquire(test_id="t1", suite_id="s1")
    h2 = mgr.acquire(test_id="t2", suite_id="s2")
    h3 = mgr.acquire(test_id="t99", suite_id="s99")
    assert h1 is h2 is h3
    # Only shutdown_all (or close) drains; release_test + release_suite are no-ops.
    assert mgr.release_test("t1") == []
    assert mgr.release_suite("s1") == []
    results = mgr.shutdown_all()
    assert len(results) == 1


def test_release_test_no_op_outside_test_scope(_patched_subprocess: dict[str, Any]) -> None:
    """H1: release_test() in 'suite' or 'process' scope is a no-op."""
    for scope in ("suite", "process"):
        mgr = MCPLifecycleManager(scope, default_spec=_default_spec())  # type: ignore[arg-type]
        mgr.acquire(test_id="t1", suite_id="s1")
        assert mgr.release_test("t1") == []


# ---- H2 process_lifetime_ms uses monotonic-only subtraction ------------ #


def test_release_result_process_lifetime_ms_is_non_negative(_patched_subprocess: dict[str, Any]) -> None:
    """H2: process_lifetime_ms must be computed from monotonic deltas — never
    negative, never billion-magnitude. Pre-fix value was on the order of
    -monotonic_origin * 1000 (often -10^12 to -10^13).
    """
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    mgr.acquire(test_id="t1", suite_id="s1")
    time.sleep(0.001)  # ensure a non-zero monotonic delta
    results = mgr.release_test("t1")
    assert len(results) == 1
    rr = results[0]
    # Monotonic-only math: must be small positive number (a few ms at most for
    # the sleep + signal overhead in the test fixture).
    assert 0.0 <= rr.process_lifetime_ms < 1000.0, f"unexpected lifetime: {rr.process_lifetime_ms}"


# ---- H7 D-state survivors don't abandon remaining handles --------------- #


def test_shutdown_all_continues_when_one_handle_survives(
    _patched_subprocess: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """H7: shutdown_all() drains ALL handles even if one ends up as 'survived';
    we must not abandon the rest mid-loop.
    """
    mgr = MCPLifecycleManager("test", default_spec=_default_spec())
    h1 = mgr.acquire(test_id="t1", suite_id="s1")
    mgr.acquire(test_id="t2", suite_id="s2")

    # Force the first handle to "survive": override its Popen.poll() so it
    # always returns None (alive) even after wait+kill calls.
    original_poll = h1.process.poll  # type: ignore[attr-defined]

    def fake_poll() -> None:
        return None  # Always alive — synthesizes D-state survivor.

    h1.process.poll = fake_poll  # type: ignore[method-assign,attr-defined]
    # Make wait() also fail to reap (TimeoutExpired forever).
    h1.process.wait = lambda timeout=None: (_ for _ in ()).throw(  # type: ignore[method-assign,attr-defined]
        subprocess.TimeoutExpired(cmd=["fake"], timeout=timeout or 0)
    )

    results = mgr.shutdown_all()
    assert len(results) == 2  # both handles drained
    signaled_set = {r.signaled_with for r in results}
    assert "survived" in signaled_set  # h1 survived
    assert "SIGTERM" in signaled_set or "SIGKILL" in signaled_set or "already-dead" in signaled_set

    # Restore for cleanup hygiene.
    h1.process.poll = original_poll  # type: ignore[method-assign,attr-defined]


# ---- M2 close() restores prior SIGTERM handler + unregisters atexit ----- #


def test_close_unregisters_atexit_and_restores_sigterm_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """M2: close() must restore prior SIGTERM handler + remove atexit registration."""
    monkeypatch.setattr(ctx.subprocess, "Popen", _FakePopen)
    prior = signal.getsignal(signal.SIGTERM)
    try:
        mgr = MCPLifecycleManager("test", install_sigterm_handler=True)
        from AgentEval._kernel.context import _sigterm_to_sysexit

        assert signal.getsignal(signal.SIGTERM) is _sigterm_to_sysexit
        mgr.close()
        assert signal.getsignal(signal.SIGTERM) is prior
    finally:
        signal.signal(signal.SIGTERM, prior)


# ---- M6 shutdown_timeout_s must be > 0 --------------------------------- #


def test_serverspec_rejects_zero_or_negative_shutdown_timeout() -> None:
    """M6: shutdown_timeout_s must be > 0; zero/negative would skip graceful wait."""
    with pytest.raises(ValueError, match="shutdown_timeout_s must be > 0"):
        ServerSpec.create(command=["x"], marker="m", shutdown_timeout_s=0)
    with pytest.raises(ValueError, match="shutdown_timeout_s must be > 0"):
        ServerSpec.create(command=["x"], marker="m", shutdown_timeout_s=-1.0)


# ---- M7 _load_dotenv handles quoted values + export prefix ------------- #


def test_load_dotenv_strips_surrounding_quotes(tmp_path: Path) -> None:
    """M7: surrounding matching quotes are stripped from values."""
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        'AGENTEVAL_PROVIDER="litellm"\n'
        "AGENTEVAL_TELEMETRY='true'\n"
        "AGENTEVAL_TRACE_BACKEND=memory\n"  # no quotes, unchanged
    )
    parsed = ctx._load_dotenv(dotenv)
    assert parsed == {
        "AGENTEVAL_PROVIDER": "litellm",
        "AGENTEVAL_TELEMETRY": "true",
        "AGENTEVAL_TRACE_BACKEND": "memory",
    }


def test_load_dotenv_strips_export_prefix(tmp_path: Path) -> None:
    """M7: shell-sourced .env files use `export KEY=VALUE`; prefix must be stripped."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("export AGENTEVAL_PROVIDER=litellm\n")
    parsed = ctx._load_dotenv(dotenv)
    assert parsed == {"AGENTEVAL_PROVIDER": "litellm"}


# ---- M8 unknown AGENTEVAL_* keys emit warning -------------------------- #


def test_resolve_config_warns_on_unknown_agenteval_env_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """M8: typos like AGENTEVAL_PROVDER must produce UserWarning rather than silent fallback."""
    monkeypatch.setenv("AGENTEVAL_PROVDER", "anthropic")  # typo
    with pytest.warns(UserWarning, match=r"Unknown agenteval env-var 'AGENTEVAL_PROVDER'"):
        resolve_config({}, dotenv_path=tmp_path / "absent.env")


# ---- L5 ServerSpec direct constructor still seals env via __post_init__ - #


def test_serverspec_post_init_reseals_direct_constructor_env() -> None:
    """L5: even ServerSpec(env=MappingProxyType(d)) (direct, not .create) must
    seal the env so caller mutations to `d` after construction can't leak.
    """
    from types import MappingProxyType

    mutable = {"K": "v"}
    spec = ServerSpec(command=["x"], marker="m", env=MappingProxyType(mutable))
    mutable["K"] = "MUTATED"
    assert dict(spec.env) == {"K": "v"}, "ServerSpec.env leaked through MappingProxyType view"


# ---- H4 SIGTERM install guarded to main thread ------------------------- #


def test_sigterm_install_skipped_from_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """H4: signal.signal() raises ValueError off the main thread; the manager
    must warn + skip rather than crash.
    """
    monkeypatch.setattr(ctx.subprocess, "Popen", _FakePopen)
    seen_warnings: list[Any] = []

    def worker() -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                mgr = MCPLifecycleManager("test", install_sigterm_handler=True)
                mgr.close()  # cleanup
            except ValueError:
                seen_warnings.append(("ValueError raised", None))
                return
            seen_warnings.extend(caught)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    # Manager must NOT crash; it must emit a UserWarning instead.
    sigterm_warnings = [w for w in seen_warnings if hasattr(w, "message") and "SIGTERM auto-install" in str(w.message)]
    assert sigterm_warnings, f"expected SIGTERM-skip warning from worker thread; got {seen_warnings!r}"
