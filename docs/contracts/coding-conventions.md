# Coding Conventions

**Status:** Phase-1 skeleton — content to be filled by Story 1a.5 (Project Hygiene — CONTRIBUTING + SECURITY + Issue Templates + License Headers).
**Owning epic:** Story 1a.5
**Related ADRs:** none directly; informed by every authored ADR's prose style + the architecture's Step-5 reference card.
**Related references:** `CONTRIBUTING.md` (Story 1a.5 deliverable), `pyproject.toml` ruff + mypy configurations.

## Purpose

Documents agenteval's **coding conventions** as a side-by-side good/anti-pattern reference card. Per architecture Step-5, this contract is the single artifact contributors consult before opening a PR. The CI surface (`ci.yml`'s ruff + mypy steps) enforces what's enforceable; this doc covers the human-judgment-level conventions (naming, docstring style, comment policy, error-message wording, type-annotation idioms).

## Scope

### In-scope

- Naming conventions: modules, classes, functions, variables, constants, RF keywords.
- Type annotations: where required, which idioms preferred (e.g., `Literal[...]` for closed sets, `Protocol` for structural typing).
- Docstring style: format, when required, content.
- Error messages: format requirements (FR59 surface — file path, line, field, fix suggestion) + per-error-class wording rules.
- Comment policy: where comments are required, where they're discouraged.
- Import ordering: ruff-enforced (`isort`-compatible).
- Test-naming conventions: per `tests/<dir>/test_*.py` files.

### Out-of-scope

- Ruff + mypy rule lists — those live in `ruff.toml` + `mypy.ini`. This contract covers the human-judgment dimension; the config files are the machine-enforced one.
- Per-keyword libdoc style — that's a separate per-keyword consideration governed by RF Library conventions.

## Contract

*Phase-1 skeleton — Story 1a.5 fills in the formal specification.*

The contract will at minimum include:

- A 2-column table per convention category: ✅ good pattern (with code snippet) | ❌ anti-pattern (with code snippet) + the CI check that catches the anti-pattern.
- Pointer to `ruff.toml` for machine-enforced subset.
- Pointer to `mypy.ini` for type-check rules.
- Cross-reference to `CONTRIBUTING.md` for the PR workflow.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The conventions are `provisional` in Phase 1 — Story 1a.5 finalizes the initial set; downstream stories may propose additions. Major changes (e.g., re-styling all docstrings) require an ADR amendment to avoid churn.

## References

- Architecture Step-5 reference card (the source for this contract's structure)
- `CONTRIBUTING.md` (Story 1a.5 deliverable)
- `ruff.toml` (Story 1a.1 baseline; Story 1a.5 may iterate)
- `mypy.ini` (Story 1a.1 baseline)
- PEP 8 + PEP 484 + PEP 526 for Python idioms (cited as base; agenteval may diverge)
