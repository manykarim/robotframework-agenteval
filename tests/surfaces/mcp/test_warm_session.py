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

"""Warm-session reuse: one server spawn across connect + N ops, clean teardown."""

from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from MCPLibrary import MCPLibrary, _lifecycle

from ._helpers import build_echo_server

_MARKER_SERVER = str(Path(__file__).with_name("_stdio_marker_server.py"))


def _warm_thread_names() -> list[str]:
    """Names of live background threads this library spawns for warm sessions."""
    return [t.name for t in threading.enumerate() if t.name.startswith("mcp-warm-")]


def _pid_alive(pid: int) -> bool:
    """True while ``pid`` still exists (a reaped subprocess reports False)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_until_gone(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


class CountingFactory:
    """Wraps the in-memory server factory and counts how often it is opened.

    Each ``_open_session`` for the ``in_memory`` transport invokes the factory
    exactly once, so the call count is the number of distinct server sessions
    spawned - the warm path must open exactly one across many operations.
    """

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> Any:
        self.count += 1
        return build_echo_server()


@pytest.fixture
def lib() -> Iterator[MCPLibrary]:
    """A library instance whose warm sessions are always torn down after."""
    instance = MCPLibrary()
    handles: list[Any] = []
    orig = instance.start_server

    def _tracking_start(*args: Any, **kwargs: Any) -> Any:
        handle = orig(*args, **kwargs)
        handles.append(handle)
        return handle

    instance.start_server = _tracking_start  # type: ignore[method-assign]
    try:
        yield instance
    finally:
        # Teardown runs even if the test body raised, so no session, thread, or
        # subprocess leaks into the rest of the suite.
        for handle in handles:
            with contextlib.suppress(Exception):  # best-effort cleanup
                instance.stop_server(handle)


def test_in_memory_warm_session_opens_server_exactly_once(lib: MCPLibrary) -> None:
    factory = CountingFactory()
    handle = lib.start_server("echo", "in_memory", server_factory=factory)

    session = lib.connect_to_server(handle)
    assert session.protocol_version
    # After connect, a warm session is registered for this handle.
    assert _lifecycle._get_warm(handle) is not None

    tools_first = lib.list_tools(handle)
    tools_second = lib.list_tools(handle)
    assert {t.name for t in tools_first} == {t.name for t in tools_second} == {"echo_back", "search"}

    r1 = lib.call_tool(handle, "echo_back", text="one")
    r2 = lib.call_tool(handle, "search", query="two")
    assert r1.is_error is False and r2.is_error is False
    assert any("one" in (b.get("text") or "") for b in r1.content)
    assert any("two" in (b.get("text") or "") for b in r2.content)

    # Connect + 2 List + 2 Call = 5 operations, but only ONE server open.
    assert factory.count == 1, f"expected a single warm open, saw {factory.count}"

    lib.stop_server(handle)
    assert _lifecycle._get_warm(handle) is None
    # Idempotent stop must not reopen or raise.
    lib.stop_server(handle)
    assert factory.count == 1


def test_in_memory_cold_path_opens_per_op_without_connect(lib: MCPLibrary) -> None:
    # Backward compatibility: List/Call without a prior Connect still work, and
    # (by contrast with the warm path) open a fresh session per operation.
    factory = CountingFactory()
    handle = lib.start_server("echo", "in_memory", server_factory=factory)

    lib.list_tools(handle)
    lib.list_tools(handle)
    lib.call_tool(handle, "echo_back", text="hi")

    assert factory.count == 3
    assert _lifecycle._get_warm(handle) is None


def test_reconnect_replaces_warm_session(lib: MCPLibrary) -> None:
    factory = CountingFactory()
    handle = lib.start_server("echo", "in_memory", server_factory=factory)

    lib.connect_to_server(handle)
    first_warm = _lifecycle._get_warm(handle)
    lib.connect_to_server(handle)
    second_warm = _lifecycle._get_warm(handle)

    assert first_warm is not None and second_warm is not None
    assert first_warm is not second_warm  # old session was torn down + replaced
    assert factory.count == 2


def test_use_after_stop_raises_structured_error(lib: MCPLibrary) -> None:
    factory = CountingFactory()
    handle = lib.start_server("echo", "in_memory", server_factory=factory)
    lib.connect_to_server(handle)
    warm = _lifecycle._get_warm(handle)
    assert warm is not None

    # Close the underlying warm session but leave it registered, then prove a
    # dispatched op fails loudly instead of hanging.
    warm.close()
    with pytest.raises(_lifecycle.MCPError):
        warm.list_tools()


def test_stdio_single_spawn_and_teardown(lib: MCPLibrary, tmp_path: Path) -> None:
    marker = tmp_path / "spawns.log"
    env = {**os.environ, "MCP_SPAWN_MARKER": str(marker)}
    handle = lib.start_server(
        "marker",
        "stdio",
        command=sys.executable,
        args=[_MARKER_SERVER],
        env=env,
    )

    threads_before = set(threading.enumerate())

    session = lib.connect_to_server(handle)
    assert session.protocol_version
    assert session.transport == "stdio"

    tools = lib.list_tools(handle)
    assert "echo_back" in {t.name for t in tools}
    lib.list_tools(handle)

    r1 = lib.call_tool(handle, "echo_back", text="alpha")
    r2 = lib.call_tool(handle, "echo_back", text="beta")
    assert any("alpha" in (b.get("text") or "") for b in r1.content)
    assert any("beta" in (b.get("text") or "") for b in r2.content)

    # The marker file has exactly one line: one subprocess spawned across the
    # whole Connect + 2 List + 2 Call sequence.
    lines = [ln for ln in marker.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one server spawn, saw {len(lines)}: {lines!r}"
    child_pid = int(lines[0])
    assert _pid_alive(child_pid), "server subprocess should be alive before Stop Server"
    assert _warm_thread_names(), "warm loop thread should be alive while connected"

    lib.stop_server(handle)

    # After Stop Server: subprocess reaped, loop thread joined, session gone.
    assert _wait_until_gone(child_pid), f"subprocess {child_pid} leaked after Stop Server"
    assert _lifecycle._get_warm(handle) is None
    assert not _warm_thread_names(), "warm loop thread leaked after Stop Server"
    # No stray threads left behind relative to the start of the test.
    leaked = {t for t in threading.enumerate() if t not in threads_before and t.name.startswith("mcp-warm-")}
    assert not leaked, f"leaked warm threads: {[t.name for t in leaked]}"
