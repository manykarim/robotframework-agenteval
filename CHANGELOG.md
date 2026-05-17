# Changelog

All notable changes to **robotframework-agenteval** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(per NFR-MAINT-03).

## [Unreleased]

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
