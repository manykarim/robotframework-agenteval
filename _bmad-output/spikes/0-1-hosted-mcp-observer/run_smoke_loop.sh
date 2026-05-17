#!/usr/bin/env bash
# Story 0.1 spike — 5-iteration pabot smoke loop with per-iteration evidence preserved.
# Per P3 (review): prior version wiped pabot_evidence/ between iters, losing 4 of 5 runs'
# evidence. This script preserves each iteration to pabot_evidence/iter_N/.
#
# Output: measurements/smoke_loop.txt (timing + pass/fail summary)
#         concurrency/pabot_evidence/iter_{1..5}/worker_pid*.jsonl
#         concurrency/pabot_evidence/iter_{1..5}/output.xml

set -e
cd "$(dirname "$0")"
# Force C locale so printf %.2f uses '.' not ',' (German locale issue)
export LC_ALL=C

ITERS=${ITERS:-5}
PROCESSES=${PROCESSES:-4}
OUTFILE=measurements/smoke_loop.txt

mkdir -p concurrency/pabot_evidence measurements
# Clean residual JSONL before iter 1 so per-iter counts are clean.
rm -f concurrency/pabot_evidence/*.jsonl
: > "$OUTFILE"
echo "=== Story 0.1 5-iter pabot smoke loop (--processes $PROCESSES) ===" >> "$OUTFILE"
echo "started: $(date -Iseconds)" >> "$OUTFILE"
echo "" >> "$OUTFILE"

total_pass=0
total_fail=0
for i in $(seq 1 $ITERS); do
  iter_dir=concurrency/pabot_evidence/iter_$i
  rm -rf "$iter_dir" concurrency/pabot_results
  mkdir -p "$iter_dir"

  START=$(date +%s.%N)
  PATH="$PWD/.venv/bin:$PATH" .venv/bin/pabot \
    --testlevelsplit \
    --processes $PROCESSES \
    --outputdir concurrency/pabot_results \
    concurrency/test_pabot.robot > "$iter_dir/pabot_stdout.log" 2>&1
  END=$(date +%s.%N)
  ELAPSED=$(echo "$END - $START" | bc)

  # Move JSONL evidence into per-iter dir
  mv concurrency/pabot_evidence/worker_pid*.jsonl "$iter_dir/" 2>/dev/null || true
  cp concurrency/pabot_results/output.xml "$iter_dir/output.xml" 2>/dev/null || true

  # Parse iteration result
  PASS_FAIL=$(grep -E "tests,.*passed" "$iter_dir/pabot_stdout.log" | tail -1)
  RUNS=$(cat "$iter_dir"/worker_pid*.jsonl 2>/dev/null | wc -l)
  TOOLCALLS=$(cat "$iter_dir"/worker_pid*.jsonl 2>/dev/null | .venv/bin/python -c "
import sys, json
print(sum(json.loads(l)['tool_call_count'] for l in sys.stdin if l.strip()))
" 2>/dev/null || echo "?")
  COV=$(cat "$iter_dir"/worker_pid*.jsonl 2>/dev/null | .venv/bin/python -c "
import sys, json
from collections import Counter
recs = [json.loads(l) for l in sys.stdin if l.strip()]
c = Counter(r['mcp_coverage'] for r in recs)
print(','.join(f'{k}={v}' for k, v in sorted(c.items())))
" 2>/dev/null || echo "?")

  printf 'iter %d: %s wall=%.2fs runs=%s tool_calls=%s coverages=[%s]\n' \
    "$i" "$PASS_FAIL" "$ELAPSED" "$RUNS" "$TOOLCALLS" "$COV" | tee -a "$OUTFILE"
done

echo "" >> "$OUTFILE"
echo "completed: $(date -Iseconds)" >> "$OUTFILE"
echo "evidence preserved at: concurrency/pabot_evidence/iter_{1..$ITERS}/" >> "$OUTFILE"
echo "" >> "$OUTFILE"
cat "$OUTFILE"
