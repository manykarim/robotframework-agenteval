# Tasks — add-red-team-probes

## 1. Remove dead sandbox stubs

> Already closed upstream by the `remove-dead-machinery` change: the
> `src/AgentEval/security/` package (`null_sandbox.py` / `protocols.py` /
> `policy.py`) no longer exists. The only remaining `SandboxBackend` /
> `NullSandbox` mentions are intentional doc-references in `errors.py` +
> `_kernel/discovery.py` documenting the pre-1.0 withdrawal + the Phase-3
> `agenteval.sandboxes` re-introduction seam (0 functional callers). This change
> repurposes a fresh `redteam/` package (design D6 Open Question resolved →
> `redteam/`).

- [x] 1.1 Grep-confirm zero functional callers of `SandboxBackend` / `NullSandbox` / `security/policy` across `src/` and `tests/`
- [x] 1.2 Remove `src/AgentEval/security/null_sandbox.py`, `protocols.py`, `policy.py` and prune `security/__init__.py` exports (or delete the package if repurposing to `redteam/`) — package already deleted upstream; new `redteam/` package used
- [x] 1.3 Update any `docs/` / carry-over references to the removed stubs — done upstream; stability-surface Sandbox row documents the withdrawal

## 2. Probe schema and pack loader

- [x] 2.1 Define a typed `Probe` schema with fields `id`, `category`, `severity`, `source`, `expected_behavior`, and the attack payload (`redteam/schema.py`)
- [x] 2.2 Implement a YAML pack loader that validates each probe, enforces the four allowed categories, and surfaces structured errors (naming probe + field) in the project's File/Line/Field/Fix style
- [x] 2.3 Expose and validate a `pack_version` on the loaded pack
- [x] 2.4 Support user-supplied YAML extension: load + validate external probe files, merge with the bundled pack, and raise on duplicate `id` across packs

## 3. Bundled probe corpus (~20-40 single-turn probes)

- [x] 3.1 Author `prompt_injection` probes as YAML data (package data under `redteam/probes/`)
- [x] 3.2 Author `jailbreak` / role-play probes
- [x] 3.3 Author `pii_leakage` / system-prompt-leakage probes
- [x] 3.4 Author `encoding_obfuscation` probes
- [x] 3.5 Populate every probe's metadata (attribution to public garak/DeepTeam/OWASP sources) and confirm ≥20 total; add a top-of-pack VALIDATION-CEILING note stating what the pack does and does not cover, and confirm NO DoS / resource-exhaustion probes are present — 24 probes (6 per category); each YAML carries a VALIDATION-CEILING header; category set is closed (loader rejects any 5th category)

## 4. Refusal detection strategies

- [x] 4.1 Implement the deterministic, credential-free `pattern` refusal detector with a versioned, user-overridable refusal-language pattern set
- [x] 4.2 Implement the `judge` refusal detector delegating to the existing calibrated Judge library with a refusal-criteria prompt
- [x] 4.3 Implement the `both` combiner using the "refuse iff EITHER detects a refusal" rule and document the polarity (refusal = safe)

## 5. RedTeamLibrary keywords

- [x] 5.1 Implement `Run Probe` — single probe + Tier-3 category / `probe=all` fan-out routed through `@guarded_fanout` so `max_cost_usd` applies; drive the target via the existing adapter layer; return structured `ProbeResult` / `list[ProbeResult]`. **Decision:** a single keyword carries ONE tier annotation; since `Run Probe` CAN fan out and MUST always enforce budgets, it is `@tier(3) @guarded_fanout()` and a single-probe run is a degenerate 1-trial fan-out (documented in the docstring). This is strictly safer than a mode-dependent tier (budgets always apply) and keeps a single `Run Probe` keyword per the spec.
- [x] 5.2 Implement `Should Refuse` with `strategy=pattern|judge|both` (default `pattern`) — `@tier(2)` (the judge path is a single LLM call; pattern path is free)
- [x] 5.3 Implement `Get Attack Success Rate` mapping results to per-trial booleans (success = did NOT refuse) and reducing via the existing Wilson-CI primitive (`stats/wilson.py`; no new CI code); document ASR = compliance fraction, lower is safer
- [x] 5.4 Implement `Attack Success Rate Should Be Below    threshold=...` raising a structured `AssertionError` reporting observed ASR + Wilson CI + threshold on failure (strict `asr < threshold`)
- [x] 5.5 Register `RedTeamLibrary` in the `AgentEval/__init__.py` composition; verify each namespaced keyword name's post-dot portion is multi-word per the libdoc namespace norm — categorized as `RedTeam` in `test_keyword_namespace_prefix.py`; all four post-dot names are multi-word (libdoc-render smoke passes)

## 6. Heatmap integration

- [x] 6.1 Project probe results into the existing cohort-heatmap model as a probe-category × model grid (cell = ASR), reusing the existing `CohortHeatmap` renderers via a new `CohortHeatmap.from_probe_results` classmethod (rows = categories, columns = adapters, cell = ASR)

## 7. Tests

- [x] 7.1 Unit tests for the schema/loader: valid load, missing-field rejection, invalid-category rejection, `pack_version`, user-extension merge, duplicate-id error (`test_schema_loader.py`)
- [x] 7.2 Unit tests for refusal strategies incl. nullish/edge responses and the `both` combine rule (`test_refusal.py`)
- [x] 7.3 Unit/integration tests for `Run Probe` single + fan-out incl. budget-halt path, on mock adapters (`test_library.py`)
- [x] 7.4 Test ASR polarity: a fully-refusing mock scores ASR=0.0; a fully-complying mock scores ASR=1.0; CI is populated (`test_library.py`)
- [x] 7.5 Test `Attack Success Rate Should Be Below` pass + fail-with-detail paths (`test_library.py`)
- [x] 7.6 A `.robot` dogfood/example test exercising `Run Probe` → `Get Attack Success Rate` → `Attack Success Rate Should Be Below` end-to-end (`test_redteam_integration.robot`); fake-green precheck run (mutating the refusing-agent ASR expectation to 1.0 turns the suite RED)

## 8. Docs and finalization

- [x] 8.1 Add a README keyword-table entry for each new keyword and update the total keyword/library counts (94 keywords across 13 libraries; README + docs/index.md agree; `check_doc_keyword_count.py` passes)
- [x] 8.2 Add a red-teaming recipe/doc framing this as DEFENSIVE evaluation of the user's own agent; note multi-turn / Crescendo attacks as a future extension dependent on `add-multi-turn-conversation-testing`; smoke-execute any fenced code blocks (`docs/recipes/11-red-team-probes.md`; recipe-dryrun harness passes) + stability-surface entry + carry-over catalog C108 (`DF-RTP-S1`)
- [x] 8.3 Run `uv run pytest tests/`, `uv run ruff check src/ tests/`, `uv run mypy src/`, and a libdoc-render smoke of the new library (all green; libdoc HTML regenerated for `AgentEval.html` + `RedTeamLibrary.html`)
