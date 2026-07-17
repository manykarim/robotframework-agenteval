# CLAUDE.md — robotframework-agenteval

Project-level operating manual for Claude Code / autonomous-loop sessions on
`robotframework-agenteval`. This file is auto-loaded into every Claude Code
session opened in this directory and is the **canonical source of truth** for
the project's collaboration norms.

If anything below conflicts with the user-global
`/home/many/.claude/CLAUDE.md`, project-level rules win for this repo.

---

## Cross-LLM review chain (3-tier — ratified Epic 10 retro 2026-05-26)

**Non-trivial story commits + retros MUST pass a cross-LLM adversarial review
before being marked `done`.** The project runs a **3-tier review chain** with
different fallback semantics per tier. Ratified at Epic 10 retro with **N=9
substantive story-level reviews** across Epics 8+9+10 backing the third tier.

### Tier 1 (primary): Claude CLI

```
claude -p --dangerously-skip-permissions --model opus "<prompt>"
```

- Catches **semantic-shape bugs + empirical-SDK-probe-class bugs**. Best at:
  bidirectional dataclass-attribute verification, listener-hook API surface
  checks, test-name vs assertion-body match.
- Failure modes: session rate-limits (`You've hit your session limit · resets <time>`),
  empty output (returns 0 bytes for some long-prompt classes — Epic 8a.2 origin).
- When degraded: proceed to Tier 2.

### Tier 2 (secondary, when quota available): Codex CLI

```
codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "<prompt>"
```

- Catches **numeric drift + citation drift + accounting reconciliation
  failures**. Best at: machine-re-verifiable counts, git-range math,
  cross-source citation consistency.
- Failure modes: hard usage limits (`ERROR: You've hit your usage limit. ... try again at <time>`).
  Time-window-bound; restores naturally on the quoted retry-after.
- When degraded: proceed to Tier 3. **Do NOT block on Codex** — it is
  unreliable as a sole reviewer (Epic 8/9/10 evidence base).

### Tier 3 (canonical fallback when Tier 1+2 both degrade): kilo/minimax-M2.7

```
~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7 "<prompt>"
```

- Catches **framing/process drift + months-old citation renumbering trails +
  evaluative-vs-factual claim misframing**. Best at: orthogonal coverage to
  Claude + Codex (zero finding-overlap demonstrated at Epic 10 retro-on-retro).
- Operational note: `--auto` mode invokes Write/Read/Grep/Bash tools
  autonomously. Prompt MUST instruct kilo to `Write` its findings to a
  specific file path or the final answer may be lost to streaming output.
- Failure modes: occasional empty output on long-prompt classes (treat same as
  Claude). No documented rate-limit at the M2.7 endpoint at time of ratification.

### How to invoke the chain

For each non-trivial commit / retro draft:

1. **Run Tiers 1 + 2 in parallel** via background Bash tasks. Save findings to
   `_bmad-output/cross-llm-reviews/<artifact>-{claude,codex}-findings.md`.
2. **If both produce ≥1 HIGH OR ≥2 MED**, ratify the patches inline. Done.
3. **If either is empty/rate-limited**, invoke Tier 3 immediately. Save to
   `_bmad-output/cross-llm-reviews/<artifact>-kilo-findings.md`.
4. **For non-trivial retros (`bmad-retrospective` outputs)**, invoke ALL 3 tiers
   independently regardless of degradation status. Coverage is multiplicative,
   not redundant (Epic 10 retro: codex caught 6 HIGH numeric drifts; kilo caught
   2 MED framing drifts; ZERO overlap).
5. Apply HIGH findings inline (v2 of the artifact). MED findings: triage
   honestly — apply if real, otherwise document why deferred.
6. Save all reviewer stdouts under `_bmad-output/cross-llm-reviews/` for the
   audit trail.

### When ALL 3 tiers degrade

Per `feedback_integration_test_forcing_function` (Epic 8 retro): substitute
**end-to-end integration tests as the empirical-truth check**. Real-bug catches
through this path are well-documented (Stories 8a.2 / 8b.1 / 8b.2 / 10.2). The
chain is the canonical mitigation — integration tests are the stopgap, not the
fix. After-the-fact, retry the chain when quotas restore (Epic-9-retro-batch
commit `16ee936` is the pattern: 8 HIGH patches applied across 7 retroactive
story reviews via kilo/minimax once it became available).

### Source

- Epic 10 retrospective: `_bmad-output/implementation-artifacts/epic-10-retro-2026-05-26.md`
  (codex + kilo dual-substantive review of the retro itself was the highest-leverage validation).
- Norm file: `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_third_llm_family_fallback.md`.

---

## Project memory — auto-loaded norms

Twenty-three ratified norms live in `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/`
and are auto-loaded into every session. The most load-bearing are:

- **`feedback_spec_vs_ratified_doc_precheck`** (44 consecutive uses, 100% catch
  rate) — at `/bmad-create-story` time, grep epics.md + architecture.md + PRD
  for drift vs spec; resolve drift via "fix-the-losing-source-NOW" in the same
  commit. Catches 5–10 drifts per story authoring.
- **`feedback_carry_over_catalog_gate` UPSTREAM** (23 consecutive stories) — at
  `/bmad-dev-story` Task N-1 (BEFORE invoking `bmad-code-review`), grep new
  files for `DF-X-SY` patterns and verify each is in
  `docs/phase-1-5-carry-overs.md`.
- **`feedback_third_llm_family_fallback`** (see above; ratified Epic 10).
- **`feedback_cross_story_upstream_lesson_propagation`** (ratified Epic 10) —
  when Story N+1 touches the same surface as Story N, fold N's review HIGH+MED
  findings into N+1's ACs UPSTREAM.
- **`feedback_citation_drift_first_class`** (Epic 1a) — reviewer must
  re-derive each cited fact from source.
- **`feedback_honest_framing`** — numeric bars, not vibes. Quote `wc -l`,
  `git rev-list --count`, etc. when claiming counts.

See `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/MEMORY.md`
for the full index. **Do not duplicate memory content here** — memory files
are the canonical source.

---

## Project quick-facts

- **Purpose:** Open-source RF library evaluating AI coding agents (RF 7.x).
  PyPI dist: `robotframework-agenteval`; Python package: `AgentEval`.
- **Phase status:** Phase 1 complete (Epics 0-9). Phase 2 in progress
  (Epic 10 done + retro-closed; Epic 11 next — CLI Adapters + AdapterVersionDriftWarning).
- **Test surface:** 1605 passed + 10 skipped at HEAD. `uv run pytest tests/`.
- **Lint + types:** `uv run ruff check src/ tests/` + `uv run mypy src/`
  (scoped to src — tests/ lint-only).
- **Full local gate (run ALL before committing — these mirror CI; three of
  them are CI-only and previously slipped to PR time):**
  ```bash
  uv run ruff check src/ tests/
  uv run ruff format --check src/ tests/          # CI-only gate (ci.yml)
  uv run mypy src/
  uv run python scripts/check-license-headers.py  # CI-only gate (ci.yml)
  uv run python scripts/check-contract-sections.py # CI-only gate (docs-build.yml, NFR-MAINT-04)
  uv run python scripts/check_doc_keyword_count.py # CI-only gate (docs-build.yml)
  uv run python scripts/check-doc-rendering.py     # CI-only gate (docs-build.yml)
  uv run pytest tests/
  ```
  The same set is wired into `.pre-commit-config.yaml` (`uv run pre-commit run
  --all-files`), but `pre-commit install` is blocked when `core.hooksPath` is
  set, so agent sessions must run the sequence explicitly rather than relying on
  the git hook firing.
- **Dogfood targets:** `rf-mcp` (vendored at `/home/many/workspace/rf-mcp/`) +
  `robotframework-agentskills`. Path-B live-LLM E2E now operational via
  minimax M2.7 (`tests/dogfood/rf-mcp/test_metrics_e2e_smoke.robot`).
- **Reference inspiration only:** `agentguard` is a pattern source, NOT a
  dependency. Free to diverge.

---

## Retro-debt mini-pass at story-create time

**Before invoking `/bmad-create-story`, the operator runs a 2-minute audit of
prior-retro action items + commits to closing ≥1 unresolved item BEFORE
starting the new story.** Installed by Story 14.1 META (2026-06-03) per Epic 12
retro L161 Action #2 (`_bmad-output/implementation-artifacts/epic-12-retro-2026-06-01.md`)
+ Epic 13 retro L179 Action #2 (`_bmad-output/implementation-artifacts/epic-13-retro-2026-06-03.md`).
Motivation: the autonomous /goal loop demonstrated 9% retro-debt
follow-through over 3 consecutive epics (Epic 13 retro L193 honest framing).
This mini-pass shifts retro-debt closure from passive ("the loop fails to
close items") to active ("operator allocates 1 item per story-create to
close").

### 5-step procedure

1. List the most recent N=3 retro files:
   ```bash
   ls -t _bmad-output/implementation-artifacts/epic-*-retro-*.md | head -3
   ```
2. For each retro, read the `## Action items for next retrospective check`
   table (each retro carries one; structure is consistent since Epic 7).
3. For each unresolved action item still relevant to the upcoming story,
   either write its closure into the new story's spec OR explicitly
   document why it's deferred (per `feedback_honest_framing` — no silent
   carryover).
4. Allocate ≥1 retro-debt closure as an explicit AC in the new story.
   The closure is part of the story scope, NOT parallel work tracked
   elsewhere.
5. Save the audit notes as a `## Retro-debt mini-pass` subsection in the
   new story spec (placed under the drift check, before ACs), naming
   which retro items were considered + which got closed by this story.

### Common failure mode (per Story 13.5 HIGH-A precedent)

**Reading the action item and deciding it's N/A without grep'ing for the
named symbol.** When an action item names a specific symbol, file, or flag,
run a concrete grep before deciding it's N/A. Examples:

- Action item: "close `@guarded_fanout` MCPLibrary carve-out" →
  `grep -nE "@guarded_fanout|_max_cost_usd" src/AgentEval/mcp/library.py`
  BEFORE deciding the action is closed or N/A.
- Action item: "backfill Story 7.1 spec Change Log" →
  `grep -nE "^## Change Log|^\\| 20" _bmad-output/implementation-artifacts/7-1-*.md`
  BEFORE deciding the action is satisfied.
- Action item: "live integration tests for 5+ adapters" →
  `grep -lE "AGENTEVAL_INTEGRATION_TESTS" tests/integration/test_*_live.py`
  + check CI run logs BEFORE deciding the action is closed.

The grep is the audit; the action item text is only a pointer.

### Closure note

This section installed by Story 14.1 (`14-1-meta-install-retro-debt-mini-pass-libdoc-smoke-story-7-1-changelog`)
on 2026-06-03, closing Epic 12 retro Action #2 + Epic 13 retro Action #2
(both reference identical "install CLAUDE.md story-create-time retro-debt
mini-pass" criteria).

---

## Hard rules for autonomous loops

- **NEVER skip pre-commit hooks** (`--no-verify`, `--no-gpg-sign`) unless the
  user explicitly says to. If a hook fails, fix the root cause + create a NEW
  commit (NEVER amend the previous one — the failed commit didn't happen, so
  amending modifies the wrong target).
- **NEVER push unless explicitly asked.** Most session work is local-only by
  design.
- **NEVER mark a task `completed` if tests are failing, implementation is
  partial, or you couldn't find a required file.** Status `in_progress` until
  the work actually passes.
- **NEVER commit `.env`** or any file containing `sk-` / `Bearer ` / API-key
  patterns. `.env` is gitignored at L59-61 of `.gitignore`.
- **For dogfood test invocations that exercise live providers:** read env vars
  via Python `os.environ.get(...)` in a `@library`-decorated helper class, NOT
  via RF's `Get Environment Variable` (the latter logs values to `log.html`).
  See `tests/dogfood/rf-mcp/_minimax_orchestrator.py:Skip If Minimax Credentials Missing`
  for the canonical pattern.
