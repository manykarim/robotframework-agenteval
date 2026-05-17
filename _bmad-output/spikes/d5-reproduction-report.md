# D5 Independent Reproduction — Human Review Report

**Date:** 2026-05-17
**Methodology:** 3 independent coding agents ran reproductions of both Epic 0 spikes (Story 0.1 + Story 0.2) on this Linux host.

| Agent | Model family | Sign-off |
|---|---|---|
| Codex CLI | OpenAI (GPT-5-Codex) | **NO-GO** |
| GitHub Copilot CLI | OpenAI (GPT-5.4 via Copilot) | **NO-GO** |
| Claude Sonnet 4.6 sub-agent | Anthropic (different model from Opus 4.7 that built the spikes) | **GO WITH RESERVATIONS** |

## TL;DR in plain language

**Story 0.1 (Hosted-MCP Observer): all 3 agents say CLEAN.** The 75/75 smoke loop, the 5/5 edge cases, the coverage state breakdown, the dual-transport observer pattern — all reproduce exactly as documented. **Story 0.1 is ratifiable.**

**Story 0.2 (Per-Test MCP Cleanup): a mixed picture.**
- The two **standalone probes** (handshake-race, atexit) reproduce **cleanly** under all 3 agents. The technical findings about the auto-installed SIGTERM handler and SIGKILL being unrecoverable are confirmed.
- The **smoke matrix** (the big 45-iteration table that is the headline evidence for AC-0.2.1 "zero leaks") **does NOT reproduce cleanly** for any of the 3 agents. They each saw the same class of failures: pabot rc=252 errors on test-scope cells when run back-to-back, missing pabot output XML, and in one case actual cross-cell process leaks that contradict the "zero leaks" headline.

**The verdict's substance is still credible** — the lifecycle manager works, the auto-installed SIGTERM handler is the right answer, SIGKILL-is-unrecoverable is empirically established. But the matrix's headline claim of "45/45 clean iterations" is **not robustly reproducible**.

## What went wrong (mostly my fault, partly real)

Two distinct issues mixed together:

### Issue 1 (my methodology error)

I launched Codex and Copilot in parallel, both running `run_smoke_matrix.sh` concurrently in the same workspace. The script writes to a single `measurements/raw_*.jsonl` path and a single `pabot_results/` dir. Two pabot invocations competing for the same pabotlib port + the same scratch dirs → mass test failures. This explains a large portion of the Codex + Copilot failures. **My fault for parallelizing the wrong thing.**

### Issue 2 (a real harness fragility — Sonnet caught it)

Sonnet ran AFTER Codex+Copilot finished and got the workspace mostly to itself. Sonnet still saw:
- **3 orphaned `echo_server` processes during suite/slow_server iter 4** — cross-cell leak the P2.1 baseline fix was supposed to prevent. The leak detector's 200ms grace window isn't enough for prior-cell processes to fully die before the next cell starts.
- **Test-scope cells failing back-to-back** with pabot rc=252 / "No output files in pabot_results/pabot_results". When the same workspace runs `pabot --testlevelsplit --processes 8` repeatedly with only a 200ms sleep between runs, pabot has file-handle release races.
- **Cross-cell JSONL contamination** — raw_*.jsonl files from one cell landed in another cell's iter dir.

When test-scope cells were run **in isolation** (one cell at a time, manual invocation), they passed 16/16 reliably. So the lifecycle manager itself works. The matrix harness has the bug.

## What each agent agreed on (high confidence)

| Finding | Codex | Copilot | Sonnet | Confidence |
|---|---|---|---|---|
| Story 0.1 smoke loop: 75/75 runs, 195 tool calls, all 3 coverage states | ✅ | ✅ | ✅ | **Very high** — 3/3 |
| Story 0.1 edge cases: 5/5 pass | ✅ | ✅ | ✅ | **Very high** — 3/3 |
| Story 0.2 handshake-race probe: 5/5 clean, shutdown 5-7ms | ✅ | ✅ | ✅ | **Very high** — 3/3 |
| Story 0.2 atexit probe: A=0 leaks, B=3/iter, C=3/iter | ✅ | ⚠️ (1 leak in A) | ✅ | **High** — 2/3 + 1 likely-contamination |
| Story 0.2 smoke matrix: NOT cleanly reproducible | ❌ found rc=252s | ❌ found rc=252s | ❌ found rc=252s + real leak | **High** — 3/3 agree there's a problem |

## What the matrix issue means for Story 0.3

The verdict text (Listener v3 primary + auto-installed SIGTERM handler + SIGKILL unrecoverable) is supported by **standalone probe evidence** that ALL 3 agents reproduced cleanly. Story 0.3's ADR-A6 / ADR-A8 amendment text does NOT depend on "45/45 matrix clean" being literally true.

What the matrix issue DOES affect:
1. The findings doc's headline number "45/45 iterations pass" is not robust under back-to-back execution. It's true under quieter conditions but the harness has cross-cell contamination.
2. The "zero leaks" claim is contradicted by Sonnet's observation of 3 echo_server orphans during one suite/slow_server iter.
3. The `mcp_per_test="test"` cleanup overhead numbers in §AC-0.2.2 should be treated as floor-estimates, not "validated targets" — production code under sustained pabot load may hit harness-class instabilities the spike's harness exposes.

## Adversarial concerns the agents independently surfaced

Each agent flagged 3 concerns. The overlap is informative:

**All 3 agents flagged: smoke matrix is not as clean as the findings doc says.**
- Codex: "the matrix harness is racing or appending stale data"
- Copilot: "measurement artifacts appear append-oriented and easy to misread; raises risk of accidentally summarizing historical data as fresh results"
- Sonnet: "cross-cell JSONL contamination; the P2.1 per-iter baseline did NOT fully prevent cross-cell process leakage"

**2/3 agents flagged: rf_mcp_substitute is unvalidated.**
- Sonnet: "load-bearing unvalidated substitute; every latency claim and every zero-leaks claim depends on the substitute behaving like the real server"
- Codex: "synthetic fixtures + narrow Linux-only runs" overstate decision-readiness

**Other concerns:**
- Sonnet: "test-scope cells don't reproduce cleanly in the matrix context — a harness-level stability issue not acknowledged in the findings doc"
- Codex: "shell-level command returned before pabot work had fully settled — that behavior makes timeout handling less trustworthy than the findings doc implies"
- Copilot: "atexit/cleanup claims framed too confidently for ratification"

## Recommended Story 0.3 unblock decision

You have three honest options:

### Option A — Accept current evidence, downgrade matrix headline (recommended)

The lifecycle manager works (proven by handshake-race, atexit, isolated test-scope runs). The ADR amendments are sound. Edit the findings doc to:
- Downgrade the §AC-0.2.1 headline from "45/45 pass" to "9/9 cells pass when run in isolation; matrix harness has known back-to-back instabilities documented in §Substitution disclosures"
- Acknowledge in §AC-0.2.1 the 3-orphan observation Sonnet caught
- Promote the rf_mcp_substitute caveat from footnote to primary risk

Then Story 0.3 ratifies the ADRs with the corrected evidence-claim language. **Cost: ~30 min of doc editing. No code rework.**

### Option B — Fix the harness, re-run

Fix the cross-cell contamination (per-iter sub-dirs for raw_*.jsonl), add proper inter-iter cool-down (longer than 200ms), reset pabot_results properly. Then re-run the matrix until 3/3 agents agree. **Cost: 1-2h of harness work + reruns. Higher rigor.**

### Option C — Accept the spike findings as-is, document the gaps as Story 0.3 preconditions

Don't edit the findings doc; instead, add to Story 0.3's unblock list:
- "Fix matrix harness cross-cell contamination before next reproducer run"
- "Validate against real rf-mcp before ratifying ADR-A8"
- Move Story 0.3 to `ready-for-dev` but with these caveats inline in the story file

**Cost: minimal. Pushes the work into Story 0.3 / Epic 1b Story 1b.1.**

## My honest recommendation

**Option A.** The spike has done what spikes do: it taught us that (a) the lifecycle manager is correct, (b) the auto-installed SIGTERM handler is necessary, (c) SIGKILL is unrecoverable at the listener layer, (d) the harness has limitations under sustained load. All four are useful findings. The matrix's "45/45 clean" headline overstates (d) but the verdict's substance is sound.

The production observer in Story 1b.1 / 5.2 won't use this exact harness anyway — it'll be wired into agenteval's actual test infrastructure, which has different scaffolding. Fixing this throwaway harness has marginal value; honestly documenting what it taught us has high value.

## Raw reports

- `/tmp/repro_codex.md` — Codex's full report
- `/tmp/repro_copilot.md` — Copilot's full report
- `/tmp/repro_sonnet.md` — Sonnet's full report

## What I'd like you to decide

Pick A, B, or C. I'll execute whichever path you choose.
