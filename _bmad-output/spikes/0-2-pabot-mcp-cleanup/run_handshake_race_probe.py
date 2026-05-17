"""D2.3 handshake-race probe — Story 0.2 code review follow-up.

Architecture.md L710 names "SIGTERM-race conditions during cleanup" as the slow-server
failure mode to probe. The original `slow_server.py` (with `time.sleep(2.0)` BEFORE
`stdio_server`) only validates SIGTERM-during-sleep, NOT SIGTERM-during-MCP-handshake
(the actually-load-bearing case for Epic 5 Story 5.2's stdio_client.initialize).

This probe explicitly:
1. Spawns `slow_server.py` (which sleeps 2s before opening stdio).
2. Starts an MCP handshake (`stdio_client(...)` + `ClientSession.initialize()`) — this
   call BLOCKS waiting for the subprocess's stdio_server to come up.
3. After a configurable delay (default 0.5s — well within the subprocess's 2s sleep),
   SIGTERMs the subprocess's process group.
4. Records:
   - whether initialize() raised, returned, or hung past the deadline
   - whether the subprocess actually died (poll() check + ps grep)
   - shutdown latency from SIGTERM to process exit
   - any orphan processes left on the host

Run 5 iterations and aggregate. Outputs `measurements/handshake_race/results.jsonl`.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SPIKE_DIR))

from mcp import StdioServerParameters  # noqa: E402
from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


SIGTERM_DELAY_S = float(os.environ.get("SIGTERM_DELAY_S", "0.5"))
HANDSHAKE_DEADLINE_S = float(os.environ.get("HANDSHAKE_DEADLINE_S", "5.0"))


async def run_one_iter(iter_id: int) -> dict:
    """Spawn slow_server, start initialize() handshake, SIGTERM mid-handshake, measure."""
    # Build the Popen command directly (NOT through stdio_client) so we can SIGTERM
    # the subprocess at a precise moment. We do the stdio handshake manually-ish.
    cmd = [sys.executable, "-m", "servers.slow_server", "SPIKE-0-2-SLOW"]
    env = os.environ.copy()

    stderr_path = SPIKE_DIR / "measurements" / "handshake_race" / f"iter{iter_id}.stderr"
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_file = open(stderr_path, "w", encoding="utf-8")

    params = StdioServerParameters(command=cmd[0], args=cmd[1:], env=env)

    spawn_time = time.time()
    sigterm_time = None
    handshake_completed_at = None
    handshake_error = None
    process_pid = None
    process_alive_at_sigterm = None
    final_poll = None

    # Run stdio_client with a manual cancel after SIGTERM_DELAY_S. We need to peek at
    # the subprocess pid; mcp.client.stdio doesn't expose it directly via the public API,
    # so we spawn the process ourselves and feed its stdio to ClientSession.
    # Actually the cleanest path: use stdio_client AND watch for it. mcp's stdio_client
    # spawns the subprocess; on cancel, it tears down via its async context manager.

    cancel_scope_task = None

    async def sigterm_after_delay(pid_holder: dict):
        await asyncio.sleep(SIGTERM_DELAY_S)
        nonlocal sigterm_time, process_alive_at_sigterm
        sigterm_time = time.time()
        if pid_holder.get("pid") is not None:
            try:
                # SIGTERM the process group
                os.killpg(pid_holder["pid"], signal.SIGTERM)
                process_alive_at_sigterm = True
            except ProcessLookupError:
                process_alive_at_sigterm = False

    async def handshake():
        nonlocal handshake_completed_at, handshake_error, process_pid
        pid_holder: dict = {"pid": None}
        # Start the SIGTERM timer immediately
        sigterm_task = asyncio.create_task(sigterm_after_delay(pid_holder))
        try:
            async with stdio_client(params, errlog=stderr_file) as (read, write):
                # We don't have direct access to the subprocess pid through stdio_client's
                # public API, but the subprocess was just spawned — `pgrep -f` for our marker
                # finds it. This is a brief sync syscall, acceptable here.
                pgrep = subprocess.run(
                    ["pgrep", "-f", "SPIKE-0-2-SLOW"],
                    capture_output=True, text=True, timeout=1.0,
                )
                for line in pgrep.stdout.strip().splitlines():
                    if line.strip().isdigit():
                        process_pid = int(line.strip())
                        pid_holder["pid"] = process_pid
                        break

                async with ClientSession(
                    read, write, read_timeout_seconds=timedelta(seconds=HANDSHAKE_DEADLINE_S)
                ) as session:
                    await asyncio.wait_for(session.initialize(), timeout=HANDSHAKE_DEADLINE_S)
                    handshake_completed_at = time.time()
        except Exception as exc:
            handshake_error = f"{type(exc).__name__}: {exc}"
        finally:
            await sigterm_task

    try:
        await asyncio.wait_for(handshake(), timeout=HANDSHAKE_DEADLINE_S + 2.0)
    except asyncio.TimeoutError:
        handshake_error = handshake_error or "outer wait_for timeout"

    # Verify process actually died — wait up to 2s for it to exit
    process_exit_at = None
    if process_pid is not None:
        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                os.kill(process_pid, 0)
                await asyncio.sleep(0.05)
            except ProcessLookupError:
                process_exit_at = time.time()
                final_poll = "exited"
                break
        else:
            final_poll = "still-alive"

    stderr_file.close()

    return {
        "iter": iter_id,
        "spawn_unix": spawn_time,
        "sigterm_unix": sigterm_time,
        "sigterm_delay_target_s": SIGTERM_DELAY_S,
        "handshake_deadline_s": HANDSHAKE_DEADLINE_S,
        "process_pid": process_pid,
        "process_alive_at_sigterm": process_alive_at_sigterm,
        "handshake_completed_at_unix": handshake_completed_at,
        "handshake_error": handshake_error,
        "shutdown_latency_ms": (
            (process_exit_at - sigterm_time) * 1000
            if (process_exit_at is not None and sigterm_time is not None)
            else None
        ),
        "final_poll": final_poll,
    }


async def main() -> int:
    out_dir = SPIKE_DIR / "measurements" / "handshake_race"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.jsonl"
    if out_path.exists():
        out_path.unlink()

    n_iters = int(os.environ.get("HANDSHAKE_ITERS", "5"))
    leaks = 0
    for i in range(1, n_iters + 1):
        # Baseline ps count BEFORE iter
        before = subprocess.run(
            ["pgrep", "-fc", "SPIKE-0-2-SLOW"],
            capture_output=True, text=True,
        )
        before_n = int(before.stdout.strip() or "0")

        result = await run_one_iter(i)

        # Post-iter check
        await asyncio.sleep(0.3)
        after = subprocess.run(
            ["pgrep", "-fc", "SPIKE-0-2-SLOW"],
            capture_output=True, text=True,
        )
        after_n = int(after.stdout.strip() or "0")
        iter_leak = max(0, after_n - before_n)
        leaks += iter_leak

        result["pre_iter_ps_count"] = before_n
        result["post_iter_ps_count"] = after_n
        result["leak_count"] = iter_leak

        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")

        print(
            f"iter {i}: sigterm@{SIGTERM_DELAY_S}s "
            f"handshake_err={'YES' if result['handshake_error'] else 'no'} "
            f"final_poll={result['final_poll']} "
            f"shutdown_ms={result['shutdown_latency_ms']!r} "
            f"leak={iter_leak}"
        )

    print(f"\ntotal leaks across {n_iters} iters: {leaks}")
    print(f"out: {out_path}")
    return 0 if leaks == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
