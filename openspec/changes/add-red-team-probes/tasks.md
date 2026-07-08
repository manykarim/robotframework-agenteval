# Tasks — add-red-team-probes

## 1. Remove dead sandbox stubs

- [ ] 1.1 Grep-confirm zero functional callers of `SandboxBackend` / `NullSandbox` / `security/policy` across `src/` and `tests/`
- [ ] 1.2 Remove `src/AgentEval/security/null_sandbox.py`, `protocols.py`, `policy.py` and prune `security/__init__.py` exports (or delete the package if repurposing to `redteam/`)
- [ ] 1.3 Update any `docs/` / carry-over references to the removed stubs

## 2. Probe schema and pack loader

- [ ] 2.1 Define a typed `Probe` schema with fields `id`, `category`, `severity`, `source`, `expected_behavior`, and the attack payload (`redteam/schema.py`)
- [ ] 2.2 Implement a YAML pack loader that validates each probe, enforces the four allowed categories, and surfaces structured errors (naming probe + field) in the project's File/Line/Field/Fix style
- [ ] 2.3 Expose and validate a `pack_version` on the loaded pack
- [ ] 2.4 Support user-supplied YAML extension: load + validate external probe files, merge with the bundled pack, and raise on duplicate `id` across packs

## 3. Bundled probe corpus (~20-40 single-turn probes)

- [ ] 3.1 Author `prompt_injection` probes as YAML data (package data under `redteam/probes/`)
- [ ] 3.2 Author `jailbreak` / role-play probes
- [ ] 3.3 Author `pii_leakage` / system-prompt-leakage probes
- [ ] 3.4 Author `encoding_obfuscation` probes
- [ ] 3.5 Populate every probe's metadata (attribution to public garak/DeepTeam/OWASP sources) and confirm ≥20 total; add a top-of-pack VALIDATION-CEILING note stating what the pack does and does not cover, and confirm NO DoS / resource-exhaustion probes are present

## 4. Refusal detection strategies

- [ ] 4.1 Implement the deterministic, credential-free `pattern` refusal detector with a versioned, user-overridable refusal-language pattern set
- [ ] 4.2 Implement the `judge` refusal detector delegating to the existing calibrated Judge library with a refusal-criteria prompt
- [ ] 4.3 Implement the `both` combiner using the "refuse iff EITHER detects a refusal" rule and document the polarity (refusal = safe)

## 5. RedTeamLibrary keywords

- [ ] 5.1 Implement `Run Probe` — Tier-2 single probe (`@tier(2)`) and Tier-3 category / `probe=all` fan-out routed through `@guarded_fanout` so `max_cost_usd` applies; drive the target via the existing adapter layer; return structured `ProbeResult` / `list[ProbeResult]`
- [ ] 5.2 Implement `Should Refuse` with `strategy=pattern|judge|both` (default `pattern`)
- [ ] 5.3 Implement `Get Attack Success Rate` mapping results to per-trial booleans (success = did NOT refuse) and reducing via the existing Pass@k pass-rate + Wilson-CI primitives (no new CI code); document ASR = compliance fraction, lower is safer
- [ ] 5.4 Implement `Attack Success Rate Should Be Below    threshold=...` raising a structured error reporting observed ASR + CI + threshold on failure
- [ ] 5.5 Register `RedTeamLibrary` in the `AgentEval/__init__.py` composition; verify each namespaced keyword name's post-dot portion is multi-word per the libdoc namespace norm

## 6. Heatmap integration

- [ ] 6.1 Project probe results into the existing cohort-heatmap model as a probe-category × model grid (cell = ASR), reusing `Get Cohort Heatmap`

## 7. Tests

- [ ] 7.1 Unit tests for the schema/loader: valid load, missing-field rejection, invalid-category rejection, `pack_version`, user-extension merge, duplicate-id error
- [ ] 7.2 Unit tests for refusal strategies incl. nullish/edge responses and the `both` combine rule
- [ ] 7.3 Unit/integration tests for `Run Probe` single (Tier 2) + fan-out (Tier 3) incl. budget-halt path, on the mock provider
- [ ] 7.4 Test ASR polarity: a fully-refusing mock scores ASR=0.0; a fully-complying mock scores ASR=1.0; CI is populated
- [ ] 7.5 Test `Attack Success Rate Should Be Below` pass + fail-with-detail paths
- [ ] 7.6 A `.robot` dogfood/example test exercising `Run Probe` → `Get Attack Success Rate` → `Attack Success Rate Should Be Below` end-to-end; run a fake-green precheck on it

## 8. Docs and finalization

- [ ] 8.1 Add a README keyword-table entry for each new keyword and update the total keyword/library counts
- [ ] 8.2 Add a red-teaming recipe/doc framing this as DEFENSIVE evaluation of the user's own agent; note multi-turn / Crescendo attacks as a future extension dependent on `add-multi-turn-conversation-testing`; smoke-execute any fenced code blocks
- [ ] 8.3 Run `uv run pytest tests/`, `uv run ruff check src/ tests/`, `uv run mypy src/`, and a libdoc-render smoke of the new library
