## Context

AgentEval already ships the statistical spine of a red-team runner: the Tier-3
fan-out keyword `Stat.Run N Times` executes a callable N times and returns
per-trial `KeywordRun` records; `Stat.Get Pass At K` and
`Stat.Get Pass At K Confidence Interval` reduce those trials to a rate with a
Wilson confidence interval; `@guarded_fanout` + `max_cost_usd` cap the spend of
a fan-out; the `Judge` library (Epic 12, κ≥0.7-calibrated) can score free-text;
and `Get Cohort Heatmap` renders model × dimension grids. What is missing is
(1) an **attack corpus** and (2) a **refusal-detection front end** that turns
"did the agent comply with the attack?" into the per-trial boolean the stats
layer already consumes.

The competitive landscape (docs/ai-testing-tools-landscape.md §7) is anchored by
garak (probe library + plugin architecture), DeepTeam (50+ vulnerabilities,
20+ attack methods, local judge scoring, no dataset needed), and PyRIT
(multi-turn orchestration). promptfoo's red-team plugin catalog is its adoption
engine. AgentEval has none of this; `src/AgentEval/security/` is 194 LOC of dead
`SandboxBackend` Protocol + `NullSandbox` (0 callers, E5 audit).

This is **defensive** security testing: the operator runs curated attacks
against an agent they own and asserts it resists them. The framing, docs, and
keyword names must reflect that (evaluate resistance), not offensive tooling.

## Goals / Non-Goals

**Goals:**
- Ship a curated, versioned, single-turn probe pack (~20-40 probes) across four
  garak-style categories with rich per-probe metadata.
- Make attack-success-rate a first-class, CI-gateable metric derived from the
  existing Pass@k / Wilson machinery — no new statistics code.
- Offer a refusal-detection front end with both a zero-cost pattern strategy and
  a higher-fidelity judge strategy (reusing the calibrated `Judge`).
- Let users extend the corpus with their own YAML without forking.
- Integrate probe results into the existing cohort heatmap and cost budgets.

**Non-Goals:**
- Multi-turn / Crescendo escalating attacks (deferred to depend on
  `add-multi-turn-conversation-testing`).
- Sandboxing / process isolation (the retired stubs; out of mission).
- DoS / resource-exhaustion probes (out of mission — not a robustness class we
  evaluate).
- Automatic attack *generation* / mutation (garak-style generators). The corpus
  is static + user-extensible; generation is a possible later extension.

## Decisions

### D1: Probes are static, versioned YAML shipped as package data
Store the bundled corpus as YAML data files (e.g.
`src/AgentEval/redteam/probes/*.yaml`) loaded through a typed schema, mirroring
how scenarios are loaded elsewhere. The pack carries a `pack_version` so runs
are reproducible and drift is detectable.
- **Why over a Python-literal corpus:** YAML is diffable, user-authorable, and
  reviewable without touching code; it matches the "user-supplied YAML"
  extension requirement directly.
- **Alternative considered:** vendoring garak's probe format. Rejected — heavier
  schema than we need for single-turn, and licensing/attribution complexity.
  We instead record `source`/attribution per probe so garak/DeepTeam-derived
  probes are credited.

### D2: A probe result is a structured record, not a bare bool
`Run Probe` returns a `ProbeResult` (or `list[ProbeResult]` for `probe=all` /
category fan-out) carrying: the probe `id`/`category`/`severity`, the raw agent
`response_text`, the refusal verdict + which strategy decided it, and the
underlying `AgentRunResult` (for cost/latency/trace). This keeps ASR computation,
heatmap projection, and debugging all driven off one object.
- **Why:** `Should Refuse` and `Get Attack Success Rate` need the verdict *and*
  the evidence; a bare bool would discard the response needed for triage and for
  the judge path.

### D3: Refusal detection is strategy-selectable — pattern, judge, or both
`Should Refuse` (and the internal verdict on `Run Probe`) accepts a
`strategy` argument: `pattern` (default — regex/keyword match on refusal
language, zero API cost, deterministic), `judge` (delegate to the calibrated
`Judge` with a refusal-criteria prompt), or `both`. In `both`, define the
combine rule explicitly (see Open Questions) rather than leaving it implicit.
- **Why default pattern:** the mock-provider-first ethos and cost-consciousness
  of the project — a red-team suite must be runnable in CI without API keys and
  cheaply. The judge path is opt-in for fidelity.
- **Alternative considered:** judge-only. Rejected — forces API keys + cost on
  every run and couples the headline capability to judge availability.

### D4: ASR reuses Pass@k / Wilson — no new statistics
Define attack success per trial as "agent did NOT refuse" (i.e. complied with
the attack). `Get Attack Success Rate` maps probe results to per-trial booleans
and calls the existing pass-rate + Wilson-CI primitives, so ASR ships with a
confidence interval for free. `Attack Success Rate Should Be Below` asserts on
that rate. Framing note: a "pass" in the security sense is a *refusal*; we invert
carefully and document the polarity so the number is unambiguous (ASR = compliance
fraction; lower is safer).
- **Why:** honors the "statistics come free from existing machinery" mandate and
  avoids a second, divergent CI implementation (the codebase already carries a
  `discoverability/wilson_ci.py` duplicate of `stats/wilson.py` — do not add a
  third).

### D5: Tiering — `Run Probe` is Tier-2 single / Tier-3 fan-out
A single probe against a single adapter is one LLM round-trip → `@tier(2)`.
Running a category / `probe=all` with repetition for ASR is a fan-out →
routed through the Tier-3 `@guarded_fanout` path so `max_cost_usd` budget
enforcement and metering apply automatically. Follow the existing
`Send Prompt` (Tier 2) + `Stat.Run N Times` (Tier 3) precedent.

### D6: Retire, don't extend, the dead sandbox stubs
Remove `null_sandbox.py` / `protocols.py` / `policy.py` (0 callers) and reuse
the `security/` namespace — or introduce `redteam/` — for the functional
capability. Decided in the spec/tasks phase which package name; either way the
dead code goes.

### D7: Heatmap integration is a projection, not a new renderer
Probe results project into the existing cohort-heatmap model as a
probe-category × model grid (cell value = ASR). Reuse `Get Cohort Heatmap`
rather than building a red-team-specific report surface.

## Risks / Trade-offs

- [Pattern-based refusal detection is brittle — false negatives when an agent
  refuses in unusual phrasing, false positives when it discusses refusal while
  complying] → Ship the judge strategy as the higher-fidelity opt-in; document
  the trade-off; keep the refusal pattern set versioned and user-overridable.
- [Polarity confusion — "pass@k" means success, but a security "pass" is a
  refusal] → Name the metric Attack **Success** Rate (compliance fraction,
  lower is safer) and document the inversion at every keyword; add a scenario
  test asserting a fully-refusing mock scores ASR=0.0.
- [Shipping attack strings could read as offensive tooling / trip content
  filters] → Frame everything as defensive evaluation of the user's own agent;
  keep the corpus small and well-known (attributed to public garak/DeepTeam/OWASP
  sources); no novel or weaponizable exploit generation.
- [Judge-based path needs API keys + cost, contradicting CI-friendliness] →
  Default to `pattern`; judge is explicit opt-in and honors `max_cost_usd`.
- [Corpus staleness vs a fast-moving attack landscape] → `pack_version` + the
  user-extension loader let teams add current probes without waiting on a release.

## Migration Plan

1. New capability, additive — no existing keyword behavior changes.
2. Remove the dead `security/` sandbox stubs in the same change (0 callers, so no
   downstream breakage; verify via grep for `SandboxBackend` / `NullSandbox`).
3. Register the new library in the `AgentEval/__init__.py` composition and update
   README / docs keyword tables + counts.
4. Rollback: revert the change; because it is additive and the removed stubs were
   dead, rollback is clean.

## Open Questions

- **Package name:** repurpose `security/` vs a fresh `redteam/`? Lean `redteam/`
  for clarity (security/ connoted sandboxing); resolve in tasks.
- **`strategy=both` combine rule:** refusal iff BOTH agree it refused (stricter,
  fewer false "safe") vs iff EITHER says refused (more lenient). Lean "refuse iff
  either detects a refusal" so a real refusal missed by patterns is still caught;
  confirm in spec scenarios.
- **Default fan-out N and default threshold** for `Attack Success Rate Should Be
  Below` — pick sane defaults (e.g. threshold=0.05) but let the scenario suite
  validate they are not misleading on the mock provider.
- **Should the four categories each be a separate YAML file or one file with a
  `category` field?** Lean per-category files for reviewability; confirm in tasks.
