# Changelog

All notable changes to **robotframework-agenteval** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(per NFR-MAINT-03).

## [Unreleased]

### Added

- Story 1a.5: project hygiene baseline shipped (7 deliverable categories):
  - **CONTRIBUTING.md** at repo root — dev setup, testing, Conventional Commits, DCO sign-off (`git commit -s`), code-style + conformance-suite requirement cross-refs, security-issue routing.
  - **SECURITY.md** full content (replaces Story 1a.1 placeholder) — private reporting channels, SLA table (ack ≤7 days / embargo ≤90 days), 5 security guarantees (credential redaction NFR-SEC-01, no-eval NFR-SEC-02, TLS NFR-SEC-03, supply-chain trust boundary NFR-SEC-04, no-phone-home NFR-SEC-05), CodeQL + dependency-pin posture.
  - **3 GitHub issue templates** at `.github/ISSUE_TEMPLATE/` (bug-report, feature-request, question) with frontmatter + structured prompts + cross-refs to SECURITY.md/SUPPORT.md.
  - **Apache 2.0 license headers** prepended to all 20 `.py` files under `src/AgentEval/` via `scripts/apply-license-headers.py` (idempotent). Companion `scripts/check-license-headers.py` verifies header presence; runs via pre-commit hook AND CI step (defense-in-depth).
  - **`.pre-commit-config.yaml`** at repo root — ruff (lint + format), mypy on src/, license-header check.
  - **`.github/workflows/ci.yml`** updated — new `License headers check (Apache 2.0)` step inserted between mypy and pytest collect-only sweep.
  - **`docs/contracts/coding-conventions.md`** filled with substantive content (replaces Story 1a.4 stub) — naming conventions table, type annotations + Literal/Protocol/PEP-695 idioms, Google docstring style with examples, FR59 error-message format pattern, comment policy (good/banned), `isort`-compatible import ordering example, test-naming conventions per category, license-header enforcement.
  - **3 new GitHub labels** created via `gh label create --force`: `good first issue` (description: "Suitable for newcomers; low-context, well-scoped"), `help wanted` (description: "Maintainer would welcome external contribution"), `documentation` (description: "Docs-only change; no code impact"). 3 default labels (`bug`, `enhancement`, `question`) verified present.
- Story 1a.5 closed 2 deferred Story 1a.3 review items:
  - **LOW-1**: ADR-014 §Decision bullet "9 leaves explicitly named" → "11 leaves explicitly named" (the leaf-inventory table is authoritative at 11; prose had drifted to 9).
  - **MED-2**: ADR-010 L37 cross-reference "(ADR-013)" → "(see ADR-003 §Decision — Generic LiteLLM-backed adapter inherits from `InProcessAdapter`)" (was incorrectly citing Entry-Points Discovery ADR; corrected to the actual base-class ADR).

- Story 1a.4: 11 doc-contract skeletons at `docs/contracts/` per architecture.md L1419-1430 (9 NFR-MAINT-04/Step-4/Step-5 canonical + 2 empirical adds; agentguard-inheritance.md retired 2026-05-17):
  - **5 PRD-named (NFR-MAINT-04):** `evidence-block-format.md` (Epic 5 owns content), `determinism-contract.md` (Epic 1b owns; includes `### Tier Model` subsection), `stability-surface.md` (Story 1a.6 + Epic 6; includes `### Sandbox Protocol Surface` subsection), `exit-criteria-0x-to-1x.md` (Epic 9 Story 9.3 owns), `otel-trace-visual.md` (Phase 2 owns).
  - **4 architecture-introduced:** `error-class-hierarchy.md` (**substantive content authored 2026-05-18** per AC-1a.4.2: FR59 error-format spec + 11-leaf ADR-014 table with per-leaf `error_code` + epic ownership), `mcp-coverage-detection.md` (Epic 5 Story 5.2), `conformance-fixture-format.md` (Epic 1b Story 1b.5), `coding-conventions.md` (Story 1a.5).
  - **2 empirical adds (2026-05-18 ratification):** `listener-integration.md` (Epic 5 Story 5.1; documents RF Listener v3 hook consumption + Story 0.1/0.2 stderr-fd + SIGTERM workarounds), `junit-xml-enrichment.md` (Epic 8a Story 8a.1; FR49 + FR50 mapping).
  - **`docs/adr/README.md` analogue:** `docs/contracts/README.md` index file with the 4-section template + 11-row sorted contract index + §Retired + §Excluded explicitly sections.
  - **`.github/workflows/docs-build.yml` first real run:** Per-file section assertion transitions from `::notice::Docs-build skipped: docs/contracts/ has no .md files (Phase-1 placeholder)` to `::notice::NFR-MAINT-04 per-file section-presence assertion passed for 12 file(s)` (11 contracts + README; README passes via code-block-literal-text — minor loophole, functionally correct).

- Story 1a.3: ratified 18 ADRs in `docs/adr/` + `docs/adr/README.md` index file (1136 lines of architectural-decision content total):
  - **14 new ADRs authored**: 9 PRD-renumbered (ADR-002 Tier-1 ceiling rule, ADR-003 CodingAgentAdapter Protocol internal class split, ADR-005 conformance fidelity oracles, ADR-006 completeness field, ADR-007 mcp_coverage + IncompleteTraceError, ADR-008 MCP spec version validation, ADR-009 per-test MCP server scope, ADR-010 Copilot CLI adapter trace extraction, ADR-011 three-persona model) + 5 architecture-renumbered (ADR-012 async-to-sync bridge kernel module, ADR-013 entry-points discovery infrastructure, ADR-014 error-class hierarchy, ADR-015 cost+runtime guardrail decorator, ADR-017 conformance suite organization).
  - **ADR-001 body authored**: Architectural Influences Catalog with 22 reviewed `robotframework-agentguard` patterns + 2 competitor MCP-eval projects + 2 industry standards (OTel GenAI semconv, MCP spec), each with explicit `adopt-verbatim` / `adapt` / `borrow-concept` / `explicitly-diverge` / `not-applicable` decision + rationale. §Scope + obligation framing explicit on the no-obligation posture (`agentguard inspiration-only` per `feedback_agentguard_inspiration_not_dependency`). §Amendments Log preserved byte-identical from Story 0.3 (sha256 gate verified) + 14 new ratification entries appended.
  - **`docs/adr/README.md`**: ADR convention paragraph + 18-row sorted index + cross-reference + maintenance instructions.
  - All cross-references resolve; all 18 ADRs `Status: accepted`; zero remaining stubs.

### Changed

- Story 1a.2 code-review patches (3 commits: f2ab79b → 6e654fd → 3d978af):
  - **HIGH-1**: `dogfood-integration.yml` downgraded to honest Phase-1 install-smoke. Previous version was fake-green — `continue-on-error: true` masked 72 rf-mcp test failures + 6 robotframework-agentskills collection errors caused by missing downstream deps in the wheel-only venv. Real cross-repo testing waits for Story 9.1+9.2.
  - **HIGH-3**: `release.yml` publish step gated on `startsWith(github.ref, 'refs/tags/v')`. workflow_dispatch from non-tag refs still builds (smoke) but cannot publish to PyPI, even when `TRUSTED_PUBLISHER_CONFIGURED=true`.
  - **MED-1**: Bumped `github/codeql-action/{init,analyze}@v3` → `@v4`.
  - **MED-3**: `docs-build.yml` section-presence check is now per-file (4 distinct sections per `docs/contracts/*.md`), replacing the aggregate-count check that allowed false-pass.
  - **MED-4**: `docs-build.yml` libdoc placeholder now sweep-imports all submodules via `pkgutil.walk_packages` instead of only the top-level `AgentEval` package.
  - **MED-6**: `dogfood-integration.yml` runs `uv sync --all-extras` before `uv build` per AC-1a.2.5 spec text.
  - **LOW-1**: Dismissed CodeQL alert #2 (`src/AgentEval/security/protocols.py:54 py/ineffectual-statement`) as PEP 544 false positive (`...` Protocol-body convention).
  - **LOW-1a / Round-2 NEW MED**: CodeQL `paths-ignore` moved to `.github/codeql/codeql-config.yml` + referenced via `config-file:` input (CodeQL v4 silently rejects `paths-ignore` as a workflow input). Spike + skill paths now correctly excluded.
  - **LOW-2**: `nightly-live.yml` writes pass/fail summary table to `$GITHUB_STEP_SUMMARY` per AC-1a.2.2.

### Added

- 7 GitHub Actions CI workflows (Story 1a.2):
  - `ci.yml` — PR-gating: Python 3.12+3.13 × ubuntu-latest (Linux-only per D2.1 macOS waiver inherited from Story 0.2); `uv sync --all-extras` + `ruff check` + `ruff format --check` + `mypy src/` + Phase-1 collect-only sweep across tests/unit, tests/acceptance/smoke, tests/acceptance/tier1, tests/unit/conventions.
  - `nightly-live.yml` — NFR-REL-03: daily 06:00 UTC cron + workflow_dispatch; pytest -m live + tier3 Phase-1 collect-only.
  - `conformance.yml` — Per-release + workflow_dispatch; tests/conformance Phase-1 collect-only (harness lands Story 1b.5).
  - `security-scan.yml` — CodeQL on every PR + push to main + weekly full-repo scan (Monday 06:00 UTC); replaces retired `agentguard-drift-check.yml`.
  - `dogfood-integration.yml` — NFR-REL-05: workflow_dispatch + release + PR-with-`release-pending`-label; builds local agenteval wheel + clones rf-mcp + robotframework-agentskills + runs their pytest against the wheel; `continue-on-error: true` Phase-1 (removed in Story 9.1+9.2).
  - `docs-build.yml` — NFR-MAINT-04: workflow_dispatch + release + PR path-filtered (docs/contracts/** OR src/AgentEval/**/*.py); grep-based section-presence check (`## Purpose / ## Scope / ## Contract / ## Change Policy`) with empty-dir graceful skip.
  - `release.yml` — NFR-MAINT-03: tag push `v[0-9]+.[0-9]+.[0-9]+*` + workflow_dispatch; `uv build` + `uv publish` via PyPI OIDC trusted publishing (`id-token: write`); Phase-1 dry-run mechanic via `vars.TRUSTED_PUBLISHER_CONFIGURED` (flipped to `true` in Story 9.1 once PyPI claim is registered).
  - Added `tests/unit/conventions/` directory (architecture-mandated dir missing from Story 1a.1 baseline; needed for ci.yml conventions test step).
  - All workflows: pinned actions (`actions/checkout@v4` + `astral-sh/setup-uv@v3` + `github/codeql-action/{init,analyze}@v3`); `timeout-minutes: 10` on every job; concurrency cancel-in-progress on `ci.yml`.

## [0.0.1] — 2026-05-17

### Added

- Initial repository scaffolding (Story 1a.1):
  - `pyproject.toml` with src-layout (`src/AgentEval/`) + hatchling build backend.
  - Dependencies: `mcp==1.27.1`, `robotframework==7.4.2`, `anyio==4.13.0` (exact pins per Story 0.1/0.2 spike validation); `litellm`, `opentelemetry-api`, `opentelemetry-sdk`, `pyyaml`, `jsonschema` (range pins with upper-bound caps).
  - `[dev]` extras: `pytest`, `pytest-cov`, `ruff`, `mypy`, `robotframework-pabot==5.2.2`.
  - Empty entry-point tables (6 total): 4 `agenteval.*` discovery groups (coding_agents, providers, judges, sandboxes per ADR-018) + 1 legacy `robotframework_agenteval.adapters` (FR17a) + 1 RF-owned `robot.listener` (FR33a). Plus `[project.scripts] agenteval = "AgentEval.cli:main"` per FR18; cli.py is a Phase-1 placeholder (real subcommands `init` + `new-adapter` ship in Epic 8b).
  - `src/AgentEval/` skeleton with 16 sub-packages, each with `__init__.py`. Plus `src/AgentEval/cli.py` (Phase-1 placeholder), and 3 security stubs per ratified ADR-018 (`security/protocols.py` — SandboxBackend Protocol; `security/null_sandbox.py` — refuses every execute(); `security/policy.py` — gate placeholder for Epic 6 wiring).
  - `tests/{unit, integration, conformance, benchmarks, fixtures}/` directories.
  - `docs/{contracts, recipes, scenarios, keywords, coming-from, troubleshooting}/` directories. (`docs/adr/` pre-exists with 4 ratified ADRs from Story 0.3.)
  - `examples/` directory.
  - Config files: `.python-version`, `.gitignore`, `LICENSE` (Apache-2.0), `ruff.toml`, `mypy.ini`, `.env.example`.
  - Doc files: `README.md`, `CHANGELOG.md`, `MAINTAINERS.md`, `SUPPORT.md`.

### Known limitations

- macOS validation deferred to Phase-1.5 per D2.1 architect waiver (inherited from Story 0.2 review). Story 1a.1 only validates `uv sync` on Linux.
- Empty package — no public API yet. `import AgentEval` succeeds but exposes only `__version__`. Sub-libraries land in Epic 1b onward.

### References

- ADR-004 (was ADR-007) — hosted-MCP universal observation pattern
- ADR-016 (was ADR-A6) — MCP coverage detection default (D1 trust-floor + D4 adapter contract)
- ADR-018 (was ADR-A8) — sandbox Phase 1 policy
- ADR-001 (stub) — architectural influences catalog (body filled by Story 1a.3)
