# Contributing to robotframework-agenteval

Thanks for your interest in contributing. agenteval is a Robot Framework library for evaluating AI coding agents. This document covers what you need to know to land a change.

> **Quick links:** [Setup](#setup) · [Testing](#testing) · [Pull Request Workflow](#pull-request-workflow) · [DCO Sign-off](#dco-sign-off-required) · [Code Style & Conventions](docs/contracts/coding-conventions.md) · [Architecture Decisions](docs/adr/README.md) · [Security Issues](SECURITY.md) · [Triage SLA](SUPPORT.md)

## Setup

agenteval uses [`uv`](https://docs.astral.sh/uv/) for environment + dependency management. Python 3.12+ is required.

```bash
# Clone + enter the repo
git clone https://github.com/manykarim/robotframework-agenteval.git
cd robotframework-agenteval

# Install all dev + production deps into a project-local venv
uv sync --all-extras

# Install pre-commit hooks (runs ruff, mypy, license-header check on every commit)
uv run pre-commit install
```

Phase-1 baseline supports **Linux only** (`ubuntu-latest` in CI). macOS validation is a Phase-1.5 carry-over per the D2.1 architect waiver (Story 0.2 review). Windows is out of scope.

## Testing

```bash
# Unit tests — fast; safe to run on every save
uv run pytest tests/unit -q

# Acceptance smoke + tier1 — broader coverage
uv run pytest tests/acceptance/smoke -q
uv run pytest tests/acceptance/tier1 -q

# Conformance suite — adapter-specific (slow; runs in conformance.yml per release)
uv run pytest tests/conformance --adapter <name>

# Robot Framework integration — **Phase-1 status: forward-reference.**
# The `AgentEval.telemetry.listener` module lands in Epic 5 Story 5.1; the
# command below is NOT runnable on Phase-1 builds (commit 90d6f5c). Phase-1
# users can run RF tests without the agenteval listener via `uv run robot tests/`
# (no per-test scoping; no OTel spans emitted).
uv run robot --listener AgentEval.telemetry.listener tests/
```

**Phase-1 note:** several test directories are empty placeholders (Story 1a.1 created `.gitkeep` markers). Running `pytest` against them yields "no tests collected" which is acceptable for Phase 1 — the [`ci.yml`](.github/workflows/ci.yml) workflow handles this via the exit-5 leniency in its collect-only sweep step. Real tests land per-epic as fixtures are authored.

## Pull Request Workflow

### Conventional Commits

Commit messages MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) subset:

```
<type>(<scope>): <subject>

<optional body>

<optional footer>
```

Valid types: `feat | fix | docs | refactor | test | chore | ci | build`. Scope is the affected sub-library (e.g., `mcp`, `coding_agent`, `telemetry`).

Examples:

```
feat(mcp): add hosted-MCP universal observer per ADR-004

fix(ci): bump CodeQL action v3 → v4 to silence December 2026 deprecation

docs(adr): ratify 14 non-spike ADRs + author ADR-001 catalog per Story 1a.3
```

PR titles MUST follow the same format. Single-commit PRs use the commit message as the title.

### Branch naming

`<type>/<short-slug>` — e.g., `feat/hosted-mcp-observer`, `fix/codeql-v4-bump`.

### Link to issue

Every PR description SHOULD link to a GitHub issue (or a planning artifact). A `.github/pull_request_template.md` PR-template file is a future hygiene deliverable (not yet present at commit `90d6f5c`); until then this is a convention enforced by reviewer feedback rather than automated checks.

## DCO Sign-off (required)

agenteval requires the [Developer Certificate of Origin](https://developercertificate.org/) (DCO) on every commit. This is a lightweight statement that you have the right to contribute the code (you wrote it, or you have license to upstream it).

To sign off, add the `-s` flag when committing:

```bash
git commit -s -m "feat(mcp): add hosted-MCP universal observer per ADR-004"
```

This appends a trailer to the commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

PRs without DCO sign-off will be asked to amend their commits during review. A CI-side DCO check is a forthcoming hygiene deliverable (tracked as project debt — see [Project Debt Registry](_bmad-output/implementation-artifacts/sprint-status.yaml)); until then maintainers verify the trailer manually during PR review.

DCO sign-off is the project standard chosen on merit for agenteval's contribution model (solo + AI-agent-assisted maintainership per [MAINTAINERS.md](MAINTAINERS.md)). It is lighter-weight than a CLA — no separate document to sign; the sign-off lives in the commit message.

## Cross-LLM Code Review (project standard)

agenteval mandates **cross-LLM adversarial review** for every Tier-2 / Tier-3 keyword PR + every architecture-touching change. Per `feedback_review_methodology_norms` (Epic 0 retro ratification, 2026-05-17), reviews come from ≥2 different LLM families to catch single-model blind spots. 30+ load-bearing catches across Epics 2-7 prove this is not theatre.

### Three supported reviewer CLIs

| CLI | Invocation | When to use |
|---|---|---|
| Claude CLI | `claude -p --dangerously-skip-permissions --model opus "$(cat /tmp/review-prompt.md)"` | Primary reviewer for code + spec reviews. |
| Codex CLI | `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "$(cat /tmp/review-prompt.md)"` | Second-LLM-family adversarial. Catches behavioral edges the type-system review misses (`feedback_codex_probe_fitness`). |
| kilocode CLI (preconfigured minimax) | `~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7 "$(cat /tmp/review-prompt.md)"` | **Third-LLM-family fallback** per `feedback_third_llm_family_fallback` (Epic 10 retro candidate). 9 consecutive substantive reviews across Epic 8 + 9 + 10 retro-batch. Operationally proven when Claude + Codex CLIs degrade. |

### What a review prompt should contain

- **Story spec path** — `_bmad-output/implementation-artifacts/X-Y-*.md`
- **New + modified files** list
- **Project conventions to verify** — ADR references, ratified `feedback_*` norms, specific empirical claims to re-derive
- **Specific shape probes** — e.g., "Does the real SDK expose attribute X?" (`feedback_listener_hook_api_surface_empirical_check`)
- **Output shape ask** — HIGH/MED/LOW ranked critiques + line numbers + concrete patches
- End with: `Overall: ratify-as-is / ratify-with-patches / reject-and-revise`

A canonical prompt template lives at `/tmp/kilo-batch-prompt-template.md` — written during the Epic 8 + 9 retro-batch.

### When to escalate to the third-LLM fallback

If Claude CLI returns 0-byte output (silent degradation pattern) OR Codex CLI returns the usage-limit error after a single retry, **switch to kilocode/minimax** rather than ship without cross-LLM review. The 8-story degraded-review streak documented in Epic 8 retro Action #1 represented real lost quality signal — the third-LLM fallback was operationally validated in the Epic 8 + 9 kilo/minimax retro-batch (commit `16ee936`, 8 HIGH patches across 7 stories).

For the canonical pattern + the 8 load-bearing catches the third-LLM delivered, see [`_bmad-output/implementation-artifacts/epic-8-9-kilo-minimax-cross-review-2026-05-26.md`](_bmad-output/implementation-artifacts/epic-8-9-kilo-minimax-cross-review-2026-05-26.md).

### Recording the review in the story spec

Append a `## Senior Developer Review (AI)` section to the story spec with:
- Reviewer CLI invocation
- Outcome (`ratify-as-is` / `ratify-with-patches` / `reject-and-revise` / `degraded`)
- Per-finding bullets (severity, file:line, problem, patch applied or deferred)
- A Significance note explaining what the review caught that the dev would have missed

Then increment the story's Change Log table with a new version row (e.g., `v0.4.0`) crediting the review. See `_bmad-output/implementation-artifacts/10-1-claude-agent-sdk-adapter.md` for an end-to-end example.

## Code Style & Conventions

All Python code follows the conventions documented in [`docs/contracts/coding-conventions.md`](docs/contracts/coding-conventions.md). Highlights:

- **Naming:** lowercase_snake for modules + functions + variables; PascalCase for classes; UPPER_SNAKE for constants.
- **Type annotations:** required on every public function and method. Prefer `Literal[...]` for closed sets; `Protocol` for structural typing.
- **Docstrings:** Google style. Required on every public function and class.
- **Error messages:** Tier-1 setup-failure errors follow FR59 format (see [`docs/contracts/error-class-hierarchy.md`](docs/contracts/error-class-hierarchy.md)).
- **License header:** every Python source file under `src/AgentEval/` MUST start with the Apache 2.0 license header (see Story 1a.5's `scripts/apply-license-headers.py`). The pre-commit hook + the CI `License headers check` step enforce this.

`ruff` enforces the machine-checkable subset (configured in `ruff.toml`); `mypy` checks types (configured in `mypy.ini`). The pre-commit hooks run both on every commit.

## Conformance Suite Requirement

Every Tier-2 / Tier-3 keyword PR MUST include a conformance fixture per [`docs/contracts/conformance-fixture-format.md`](docs/contracts/conformance-fixture-format.md). Conformance fixtures are JSON files at `tests/conformance/fixtures/<adapter_name>/<scenario_name>.json` that capture the canonical `AgentRunResult` an adapter should produce when run against a fixed scenario from the deterministic mock harness.

This is the "fidelity oracle" mechanism per [ADR-005](docs/adr/ADR-005-conformance-suite-fidelity-oracles.md) — structural conformance is necessary but not sufficient; golden fixtures defend against well-meaning-but-broken adapters AND adversarially-passing ones.

## Architecture Decisions

agenteval documents architectural decisions in [`docs/adr/`](docs/adr/README.md). 19 ADRs are ratified as of Phase 1 close (ADR-001 catalog + ADR-002 → ADR-019). Read the index + [`ADR-001` Architectural Influences Catalog](docs/adr/ADR-001-architectural-influences-catalog.md) before proposing structural changes — agenteval inherits patterns from `robotframework-agentguard` (one of several reviewed references) but is **INSPIRATION ONLY**, not a dependency, and free to diverge anywhere.

New architectural decisions follow the [MADR](https://adr.github.io/madr/) template (Context / Decision / Consequences / Alternatives). Propose new ADRs via PR.

## Security Issues

**Do NOT file public GitHub Issues for security reports.** Use the private channels documented in [SECURITY.md](SECURITY.md):

- GitHub private security advisory (preferred — provides an embargo'd discussion thread)
- Direct email to the maintainer (see [MAINTAINERS.md](MAINTAINERS.md) for the address)

Expected acknowledgement: ≤7 calendar days. Embargo: ≤90 calendar days, coordinated with the reporter.

## Triage SLA

agenteval is solo + AI-agent-assisted maintained ([MAINTAINERS.md](MAINTAINERS.md)). Best-effort issue-triage SLA is **5 business days** ([SUPPORT.md](SUPPORT.md)). Security issues are prioritized.

If your org needs contracted SLA or indemnification, pair with a paid-support arrangement or fork.

## Code of Conduct

agenteval follows the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) by reference. Until this project adds a project-specific Code of Conduct file, the upstream Contributor Covenant text governs interactions in issue threads, PR reviews, and any project communication channels.

## Questions?

Open a [Question](.github/ISSUE_TEMPLATE/question.md) issue. Or open a Draft PR with your work-in-progress and ask for early feedback.

Thank you for contributing.
