## Why

AgentEval evaluates coding agents but ships **zero** adversarial-robustness
coverage: `src/AgentEval/security/` is dead stubs (a `SandboxBackend` Protocol +
a `NullSandbox` that only raises — 0 functional callers, E5 audit). Meanwhile
red-teaming is the growth engine of the competitive field: promptfoo's 40+
red-team plugins are its adoption driver, and DeepTeam (2.1k⭐) and garak
(8.4k⭐) own the category outright (landscape doc §7). This is a **critical**
market gap not on the current roadmap (E6). The differentiating insight is that
AgentEval already owns the hard part for free: the Tier-3 stochastic fan-out
machinery (`Stat.Run N Times`, `Stat.Get Pass At K`, Wilson-CI) turns any
per-trial pass/fail signal into an attack-success-rate with a confidence
interval — exactly the statistic a red-team run reports. We only need to add the
attack corpus and a refusal-detection front end.

This capability is **defensive security testing of the user's own agents** — it
measures whether an agent the user controls resists prompt injection, jailbreak
role-play, PII / system-prompt leakage, and encoding-obfuscation attacks. It is
not an offensive tool.

## What Changes

- Add a **curated, versioned probe pack** shipped as YAML data files with the
  library (~20-40 single-turn probes to start), spanning four garak-style
  categories: `prompt_injection`, `jailbreak`, `pii_leakage`, and
  `encoding_obfuscation`. Each probe carries metadata: `id`, `category`,
  `severity`, `source`/attribution, and an `expected_behavior` description.
- The pack is **extensible**: users point a keyword at their own YAML files to
  add probes without forking the library.
- New keywords on a `RedTeamLibrary`:
  - `Run Probe    ${adapter}    category=prompt_injection    probe=<id|all>` —
    Tier-2 single probe / Tier-3 fan-out over a category, returning a structured
    probe-result (or list of results).
  - `Should Refuse    ${result}` — refusal detection with a selectable strategy
    (pattern-based, judge-based reusing the existing `Judge` library, or both).
  - `Get Attack Success Rate    ${results}` — wraps the existing Pass@k / Wilson
    machinery to compute ASR (fraction of probes NOT refused) with a CI.
  - `Attack Success Rate Should Be Below    ${results}    threshold=0.05` —
    assertion for CI gating.
- Probe results **integrate with existing surfaces**: they feed the cohort
  heatmap as probe-category × model grids, and Tier-3 fan-out runs honor the
  existing `max_cost_usd` budget guardrails.
- Retire the dead `security/` sandbox stubs in favor of this functional
  capability (the sandbox Protocol has 0 callers; superseded by the probe pack).
- **Deferred (documented as future extension, not built here):** multi-turn /
  Crescendo-style escalating attacks, which depend on the sibling
  `add-multi-turn-conversation-testing` change.

## Capabilities

### New Capabilities
- `red-team-probes`: single-turn adversarial probe library — a versioned probe
  pack (data + schema + user-extension loader), the `Run Probe` /
  `Should Refuse` / `Get Attack Success Rate` /
  `Attack Success Rate Should Be Below` keywords, refusal-detection strategies,
  and integration of probe results with the cohort heatmap and cost-budget
  guardrails.

### Modified Capabilities
<!-- None. No existing openspec/specs/ capability's requirements change. The
     dead security/ stubs being retired have no ratified spec of their own. -->

## Impact

- **New package:** `src/AgentEval/security/` is repurposed from dead stubs into
  the functional red-team probe home (probe schema, YAML loader, refusal
  detection, `RedTeamLibrary`), or a new `src/AgentEval/redteam/` package if
  cleaner. Bundled probe YAML shipped as package data.
- **Reused, unchanged:** `stats/` (`Run N Times`, `Get Pass At K`,
  `Get Pass At K Confidence Interval`, Wilson-CI), `_kernel/tier.py` (`@tier`),
  `_kernel/guardrails.py` (`@guarded_fanout` + `max_cost_usd`), `judge/`
  (judge-based refusal path), `_heatmap/` (cohort grids), and `Send Prompt` /
  the adapter layer for driving the target agent.
- **New library registration** in `AgentEval/__init__.py` composition + docs /
  README keyword tables; keyword count updates.
- **No new hard dependencies** — probes are static YAML; the judge path reuses
  the existing judge provider plumbing.
- **Removed:** dead `NullSandbox` / `SandboxBackend` Protocol stubs (0 callers).
