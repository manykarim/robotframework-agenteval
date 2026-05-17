#!/usr/bin/env bash
# D2.4 atexit failsafe probe — Story 0.2 code review follow-up.
#
# Per D2.2 review decision (2026-05-17), Python atexit does NOT run on SIGKILL of the parent.
# This probe explicitly tests the verdict's documented coverage scope:
#   SIGTERM-of-parent → atexit fires → MCP grandchildren reaped (PASS expected)
#   SIGKILL-of-parent → atexit does NOT fire → MCP grandchildren orphaned to PID 1 (gap expected)
#
# Outputs:
#   measurements/atexit_probe/<scenario>_iter<N>/leak_before.txt
#   measurements/atexit_probe/<scenario>_iter<N>/leak_after.txt
#   measurements/atexit_probe/<scenario>_iter<N>/result.txt
#   measurements/atexit_probe/summary.csv

set -uo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH="$PWD"

ITERS=${ITERS:-3}
PYTHON="$PWD/.venv/bin/python"

OUT_DIR=measurements/atexit_probe
mkdir -p "$OUT_DIR"
SUMMARY="$OUT_DIR/summary.csv"
echo "scenario,iter,signal_used,leak_count,parent_exit_code,result" > "$SUMMARY"

count_marker_processes() {
  # pgrep matches its own command line, so use ps + explicit filter that excludes
  # the bash/ps/grep invocations themselves. The MCP server processes are python
  # interpreters with SPIKE-0-2- in argv tail; the ps command itself has no python.
  ps -eo pid,comm,args 2>/dev/null \
    | grep -E "SPIKE-0-2-" \
    | grep -v grep \
    | grep -v "ps -eo" \
    | grep -E "^[[:space:]]*[0-9]+[[:space:]]+python" \
    | wc -l
}

# Helper: build a tiny python harness that spawns 3 MCP server subprocesses via the
# lifecycle manager, then waits for a signal. We test SIGTERM (atexit should fire) and
# SIGKILL (atexit should NOT fire — expected leak per D2.2).
HARNESS_SCRIPT="$OUT_DIR/_harness.py"
cat > "$HARNESS_SCRIPT" <<'PY'
"""Atexit-probe harness — spawns 3 MCP servers via MCPLifecycleManager, then waits.

INSTALL_SIGTERM_HANDLER env var controls whether SIGTERM is converted to sys.exit:
    INSTALL_SIGTERM_HANDLER=1 → install a signal handler that calls sys.exit(0)
        Production pattern. atexit will fire. MCP grandchildren should be reaped.
    INSTALL_SIGTERM_HANDLER=0 → use Python's default SIGTERM handler
        Process dies without running atexit. MCP grandchildren leak.

This distinguishes 'atexit infrastructure works' from 'the verdict's defense-in-depth
claim requires a signal handler to be installed at the listener layer.'
"""
import os
import signal
import sys
import time
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent.parent.parent  # measurements/atexit_probe → spike dir
sys.path.insert(0, str(SPIKE_DIR))

from context_prototype import MCPLifecycleManager, ServerSpec

# INSTALL_SIGTERM_HANDLER controls both:
#  (a) MCPLifecycleManager's auto-installed handler (install_sigterm_handler kwarg)
#  (b) any extra harness-level handler (none here; the manager's is sufficient)
# Setting "0" disables the auto-install so scenario B can demonstrate the "without handler, leaks" case.
install_handler = os.environ.get("INSTALL_SIGTERM_HANDLER", "1") == "1"

spec = ServerSpec(
    command=[sys.executable, "-m", "servers.echo_server"],
    marker="SPIKE-0-2-ECHO",
)
mgr = MCPLifecycleManager(scope="test", default_spec=spec, install_sigterm_handler=install_handler)

for i in range(3):
    mgr.acquire(test_id=f"atexit-probe-{i}", suite_id="atexit-probe-suite")

sys.stdout.write(f"HARNESS_READY pid={os.getpid()}\n")
sys.stdout.flush()
time.sleep(60)
PY

run_one() {
  local scenario=$1
  local signal=$2
  local install_handler=$3
  local iter=$4
  local cell_dir="$OUT_DIR/${scenario}_iter${iter}"
  mkdir -p "$cell_dir"

  sleep 0.3
  local before=$(count_marker_processes)
  pgrep -af "SPIKE-0-2-" > "$cell_dir/leak_before.txt" 2>/dev/null || true

  INSTALL_SIGTERM_HANDLER=$install_handler \
    "$PYTHON" "$HARNESS_SCRIPT" > "$cell_dir/harness_stdout.txt" 2> "$cell_dir/harness_stderr.txt" &
  local harness_pid=$!

  # Wait for HARNESS_READY signal in stdout
  local deadline=$(($(date +%s) + 5))
  while [ $(date +%s) -lt $deadline ]; do
    if grep -q HARNESS_READY "$cell_dir/harness_stdout.txt" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done

  # Verify ready
  if ! grep -q HARNESS_READY "$cell_dir/harness_stdout.txt" 2>/dev/null; then
    echo "iter $iter [$scenario]: harness did NOT report ready in 5s" | tee "$cell_dir/result.txt"
    kill -KILL $harness_pid 2>/dev/null || true
    return
  fi

  # Send the signal
  kill -"$signal" $harness_pid

  # Wait for harness to exit (atexit may take a moment to run)
  local exit_deadline=$(($(date +%s) + 10))
  while kill -0 $harness_pid 2>/dev/null; do
    if [ $(date +%s) -ge $exit_deadline ]; then
      kill -KILL $harness_pid 2>/dev/null || true
      break
    fi
    sleep 0.1
  done
  wait $harness_pid 2>/dev/null
  local rc=$?

  # Allow time for grandchildren to be reaped (if SIGTERM path worked)
  sleep 0.5

  # Count leaks
  local after=$(count_marker_processes)
  pgrep -af "SPIKE-0-2-" > "$cell_dir/leak_after.txt" 2>/dev/null || true
  local leaks=$((after - before))
  if [ "$leaks" -lt 0 ]; then leaks=0; fi

  local result
  if [ "$leaks" -eq 0 ]; then
    result="CLEAN (no leaks)"
  else
    result="LEAKED $leaks (orphaned to PID 1)"
    # Best-effort: SIGTERM any leaked processes so they don't pollute subsequent iters.
    pkill -TERM -f "SPIKE-0-2-" 2>/dev/null || true
    sleep 0.3
  fi

  echo "iter $iter [$scenario] signal=$signal: harness_exit_rc=$rc leaks=$leaks → $result" \
    | tee "$cell_dir/result.txt"
  printf '%s,%d,%s,%d,%d,%s\n' "$scenario" "$iter" "$signal" "$leaks" "$rc" "$result" >> "$SUMMARY"
}

echo "=== D2.4 atexit failsafe probe ==="
echo ""
echo "scenario A: SIGTERM + signal handler installed (atexit fires; expect zero leaks)"
echo "    Production pattern — Story 1b.1 production code MUST install this handler."
for i in $(seq 1 $ITERS); do
  run_one "sigterm_with_handler" TERM 1 $i
done

echo ""
echo "scenario B: SIGTERM + default handler (Python dies w/o atexit; leaks expected)"
echo "    Demonstrates the production-pattern requirement — without the handler, atexit is bypassed."
for i in $(seq 1 $ITERS); do
  run_one "sigterm_default" TERM 0 $i
done

echo ""
echo "scenario C: SIGKILL (atexit CANNOT fire — kernel bypass; leaks always)"
echo "    Unrecoverable at listener layer per D2.2 verdict-text fix."
for i in $(seq 1 $ITERS); do
  run_one "sigkill_parent" KILL 0 $i
done

echo ""
echo "=== ATEXIT PROBE COMPLETE ==="
echo "summary: $SUMMARY"
cat "$SUMMARY"
