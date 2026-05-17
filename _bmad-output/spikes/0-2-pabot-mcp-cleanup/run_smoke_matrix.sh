#!/usr/bin/env bash
# Story 0.2 spike — full smoke matrix: 3 modes × 3 server types × 5 iterations.
#
# Pabot config per scope (chosen to actually exercise each mode's intent):
#   scope=test    → suites/test_scope_all_16.robot (1 suite × 16 tests)
#                   + --testlevelsplit + --processes 8
#                   → 16 workers, 1 test per worker, 16 servers spawned.
#                   THIS IS THE AC-0.2.1 CONFIGURATION (architecture.md L707 mandate).
#   scope=suite   → suites/multi_suite/ (4 suites × 4 tests each = 16 tests)
#                   + NO --testlevelsplit + --processes 4
#                   → 4 workers, 4 tests per worker, 1 server per suite (4 spawned).
#                   Demonstrates suite-scope's savings vs test-scope.
#   scope=process → suites/multi_suite/ (4 suites × 4 tests each = 16 tests)
#                   + NO --testlevelsplit + --processes 4
#                   → 4 workers, 4 tests per worker, 1 server per pabot process (4 spawned).
#                   Demonstrates process-scope's savings vs test-scope.
#
# Each iter: ps snapshot BEFORE, clean prior measurements, run pabot, ps snapshot AFTER,
# diff for leaks, parse releases, append to aggregated CSV + cell_summary CSV.

# P2.13 review fix: pipefail catches python heredoc errors in the parsing pipeline.
# `-e` deliberately NOT set — pabot may exit non-zero and we want to record + continue
# (with a populated rc column per P-edge-11 review).
set -uo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
export PATH="$PWD/.venv/bin:$PATH"
export PYTHONPATH="$PWD"

ITERS=${ITERS:-5}
PYTHON="$PWD/.venv/bin/python"
PABOT="$PWD/.venv/bin/pabot"

SCOPES=("test" "suite" "process")
SERVERS=("echo_server" "rf_mcp_substitute" "slow_server")

pabot_args_for_scope() {
  case "$1" in
    test)    echo "--testlevelsplit --processes 8 suites/test_scope_all_16.robot" ;;
    suite)   echo "--processes 4 suites/multi_suite" ;;
    process) echo "--processes 4 suites/multi_suite" ;;
  esac
}

mkdir -p measurements/leak_diffs

aggregated="measurements/aggregated.csv"
echo "scope,server,iter,event,test_id,suite_id,process_lifetime_ms,shutdown_latency_ms,signaled_with,killed_by_timeout,pid" > "$aggregated"

cell_summary="measurements/cell_summary.csv"
# P-edge-11 review fix: add `rc` column so pabot crashes are distinguishable from clean runs.
# P2.10 review fix: split release_count into per-event counts so scope semantics are explicit.
# P2.2 review fix: rename startup_median_ms → process_lifetime_median_ms (the field doesn't measure startup).
echo "scope,server,iter,pabot_rc,wall_time_s,tests_passed,acquire_count,release_test_count,release_suite_count,shutdown_all_count,acquire_failed_count,shutdown_median_ms,shutdown_p95_ms,shutdown_max_ms,process_lifetime_median_ms,process_lifetime_p95_ms,leaks_after,killed_by_timeout_count" > "$cell_summary"

leak_marker_re="SPIKE-0-2-(ECHO|SLOW|RFMCPSUB)"

ps_snapshot() {
  ps -eo pid,ppid,comm,args 2>/dev/null | grep -E "$leak_marker_re" | grep -v grep || true
}

count_marker_processes() {
  ps -eo pid,args 2>/dev/null | grep -E "$leak_marker_re" | grep -v grep | wc -l
}

sleep 0.5

for scope in "${SCOPES[@]}"; do
  for server in "${SERVERS[@]}"; do
    cell_dir="measurements/cell_${scope}_${server}"
    mkdir -p "$cell_dir"
    pabot_args=$(pabot_args_for_scope "$scope")
    echo ""
    echo "=== CELL: scope=$scope server=$server pabot_args=$pabot_args ==="

    for i in $(seq 1 $ITERS); do
      iter_dir="$cell_dir/iter_${i}"
      rm -rf "$iter_dir" pabot_results measurements/raw_*.jsonl
      mkdir -p "$iter_dir"

      # P2.1 review fix: re-snapshot baseline AT THE START OF EACH ITER, not once at
      # script start. This prevents cross-cell contamination if a prior iter leaked.
      sleep 0.2
      iter_baseline=$(count_marker_processes)
      ps_snapshot > "measurements/leak_diffs/${scope}_${server}_iter${i}_BEFORE.txt"

      START=$(date +%s.%N)
      "$PABOT" \
        --listener "mcp_listener.MCPCleanupListener:${scope}:${server}" \
        --outputdir pabot_results \
        $pabot_args > "$iter_dir/pabot_stdout.log" 2>&1
      RC=$?
      END=$(date +%s.%N)
      ELAPSED=$(echo "$END - $START" | bc)

      mv measurements/raw_*.jsonl "$iter_dir/" 2>/dev/null || true
      cp pabot_results/output.xml "$iter_dir/output.xml" 2>/dev/null || true

      sleep 0.3
      ps_snapshot > "measurements/leak_diffs/${scope}_${server}_iter${i}_AFTER.txt"
      after_count=$(count_marker_processes)
      leaks=$((after_count - iter_baseline))
      if [ "$leaks" -lt 0 ]; then leaks=0; fi

      # P2.18 review fix: read pass count from RF's output.xml when available — it has a
      # definitive total via the <stat all="..." pass="..."> tag. Fall back to stdout parse
      # only when output.xml is missing (pabot crashed).
      pass_fail=0
      if [ -f "$iter_dir/output.xml" ]; then
        pass_fail=$("$PYTHON" -c "
import xml.etree.ElementTree as ET
t = ET.parse('$iter_dir/output.xml').getroot()
stat = t.find('.//statistics/total/stat')
print(stat.get('pass') if stat is not None else 0)
" 2>/dev/null || echo 0)
      fi
      pass_fail=${pass_fail:-0}

      acquire_count=0
      acquire_failed_count=0
      release_test_count=0
      release_suite_count=0
      shutdown_all_count=0
      shutdown_median="?"
      shutdown_p95="?"
      shutdown_max="?"
      lifetime_median="?"
      lifetime_p95="?"
      ktimeout=0

      if ls "$iter_dir"/raw_*.jsonl >/dev/null 2>&1; then
        cat "$iter_dir"/raw_*.jsonl | "$PYTHON" -c "
import sys, json, csv, statistics
from collections import Counter
recs = [json.loads(l) for l in sys.stdin if l.strip()]
out_path = '$aggregated'
scope = '$scope'
server = '$server'
i = $i
with open(out_path, 'a', newline='') as f:
    w = csv.writer(f)
    for r in recs:
        w.writerow([
            scope, server, i, r.get('event'),
            r.get('test_id', ''), r.get('suite_id', ''),
            f\"{r.get('process_lifetime_ms', 0):.3f}\",
            f\"{r.get('shutdown_latency_ms', 0):.3f}\",
            r.get('signaled_with', ''),
            int(bool(r.get('killed_by_timeout'))),
            r.get('pid', ''),
        ])
# Only release/shutdown events have latencies; acquire events do not.
release_recs = [r for r in recs if r.get('event') in ('release_test', 'release_suite', 'shutdown_all')]
shut = sorted(r['shutdown_latency_ms'] for r in release_recs)
life = sorted(r['process_lifetime_ms'] for r in release_recs)
def pct(xs, p):
    if not xs: return 0.0
    k = max(0, min(len(xs)-1, int(round((p/100.0) * (len(xs)-1)))))
    return xs[k]
event_counts = Counter(r.get('event') for r in recs)
print(f'ACQUIRE_COUNT={event_counts[\"acquire\"]}')
print(f'ACQUIRE_FAILED_COUNT={event_counts[\"acquire_failed\"]}')
print(f'RELEASE_TEST_COUNT={event_counts[\"release_test\"]}')
print(f'RELEASE_SUITE_COUNT={event_counts[\"release_suite\"]}')
print(f'SHUTDOWN_ALL_COUNT={event_counts[\"shutdown_all\"]}')
print(f'SHUT_MED={statistics.median(shut) if shut else 0:.3f}')
print(f'SHUT_P95={pct(shut, 95):.3f}')
print(f'SHUT_MAX={max(shut) if shut else 0:.3f}')
print(f'LIFE_MED={statistics.median(life) if life else 0:.3f}')
print(f'LIFE_P95={pct(life, 95):.3f}')
print(f'KTIMEOUT={sum(1 for r in release_recs if r.get(\"killed_by_timeout\"))}')
" > "$iter_dir/stats.txt"
        acquire_count=$(grep "^ACQUIRE_COUNT=" "$iter_dir/stats.txt" | cut -d= -f2)
        acquire_failed_count=$(grep "^ACQUIRE_FAILED_COUNT=" "$iter_dir/stats.txt" | cut -d= -f2)
        release_test_count=$(grep RELEASE_TEST_COUNT "$iter_dir/stats.txt" | cut -d= -f2)
        release_suite_count=$(grep RELEASE_SUITE_COUNT "$iter_dir/stats.txt" | cut -d= -f2)
        shutdown_all_count=$(grep SHUTDOWN_ALL_COUNT "$iter_dir/stats.txt" | cut -d= -f2)
        shutdown_median=$(grep SHUT_MED "$iter_dir/stats.txt" | cut -d= -f2)
        shutdown_p95=$(grep SHUT_P95 "$iter_dir/stats.txt" | cut -d= -f2)
        shutdown_max=$(grep SHUT_MAX "$iter_dir/stats.txt" | cut -d= -f2)
        lifetime_median=$(grep LIFE_MED "$iter_dir/stats.txt" | cut -d= -f2)
        lifetime_p95=$(grep LIFE_P95 "$iter_dir/stats.txt" | cut -d= -f2)
        ktimeout=$(grep KTIMEOUT "$iter_dir/stats.txt" | cut -d= -f2)
      fi

      total_releases=$((release_test_count + release_suite_count + shutdown_all_count))
      printf '%s,%s,%d,%d,%.2f,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
        "$scope" "$server" "$i" "$RC" "$ELAPSED" "$pass_fail" \
        "$acquire_count" "$release_test_count" "$release_suite_count" "$shutdown_all_count" "$acquire_failed_count" \
        "$shutdown_median" "$shutdown_p95" "$shutdown_max" \
        "$lifetime_median" "$lifetime_p95" "$leaks" "$ktimeout" >> "$cell_summary"

      printf 'iter %d: rc=%s wall=%6.2fs pass=%s/16 acq=%s rt=%s rs=%s sa=%s aF=%s shut_med=%6sms shut_p95=%6sms shut_max=%6sms leaks=%s\n' \
        "$i" "$RC" "$ELAPSED" "$pass_fail" \
        "$acquire_count" "$release_test_count" "$release_suite_count" "$shutdown_all_count" "$acquire_failed_count" \
        "$shutdown_median" "$shutdown_p95" "$shutdown_max" "$leaks"

      sleep 0.2
    done
  done
done

echo ""
echo "=== MATRIX COMPLETE ==="
echo "aggregated CSV: $aggregated"
echo "cell summary CSV: $cell_summary"
echo "leak diffs at: measurements/leak_diffs/"
