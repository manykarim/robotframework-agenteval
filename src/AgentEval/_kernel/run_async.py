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

"""Async-to-sync bridge per ADR-012 (was ADR-A1).

Every keyword method that calls async libraries (MCP client, LiteLLM async paths,
OTel async exporter, coding-agent SDK async APIs) goes through `_run_async()`.
No direct `asyncio.run()` calls in sub-library code. No `async def` keyword
methods.

`_run_async` handles the nested-event-loop case (IDE runners, nested test
executions) by running the coroutine in a fresh worker thread that owns its own
event loop. No `nest_asyncio` import is required.

See `architecture.md` §Async-to-Sync Bridge Convention (L932-966) for the
convention this module implements, plus `docs/adr/ADR-012-async-to-sync-bridge-kernel-module.md`
for the ratified decision (M4 review fix: filename was previously cited as
`ADR-012-async-bridge-kernel.md`, which doesn't exist on disk).

ContextVar propagation (H6 review fix): when the nested-loop fallback path
fires, the worker thread runs the coroutine inside `contextvars.copy_context()`
so the caller's `_kernel/context.TestContext` binding (and any other ContextVar
state) is preserved across the thread boundary. Without this, the architecture's
per-test `test_id` propagation contract silently breaks in IDE-runner / nested-loop
scenarios — exactly where this module is intended to be used.

CI enforcement (Story 1b.6 convention test): a custom ruff/pytest rule will
scan `src/AgentEval/*/library.py` for `asyncio.run` calls — allowed only in
this module.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
from collections.abc import Coroutine
from typing import Any

__all__ = ["_run_async"]


def _run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine synchronously, with nested-event-loop fallback.

    Args:
        coro: Awaitable coroutine to run to completion.

    Returns:
        The coroutine's return value, with its original type preserved.

    Raises:
        Any exception raised by the coroutine is propagated verbatim to the
        caller (no wrapping).

    Behavior:
        - If no event loop is running in the current thread, calls
          `asyncio.run(coro)` directly (the fast path; ADR-012 §Decision).
        - If an event loop IS running (IDE runners, nested test executions),
          spawns a fresh worker thread that creates its own event loop, runs
          the coroutine inside the caller's copied ContextVar context
          (preserving per-test `test_id` propagation per H6 review fix), and
          joins back synchronously. Exception propagation is preserved via a
          one-slot exception capture across the thread boundary.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No loop running in this thread — fast path.
        return asyncio.run(coro)

    # Nested-loop fallback: spawn a thread, give it a fresh loop, join back.
    # H6: copy the caller's ContextVar context so per-test `test_id` propagation
    # (architecture L1502 / L1554 + _kernel/context.TestContext) survives the
    # thread boundary. Without this, every nested-loop call lands in a fresh
    # default Context and current_context() returns None.
    caller_ctx = contextvars.copy_context()
    result: list[T] = []
    exception: list[BaseException] = []

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            result.append(loop.run_until_complete(coro))
        except BaseException as exc:  # noqa: BLE001 — intentional re-raise across thread boundary
            exception.append(exc)
        finally:
            loop.close()

    thread = threading.Thread(target=lambda: caller_ctx.run(_runner), daemon=False)
    thread.start()
    thread.join()

    if exception:
        raise exception[0]
    return result[0]
