"""Unit tests for _kernel/run_async.py (AC-1b.1.7).

Covers:
- Sync-context invocation returns expected value.
- Nested-loop fallback path (worker-thread).
- Exception propagation across the thread boundary.
"""

from __future__ import annotations

import asyncio

import pytest

from AgentEval._kernel.run_async import _run_async

# ---- AC-1b.1.7: sync-context invocation ---------------------------------- #


def test_run_async_sync_context_returns_value() -> None:
    async def coro() -> int:
        return 42

    assert _run_async(coro()) == 42


def test_run_async_sync_context_preserves_type() -> None:
    async def coro() -> dict[str, int]:
        return {"a": 1, "b": 2}

    result = _run_async(coro())
    assert result == {"a": 1, "b": 2}


# ---- AC-1b.1.7: exception propagation ----------------------------------- #


def test_run_async_propagates_exception_from_coro() -> None:
    async def coro() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        _run_async(coro())


# ---- AC-1b.1.7: nested-loop fallback ------------------------------------ #


def test_run_async_nested_loop_fallback() -> None:
    """When called from inside a running event loop, _run_async uses a worker
    thread so the call still completes synchronously without RuntimeError.
    """

    async def inner() -> int:
        return 7

    async def outer() -> int:
        # Inside a running loop now; _run_async must NOT call asyncio.run() directly.
        return _run_async(inner())

    # asyncio.run sets up an active event loop for `outer`. If _run_async tried
    # asyncio.run() inside it, we'd get "asyncio.run() cannot be called from a
    # running event loop". The thread fallback prevents that.
    assert asyncio.run(outer()) == 7


def test_run_async_nested_loop_propagates_exception() -> None:
    async def inner() -> None:
        raise RuntimeError("nested boom")

    async def outer() -> None:
        _run_async(inner())

    with pytest.raises(RuntimeError, match="nested boom"):
        asyncio.run(outer())
