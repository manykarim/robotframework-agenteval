## Context

`JudgeLibrary` (`src/AgentEval/judge/library.py`) ships two Tier-2 keywords:

- `Judge.Get Score` — requires a Markdown rubric **file** (`## Criteria`
  bullets + `## Threshold` line, parsed by `judge/rubric.py:load_rubric`) and
  returns a frozen `JudgeScore` (`numeric_score` 0-10, `pass_threshold_met`,
  `reasoning`, `criteria_breakdown`, `cost_usd`).
- `Judge.Calibrate Rubric` — runs the judge over a labeled YAML set, computes
  Cohen's κ over binarized pass labels, hard-fails below
  `KAPPA_HARD_FAIL_THRESHOLD = 0.7` (architecture.md L199). This calibration
  gate is unique in the market (findings dossier E6) and is the project's
  brand: honest, evidence-backed judge scores.

The friction: the cheapest possible first score costs a rubric file. DeepEval's
`GEval(criteria="...")` costs one string. The findings dossier (E6 MAJOR) ranks
"judge criteria one-liner + named metrics" among the highest-value gaps. The
design problem is lowering the on-ramp without muddying the calibration story —
a criteria-string score must never masquerade as a calibrated one.

Constraints inherited from the existing surface:

- `JudgeScore` is frozen, `experimental`-public, and consumed by dogfood tests;
  changes must be additive-with-defaults.
- All LLM-calling keywords wear `@tier(2)` + `@guarded_fanout()` (ADR-015).
- `Judge.*` keyword names must keep the post-dot portion multi-word
  (`feedback_libdoc_namespace_keyword_must_be_multiword`, DynamicCore/libdoc
  auto-split defect, confirmed N=2).
- Fail-loud (M_R11): no silent retry/recovery on judge output parse failures.
- `AgentRunResult` does NOT carry the original prompt, so presets that need the
  question or grounding context must take them as explicit arguments.

## Goals / Non-Goals

**Goals:**

- One-line judging: `Judge.Score With Criteria    ${result}    criteria=...
  threshold=7` returning the exact `JudgeScore` shape.
- 3 curated metric presets (Faithfulness, Answer Relevancy, Hallucination
  Score) with precisely documented semantics, each a thin wrapper over the same
  judge path.
- One-line assert form: `Judge Score Should Be Above`.
- Visible, unfakeable honesty marking: `calibrated` + `rubric_source` fields on
  `JudgeScore`, plus a documented WARN, plus a documented graduation path from
  criteria string → calibrated rubric (presets graduate via
  `Judge.Get Preset Rubric` → `Judge.Calibrate Rubric`).

**Non-Goals:**

- New judge backends or judge-prompt strategies (still single-shot, one
  adapter call, JSON contract unchanged).
- Multi-turn judging (sibling `add-multi-turn-conversation-testing`).
- Red-team refusal judging (sibling `add-red-team-probes`).
- Shipping pre-computed calibration data claiming κ for the presets (see
  Decision 5 — this would be dishonest).
- YAML rubrics (still DF-12.1-S1 / C79).

## Decisions

### D1 — Criteria string synthesizes a real `JudgeRubric`; one parser for all sources

`Judge.Score With Criteria` builds a `JudgeRubric` in memory:

- `criteria=(("user_criteria", <the string>),)` — a single criterion carrying
  the verbatim plain-language string (G-Eval idiom: the string IS the
  evaluation instruction; we do not attempt to decompose it).
- `threshold=<threshold arg>` (default `7.0`).
- `raw_text` = synthesized Markdown (`## Criteria` bullet + `## Threshold`
  line) so `_compose_judge_prompt` and every downstream consumer work
  unchanged.

To keep one parsing/validation path, `judge/rubric.py` extracts
`parse_rubric_text(raw_text, *, source)` from `load_rubric` (file IO stays in
`load_rubric`, which becomes a thin wrapper). Embedded preset rubrics are
parsed by the same function at registry-build time, so a malformed preset fails
at import/first-use, loudly, with the same `InvalidJudgeRubricError` shape.

*Alternative considered*: bypass `JudgeRubric` and hand the criteria string
straight to a bespoke prompt. Rejected — it forks the prompt-composition and
response-parsing paths and breaks `Judge.Calibrate Rubric` interop (a
synthesized rubric can itself be calibrated later without rewriting anything).

Validation: empty/whitespace-only `criteria` raises `InvalidJudgeRubricError`
(nullish-variant unit tests per `feedback_nullish_input_fuzz_checklist`);
`threshold` outside `[0.0, 10.0]` fails via the existing `JudgeRubric`
post-init.

### D2 — Honesty marking: `calibrated: bool` + `rubric_source: str` on `JudgeScore`

`JudgeScore` gains two fields, both defaulted so all existing constructor
call-sites and asdict consumers keep working:

- `calibrated: bool = False` — `True` is NEVER set by this change's keywords.
  Phase-1 semantics: the field means "this score came from a rubric with a
  recorded passing calibration"; since no keyword yet threads a
  `CalibrationReport` into `Get Score`, every score is honestly `False`.
  `Judge.Get Score` also stamps `False` — a rubric file is not evidence of
  calibration. A future change may add
  `Judge.Get Score ... calibration_report=${report}` to flip it on evidence;
  that is deliberately out of scope (recorded as a carry-over) because doing it
  well needs rubric-identity binding (hash of `raw_text` vs the report), and
  half-doing it would let operators flip the flag by assertion.
- `rubric_source: str = "file"` — provenance enum-as-string:
  `"file"` (Get Score with path), `"preloaded"` (Get Score with a JudgeRubric
  instance), `"criteria_string"`, `"preset:<name>"`. Enables report tooling and
  the docs' two-tier story to distinguish on-ramp scores from rubric scores.

*Alternative considered*: `calibrated: bool | None` with `None` = unknown.
Rejected — tri-state booleans invite `if score.calibrated` bugs; a plain
`False` with documented "no evidence of calibration" semantics is the honest
default (`feedback_honest_framing`).

Warning: the first uncalibrated-shortcut score per process emits
`robot.api.logger.warn` ("Uncalibrated judge score (rubric_source=…). Fine for
exploration; for CI gates graduate to a calibrated rubric — see
docs/recipes/judge-calibration.md"); subsequent calls log the same at INFO to
avoid WARN-flooding cohort fan-outs. Module-level once-flag; documented as
process-scoped (parallel pabot workers each warn once — acceptable).

### D3 — Presets are embedded Markdown constants in `judge/presets.py`, not packaged data files

Registry: `judge/presets.py` with `PRESET_RUBRICS: Mapping[str, str]` (raw
Markdown) parsed lazily into `JudgeRubric` via `parse_rubric_text`. Embedded
strings avoid `importlib.resources` packaging risk, keep rubric text
grep-able/reviewable in one module, and make the "document exactly what each
preset measures" requirement enforceable (each preset's criteria bullets ARE
the documentation, quoted verbatim in the keyword docstring).

Exactly 3 presets ship (scope cap 3-5; start minimal):

| Preset | Extra required input | Measures |
|---|---|---|
| `faithfulness` | `context` (grounding text) | Every factual claim in the response is supported by the supplied context; penalizes unsupported claims proportionally. |
| `answer_relevancy` | `question` | The response actually addresses the supplied question: on-topic, answers what was asked, no evasion/padding. |
| `hallucination` | `context` | Grounding score: 10 = zero fabricated entities/facts/citations relative to the context; 0 = pervasive fabrication. |

Preset keywords: `Judge.Get Faithfulness`, `Judge.Get Answer Relevancy`,
`Judge.Get Hallucination Score` — all multi-word post-dot (libdoc constraint
satisfied). Each takes `result`, its extra input, optional `threshold`
override (default = preset rubric's threshold, 7.0), plus the standard
`judge_adapter` / `judge_model` / `**adapter_kwargs` pass-through. Returns
`JudgeScore` with `rubric_source="preset:<name>"`, `calibrated=False`.

`Judge.Get Preset Rubric    name=faithfulness` returns the parsed `JudgeRubric`
so operators can feed it to `Judge.Calibrate Rubric` (which already accepts a
`JudgeRubric` instance) — the graduation path for presets requires zero new
calibration machinery.

*Alternative considered*: `preset:` URI scheme on the existing `rubric`
argument of `Get Score`/`Calibrate Rubric`. Rejected for Phase-1 — stringly
scheme parsing on an argument documented as "path or JudgeRubric" is a
subtle contract change to existing keywords; the explicit getter keyword is
discoverable in libdoc and keeps existing keyword requirements untouched.

### D4 — Hallucination score direction: higher = better (grounding score)

`JudgeScore.pass_threshold_met` is hard-wired to `numeric_score >=
threshold`. DeepEval's HallucinationMetric scores hallucination *proportion*
(lower = better) — importing that convention would silently invert pass
semantics for one preset out of three. Decision: ALL presets are
higher-is-better; the hallucination preset scores *freedom from hallucination*
(a grounding score). The keyword docstring and rubric text state this in the
first line ("10.0 = no hallucination detected"), and the keyword name stays
`Judge.Get Hallucination Score` per scope, with the direction documented
loudly rather than renamed.

*Alternative considered*: invert threshold semantics for this preset
(`pass if score <= threshold`). Rejected — forks the `JudgeScore` contract and
every downstream consumer's mental model for one keyword.

### D5 — Presets ship uncalibrated-by-default; no bundled "default calibration sets"

Cohen's κ is a joint property of (rubric × judge model × domain distribution ×
human labelers). A calibration set we author against our own labels with one
judge model does not transfer to the user's model and domain — shipping one and
letting `calibrated=True` ride on it would be exactly the vibes-over-evidence
claim this project brands against. Instead:

- Presets are documented uncalibrated-by-default, `calibrated=False` always.
- Each preset ships a small **calibration-set template** (YAML in the schema
  `load_calibration_set` already accepts, with placeholder rows and comments
  explaining the labeling task) under `docs/examples/judge-presets/`, plus a
  recipe section showing `Judge.Get Preset Rubric` → `Judge.Calibrate Rubric`
  on the user's own labels.
- The two-tier message lands in `docs/recipes/judge-calibration.md`: tier 1
  "one-line criteria string / preset — exploration, `calibrated=False`";
  tier 2 "calibrated rubric with κ ≥ 0.7 — CI gates".

### D6 — Assertion form delegates to the same path and fails with reasoning

`Judge Score Should Be Above    ${result}    criteria=...    threshold=7`
(un-namespaced, matching `AssertionsLibrary`'s `X Should ...` naming
convention) lives on `JudgeLibrary` because it makes an LLM call and needs
`@tier(2)` + `@guarded_fanout()` — `AssertionsLibrary` is a Tier-1 surface.
Behavior: internally runs the same criteria-string scoring path, then raises
an assertion failure (RF `Fail`-compatible `AssertionError`) when
`numeric_score < threshold`, with a message carrying the score, the threshold,
`rubric_source`, the `calibrated=False` marker, and the judge's `reasoning`
(redaction not required — reasoning comes from the judge model, not tool
args; revisit if presets ever embed tool traces). On pass it returns the
`JudgeScore` so callers can log/inspect without a second LLM call.

Phase-1 accepts `criteria` only (the keyword IS the on-ramp; rubric-file users
already have `Get Score` + `Should Be True` shown in the recipe). Threshold
semantics: strictly-above reading of the name vs the project's `>=` pass
convention — decided as `numeric_score >= threshold` to match
`pass_threshold_met` everywhere else, with the docstring stating this
explicitly (avoids two subtly different threshold comparisons in one library).

### D7 — Prompt composition extension for preset inputs

`_compose_judge_prompt` gains an optional `extra_sections:
Sequence[tuple[str, str]]` parameter (default empty) appended as `# <title>`
blocks (e.g. `# Question`, `# Context`) between the rubric and the agent
response. Pure-additive: existing callers pass nothing and produce
byte-identical prompts (guarded by a regression unit test), preserving Tier-2
seed+temperature=0 reproducibility for existing suites.

## Risks / Trade-offs

- [Criteria-string scores get used as CI gates anyway] → `calibrated=False` on
  the returned object, WARN on first use, recipe's two-tier framing, and the
  assertion failure message itself restates the uncalibrated marker. We cannot
  (and should not) hard-block it — exploration is the point.
- [Preset rubric quality is subjective; users assume DeepEval-equivalent
  semantics] → each preset's docstring quotes its criteria bullets verbatim
  and names what it does NOT measure (e.g. faithfulness ≠ factual accuracy
  against the world, only against the supplied context); calibration-set
  templates push users to verify on their own data.
- [Hallucination direction surprises DeepEval migrants (lower-is-better
  there)] → first docstring line + rubric text + recipe all state
  "grounding score, 10 = no hallucination"; `docs/coming-from/` note when that
  doc dir is populated (out of scope here).
- [WARN-once-per-process is invisible in the Nth suite of a long run] →
  trade-off accepted to avoid flooding cohort fan-outs; the per-score
  `calibrated`/`rubric_source` fields are the durable signal, the log line is
  only a courtesy.
- [`JudgeScore` field additions ripple into dogfood asdict snapshots] →
  additive fields with defaults; grep + run existing judge unit/dogfood tests;
  any snapshot updates are mechanical.
- [Single-criterion synthesized rubric makes `criteria_breakdown` trivially
  one-keyed] → acceptable; the judge's JSON contract already requires every
  rubric criterion in the breakdown, and one key is the honest representation
  of a one-string rubric.
- [Preset prompt sections (`# Context`) can be huge] → no truncation in
  Phase-1 (fail-loud on provider limits is consistent with M_R11); documented
  in keyword docstrings; token-budget guardrails already meter cost via
  `@guarded_fanout`.

## Migration Plan

Purely additive; no deploy/rollback complexity. Order: types fields →
`parse_rubric_text` refactor → presets module → keywords → docs/recipe.
Existing tests must stay green at every step (`uv run pytest tests/`,
`ruff`, `mypy` per project gates). Rollback = revert the change; no data or
config migration exists.

## Open Questions

- Should a future change add `calibration_report=` evidence-binding to
  `Judge.Get Score` so `calibrated=True` becomes reachable (rubric-hash
  binding, staleness rules)? Deliberately deferred; record as a `DF-*` carry-over
  during implementation.
- Preset threshold defaults: 7.0 uniformly for all three, or per-preset tuned
  defaults? Phase-1 ships 7.0 uniformly (no evidence base to claim otherwise —
  honest framing); revisit after real calibration data exists.
