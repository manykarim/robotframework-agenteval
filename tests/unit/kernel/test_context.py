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
import threading
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
        if self._returncode is None:
            self._returncode = 0  # synthesize clean exit
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
    mgr = MCPLifecycleManager("suite", default_spec=_default_spec())
    mgr.acquire(test_id="t1", suite_id="s1")
    mgr.acquire(test_id="t2", suite_id="s1")
    mgr.acquire(test_id="t3", suite_id="s2")
    results = mgr.release_suite("s1")
    assert len(results) == 2


def test_mcplifecyclemanager_shutdown_all_drains_everything(
    _patched_subprocess: dict[str, Any],
) -> None:
    mgr = MCPLifecycleManager("process", default_spec=_default_spec())
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


def test_mcplifecyclemanager_installs_sigterm_handler_by_default(
    _patched_subprocess: dict[str, Any],
) -> None:
    """D2.4 LOAD-BEARING: __init__ MUST install a SIGTERM→sys.exit handler by
    default. Verifies signal.signal was called with SIGTERM.
    """
    MCPLifecycleManager("test")
    signal_calls = _patched_subprocess["signal_calls"]
    assert any(sig == signal.SIGTERM for sig, _ in signal_calls)


def test_mcplifecyclemanager_install_sigterm_handler_false_skips_install(
    _patched_subprocess: dict[str, Any],
) -> None:
    MCPLifecycleManager("test", install_sigterm_handler=False)
    signal_calls = _patched_subprocess["signal_calls"]
    assert not any(sig == signal.SIGTERM for sig, _ in signal_calls)


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
    cfg = resolve_config({}, dotenv_path=Path("/nonexistent/.env"))
    expected_keys = {
        "provider",
        "telemetry",
        "trace_backend",
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


def test_resolve_config_kwarg_none_falls_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A kwarg explicitly set to None must NOT shadow env-var; it falls through."""
    monkeypatch.setenv("AGENTEVAL_PROVIDER", "from-env")
    cfg = resolve_config({"provider": None}, dotenv_path=tmp_path / "absent.env")
    assert cfg["provider"] == "from-env"


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
