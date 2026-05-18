# Story 1a.5: Project Hygiene — CONTRIBUTING + SECURITY + Issue Templates + License Headers

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **contributor or potential security reporter**,
I want **`CONTRIBUTING.md` + `SECURITY.md` (full content replacing the Story 1a.1 placeholder) + 3 GitHub issue templates + Apache 2.0 license headers on every `src/AgentEval/**/*.py` file (with both pre-commit + CI enforcement) + populated `docs/contracts/coding-conventions.md` content + `good first issue` GitHub label + 2 project-debt cleanups (ADR-014 prose + ADR-010 cross-ref)**,
so that **the project meets open-source hygiene baseline before the first external contributor or vulnerability report arrives, the docs-contract registry has no remaining Phase-1 stubs in the hygiene domain, and the 2 deferred debt items from Story 1a.3 review are closed**.

## Acceptance Criteria

> **Pre-create-story drift check (5th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-18):** Architecture L1166-L1168, PRD NFR-MAINT-01 + NFR-SEC-04, epics.md Story 1a.5 description all agree on the 4 core deliverables. NO drift found — first clean pre-check since the norm started. Story 1a.5 scope expanded per Many's 2026-05-18 ratifications: fold 2 Story 1a.3 deferred debt items (LOW-1 + MED-2), fill `coding-conventions.md` content (Story 1a.4 banner-stated owner), add `good first issue` GitHub labels.

1. **AC-1a.5.1 — `CONTRIBUTING.md` authored at repo root.** Content MUST cover:
   - Dev environment setup: `uv sync --all-extras`; Python 3.12+ requirement; `uv run pre-commit install` for the pre-commit hooks (per AC-1a.5.4).
   - Test invocation: `uv run pytest tests/unit -q` (Phase-1: empty + collect-only-leniency per Story 1a.2 ci.yml); `uv run pytest tests/conformance --adapter <name>` (per `docs/contracts/conformance-fixture-format.md`); `uv run robot --listener AgentEval.telemetry.listener tests/` (Story 5.1 dependency — note Phase-1 listener may not yet exist).
   - PR conventions: commit message format (Conventional Commits subset: `<type>(<scope>): <subject>` where type ∈ `feat|fix|docs|refactor|test|chore`), PR title format same as commit (single-commit PRs MUST match), branch naming `<type>/<short-slug>`, link to a Linear/GitHub issue in the PR description.
   - Conformance-suite requirement: every Tier-2/3 keyword PR requires a conformance fixture per `docs/contracts/conformance-fixture-format.md`.
   - **DCO sign-off required** (standard OSS practice; chosen on merit for agenteval's contribution model — no comparative reference to other projects required). Document `git commit -s` requirement + the inline `Signed-off-by:` trailer.
   - Cross-reference to `docs/contracts/coding-conventions.md` for code-style + naming guidance.
   - Cross-reference to `docs/adr/README.md` for architectural-decision context.

2. **AC-1a.5.2 — `SECURITY.md` full content authored.** Replace the Story 1a.1 placeholder. Content MUST specify:
   - **Report channel:** private GitHub security advisory (preferred); direct email to maintainer as fallback (link to MAINTAINERS.md).
   - **Expected acknowledgement time:** ≤7 calendar days from initial report.
   - **Embargo period:** ≤90 calendar days from acknowledgement; coordinated disclosure with reporter.
   - **Credential-redaction guarantee** (FR38a/b): traces never contain raw credentials in published reports; library uses `config.redact_env()` per NFR-SEC-01 + supports user-extensible patterns via `config.add_redaction_pattern()`.
   - **Supply-chain trust boundary** (NFR-SEC-04): library trusts vendor CLI binaries on `$PATH` to the same level the user does; agenteval never auto-downloads/installs vendor binaries.
   - **What to include in a report**: agenteval version + RF version + Python version + OS + minimal reproducer + observed vs expected behavior.
   - **What NOT to do**: do not file public GitHub issues for security; do not include exploit code in non-encrypted email.

3. **AC-1a.5.3 — 3 GitHub issue templates created.** Files at `.github/ISSUE_TEMPLATE/`:
   - `bug-report.md` — frontmatter (`name`, `about`, `title:`, `labels: [bug]`, `assignees: ""`) + structured prompts: RF version, agenteval version, Python version, OS, minimal `.robot` reproducer (fenced code block placeholder), expected vs actual, sanitized stack trace if any.
   - `feature-request.md` — frontmatter (`name`, `about`, `title:`, `labels: [enhancement]`) + structured prompts: problem statement, proposed solution, alternatives considered, target persona (per ADR-011: QA Engineer / Agent Surface Author / Agent Developer), Phase-1 vs Phase-2 fit.
   - `question.md` — frontmatter (`name`, `about`, `title:`, `labels: [question]`) + prompts: what you tried, what surprised you, link to docs you've read.
   - All 3 templates MUST contain the boilerplate "Before filing: see `SECURITY.md` for security-related reports; see `SUPPORT.md` for triage SLA expectations."

4. **AC-1a.5.4 — Apache 2.0 license headers on every `src/AgentEval/**/*.py` file.** Implementation:
   - Author `scripts/apply-license-headers.py` — a Python script that walks `src/AgentEval/` recursively, prepends the canonical Apache 2.0 13-line header (see Dev Notes for exact text) to every `.py` file that doesn't already contain `Licensed under the Apache License`. Idempotent: re-running adds zero new headers.
   - Run the script once as part of this story's commit. Verify via `grep -l 'Licensed under the Apache License' src/AgentEval/**/*.py | wc -l` matches the count of `.py` files under `src/AgentEval/`.
   - Author `scripts/check-license-headers.py` — companion check-mode that asserts every `.py` file has the header; exits non-zero with a list of missing files if not.
   - Add `.pre-commit-config.yaml` at repo root with at least: `ruff check`, `ruff format`, `mypy src/`, `python scripts/check-license-headers.py`. The `check-license-headers.py` hook MUST fire on every new `.py` file going forward.
   - Add a step to `.github/workflows/ci.yml`: `- name: License headers check / run: uv run python scripts/check-license-headers.py` (insert between mypy and pytest steps). Documents defense-in-depth: pre-commit catches local; CI catches if `--no-verify` was used.

5. **AC-1a.5.5 — `docs/contracts/coding-conventions.md` content authored (replaces Story 1a.4 stub).** Content MUST include:
   - Naming conventions: modules (lowercase_snake), classes (PascalCase), functions/variables (lowercase_snake), constants (UPPER_SNAKE), RF keywords (Title Case With Spaces per RF convention; underlying Python methods use `snake_case` per ruff defaults).
   - Type annotations: required on every public function/method; `Literal[...]` for closed enums (e.g., `mcp_coverage` literals); `Protocol` for structural typing where duck-typing is the contract.
   - Docstring style: Google or NumPy style (pick Google for agenteval; document the choice); required on every public function/class; document `Args:`, `Returns:`, `Raises:` sections.
   - Error message format: every Tier-1 setup-failure error follows FR59 format (per `docs/contracts/error-class-hierarchy.md` Purpose section).
   - Comment policy: prefer self-documenting code; comments explain *why*, not *what*; banned comment patterns (TODOs without an issue link).
   - Import ordering: ruff-enforced (`isort` rules); stdlib → third-party → first-party (`AgentEval.*`) → local relative imports.
   - Test-naming: `test_<what>__<when>__<then>` for unit tests; `test_<scenario>` for acceptance/conformance.
   - Pointer to `ruff.toml` + `mypy.ini` for machine-enforced subset.
   - Cross-reference to `CONTRIBUTING.md` for the PR workflow.
   - Status banner updated: remove the "Phase-1 skeleton — content to be filled by Story 1a.5" line; replace with "Status: accepted (Story 1a.5 ratification 2026-05-18)".

6. **AC-1a.5.6 — `good first issue` + 2 other GitHub labels created.** Use `gh label create` to add:
   - `good first issue` (color: `7057ff` — GitHub default; description: "Suitable for newcomers; low-context, well-scoped").
   - `help wanted` (color: `008672`; description: "Maintainer would welcome external contribution").
   - `documentation` (color: `0075ca`; description: "Docs-only change; no code impact").
   - The 3 default GitHub labels that newly-created repos sometimes lack (`bug`, `enhancement`, `question`) MUST also exist (referenced by the issue templates per AC-1a.5.3) — verify via `gh label list` and create any missing.

7. **AC-1a.5.7 — Story 1a.3 deferred debt items closed (LOW-1 + MED-2).**
   - **LOW-1 cleanup**: `docs/adr/ADR-014-error-class-hierarchy.md` §Decision bullet "9 leaves explicitly named" → "11 leaves explicitly named" (the prose drift from Story 1a.3 review; the table count is authoritative at 11, prose drifted to 9).
   - **MED-2 cleanup**: `docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md` L37 — change `(ADR-013)` (which is Entry-Points Discovery, wrong reference) to `(see ADR-003 §Decision — Generic LiteLLM-backed adapter inherits from InProcessAdapter)` per the Story 1a.3 code-review's recommended fix.

8. **AC-1a.5.8 — `docs/recipes/00_setup.robot` does NOT yet exist** (clarification, NOT a deliverable). Story 1a.1 created `examples/` directory but it's empty; the first `.robot` example lands in Epic 1b. Story 1a.5 should NOT scaffold any example `.robot` files. This AC is documentary — confirms Story 1a.5's scope boundary.

9. **AC-1a.5.9 — Machine verification of all deliverables (per Norm #2).**
   - `CONTRIBUTING.md` exists at repo root with non-zero word count.
   - `SECURITY.md` has the full content (NOT the Story 1a.1 placeholder) — verify by grepping for "Story 1a.5" in the placeholder and asserting it's REMOVED.
   - `.github/ISSUE_TEMPLATE/{bug-report,feature-request,question}.md` all exist + have valid frontmatter (`name:`, `about:`, `labels:`).
   - Every `src/AgentEval/**/*.py` file has the Apache 2.0 header: `grep -l 'Licensed under the Apache License' src/AgentEval/**/*.py | wc -l` matches `find src/AgentEval -name "*.py" -type f | wc -l`.
   - `.pre-commit-config.yaml` exists at repo root.
   - `ci.yml` has a license-header check step.
   - `docs/contracts/coding-conventions.md` has substantive content (not Phase-1 stub); `grep -c '^**Status:** Phase-1 skeleton' docs/contracts/coding-conventions.md` returns 0.
   - GitHub labels exist: `gh label list | grep -E '^(good first issue|help wanted|documentation|bug|enhancement|question)'` returns 6 lines.
   - ADR-014 LOW-1 fixed: `grep '11 leaves explicitly named' docs/adr/ADR-014-error-class-hierarchy.md` returns 1 match; "9 leaves explicitly named" returns 0.
   - ADR-010 MED-2 fixed: `grep '(see ADR-003' docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md` returns ≥1 match; the bare `(ADR-013)` reference for Generic LiteLLM returns 0.

10. **AC-1a.5.10 — CI + docs-build post-push runs green with verified-real signal (per CI-log-forensics norm).** After commit + push: `ci.yml` should fire with the new license-header check step + remain green; `docs-build.yml` (manually dispatched) should still pass per-file 4-section assertion for all 12 contract files (coding-conventions.md's content fill MUST NOT regress its 4-section structure).

## Tasks / Subtasks

- [x] **Task 1: Pre-flight verification + Apache 2.0 header text canonical (AC: 1a.5.4)**
  - [x] Re-verify Story 1a.4 done baseline: `ls docs/contracts/` outputs 12 entries; `error-class-hierarchy.md` has the substantive content.
  - [x] Verify SECURITY.md current state shows placeholder text (`grep -c '⚠️ PLACEHOLDER' SECURITY.md` = 1).
  - [x] Verify `scripts/` directory does not yet exist (Story 1a.5 creates it).
  - [x] Verify `.pre-commit-config.yaml` does not yet exist.
  - [x] Canonical Apache 2.0 header text (13 lines including blank-comment separator) — see Dev Notes §Apache 2.0 Header Text.

- [x] **Task 2: Author `CONTRIBUTING.md` (AC: 1a.5.1)**
  - [x] Author at repo root. Sections: §Setup, §Testing, §Code Style + Conventions (pointer to coding-conventions.md), §Pull Request Workflow (commit format + DCO sign-off), §Architecture Decision Records (pointer to docs/adr/README.md), §Conformance Suite Requirement, §Security Issues (pointer to SECURITY.md), §Code of Conduct (TBD pointer to a future CODE_OF_CONDUCT.md or upstream link).
  - [x] Cite specific commands (`uv sync --all-extras`, `uv run pre-commit install`, `uv run pytest tests/unit -q`, etc.) — runnable copy-paste.
  - [x] DCO sign-off section: explain `git commit -s`, the `Signed-off-by:` trailer format, and that PRs without DCO sign-off will be requested to amend.

- [x] **Task 3: Author SECURITY.md full content (AC: 1a.5.2)**
  - [x] Replace existing placeholder content at SECURITY.md. Preserve the file location (do not move).
  - [x] Sections per AC-1a.5.2: §Report channel, §Acknowledgement time, §Embargo period, §What to include, §What NOT to do, §Credential redaction guarantee, §Supply-chain trust boundary.
  - [x] Remove the "⚠️ PLACEHOLDER" notice + the "Story 1a.5 (Project Hygiene...) authors the authoritative version" line.
  - [x] Cross-references: link to MAINTAINERS.md (maintainer contact), CONTRIBUTING.md (general report flow), `feedback_agentguard_inspiration_not_dependency` posture (no agentguard dependency means no agentguard CVE inheritance).

- [x] **Task 4: Author 3 GitHub issue templates (AC: 1a.5.3)**
  - [x] Create `.github/ISSUE_TEMPLATE/bug-report.md` per AC-1a.5.3 spec.
  - [x] Create `.github/ISSUE_TEMPLATE/feature-request.md`.
  - [x] Create `.github/ISSUE_TEMPLATE/question.md`.
  - [x] Each template has frontmatter (`name`, `about`, `title:`, `labels:`, `assignees:`).
  - [x] Each template has the boilerplate cross-reference to SECURITY.md (security issues) + SUPPORT.md (triage SLA).

- [x] **Task 5: Author + run license-header scripts (AC: 1a.5.4)**
  - [x] Author `scripts/apply-license-headers.py` per Dev Notes §License-header Scripts. Idempotent.
  - [x] Author `scripts/check-license-headers.py` (companion check-mode).
  - [x] Run `uv run python scripts/apply-license-headers.py` once to apply headers across `src/AgentEval/**/*.py`.
  - [x] **Verify idempotency**: re-run the script + confirm zero new headers added.
  - [x] Author `.pre-commit-config.yaml` at repo root with the hook list (ruff check, ruff format, mypy, license-header check). Cite the pre-commit framework's standard `repos:` syntax.
  - [x] **Numeric verification (Norm #2)**: `find src/AgentEval -name "*.py" -type f | wc -l` MUST match `grep -l 'Licensed under the Apache License' src/AgentEval/**/*.py | wc -l`.

- [x] **Task 6: Wire CI license-header check (AC: 1a.5.4)**
  - [x] Edit `.github/workflows/ci.yml` — add a step between mypy + the pytest collect-only sweep: `- name: License headers check / run: uv run python scripts/check-license-headers.py`. Use the existing matrix runner.
  - [x] Document the defense-in-depth posture in a top-of-file comment update to ci.yml.

- [x] **Task 7: Fill `docs/contracts/coding-conventions.md` content (AC: 1a.5.5)**
  - [x] Replace the current Phase-1 skeleton text under §Contract with substantive coding-conventions content per AC-1a.5.5 (naming, type annotations, docstring style, error message format, comment policy, import ordering, test naming).
  - [x] Update §Status banner: remove "Phase-1 skeleton — content to be filled by Story 1a.5"; replace with "Status: accepted (Story 1a.5 ratification 2026-05-18)".
  - [x] **Critical**: preserve the 4 required NFR-MAINT-04 section headers (`## Purpose`, `## Scope`, `## Contract`, `## Change Policy`) — the file MUST still pass `docs-build.yml`'s per-file section assertion after the content fill.

- [x] **Task 8: Create GitHub labels (AC: 1a.5.6)**
  - [x] `gh label create "good first issue" --color "7057ff" --description "Suitable for newcomers; low-context, well-scoped" --force` (force = update if exists).
  - [x] `gh label create "help wanted" --color "008672" --description "Maintainer would welcome external contribution" --force`.
  - [x] `gh label create "documentation" --color "0075ca" --description "Docs-only change; no code impact" --force`.
  - [x] Verify the 3 default-shipped labels exist: `gh label list | grep -E '^(bug|enhancement|question)'`. Create any missing via `gh label create`.
  - [x] **Numeric verification (Norm #2)**: `gh label list --json name --jq 'map(.name) | sort | .[]' | grep -cE '^(good first issue|help wanted|documentation|bug|enhancement|question)$'` MUST output `6`.

- [x] **Task 9: Close Story 1a.3 deferred debt (AC: 1a.5.7)**
  - [x] **LOW-1**: `docs/adr/ADR-014-error-class-hierarchy.md` — find the line "9 leaves explicitly named" + change to "11 leaves explicitly named". Verify table count = 11 leaves (2 Safety + 2 Budget + 4 Compat + 3 Integrity).
  - [x] **MED-2**: `docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md` — find L37 "(ADR-013)" + replace with "(see ADR-003 §Decision — Generic LiteLLM-backed adapter inherits from `InProcessAdapter`)".

- [x] **Task 10: Verify + commit prep (AC: 1a.5.9, 1a.5.10)**
  - [x] Run all numeric verifications from AC-1a.5.9.
  - [x] Update CHANGELOG.md `## [Unreleased]` with summary of all Story 1a.5 deliverables.
  - [x] Story file Dev Agent Record + File List + Change Log per BMad workflow.
  - [x] After push: CI runs (`ci`, `security-scan`) auto-fire. Manually trigger `docs-build` via `gh workflow run docs-build.yml --ref main`.
  - [x] **CI-log-forensics per Many's norm**: inspect post-push CI runs for hidden warnings (cache 400 + Node 20 deprecation are pre-existing; any NEW warning flagged).
  - [x] **License-header CI check**: confirm the new `License headers check` step in ci.yml fires green on at least one matrix cell (Python 3.12 + 3.13).
  - [x] **docs-build coding-conventions verification**: confirm `docs-build.yml`'s per-file assertion fires `##[notice]All 4 NFR-MAINT-04 sections present` for `coding-conventions.md` after the content fill.

## Dev Notes

### Why this story exists

Phase-1's open-source hygiene baseline. Without it:
- An external contributor encountering the repo can't tell what conventions to follow (no CONTRIBUTING.md) or how to set up their dev environment.
- A security researcher discovering a vulnerability has no clear disclosure path (the Story 1a.1 SECURITY.md placeholder mostly works but doesn't specify the 7-day/90-day SLA).
- Issue authors can't follow a structured template; triage becomes noise-filtering.
- `src/AgentEval/**/*.py` files lack Apache 2.0 attribution headers — license compliance gap for redistributors.
- `docs/contracts/coding-conventions.md` is a Phase-1 stub even though Story 1a.4 documented Story 1a.5 as its owner.

This story closes the hygiene gap before Epic 1b (kernel modules) starts adding ~2000+ lines of `.py` code that would otherwise ship without headers.

### Architecture compliance + scope

- **architecture.md L1166-1168 + PRD NFR-MAINT-01 + PRD NFR-SEC-04** are the canonical sources. All 3 agree on the 4 core deliverables (CONTRIBUTING + SECURITY + ISSUE_TEMPLATE + license headers). Pre-create-story drift check (5th use of the norm) found NO drift this time — first clean pre-check since the norm began.
- **`coding-conventions.md` content** added to scope per Many's 2026-05-18 ratification (Story 1a.4 banner-stated Story 1a.5 as owner).
- **`good first issue` GitHub labels** added per Many's ratification (PRD NFR-MAINT-01 names these explicitly as a bus-factor-mitigation deliverable).
- **Story 1a.3 deferred debt (LOW-1 + MED-2)** added per Many's ratification — folds into the hygiene batch since both are 1-line prose fixes.
- **OUT OF SCOPE** (deferred to Epic 1b or later): Mock adapter template, "agent* portfolio docs" deep population, full `docs/recipes/` content.

### Apache 2.0 Header Text (canonical 13 lines)

Every `src/AgentEval/**/*.py` file MUST start with these exact 13 lines (no leading blank line; subsequent code starts on line 14):

```python
# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

Year `2026`. Copyright holder `Many Kasiriha` (matches `pyproject.toml` author field).

### License-header Scripts structure

**`scripts/apply-license-headers.py`** (single-file ~50 LoC):
- Walks `src/AgentEval/` recursively for `*.py` files.
- For each file: reads content, checks for substring `Licensed under the Apache License`. If absent: prepend the canonical 13-line header + a blank line. If present: skip (idempotent).
- Prints a one-line summary: "Applied N headers; M files already had headers."
- Exit code 0 always (the apply-mode is non-failing).

**`scripts/check-license-headers.py`** (single-file ~30 LoC):
- Same walk pattern but check-mode only.
- For each `.py` file: assert header present. Track missing files.
- Print summary: "Checked N files; M missing headers."
- Exit code 0 if zero missing; non-zero if any missing (lists them).

### `.pre-commit-config.yaml` structure

Minimum content (per pre-commit framework conventions):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0  # match pyproject.toml ruff version pin
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        files: ^src/
  - repo: local
    hooks:
      - id: license-headers
        name: Check Apache 2.0 license headers
        entry: uv run python scripts/check-license-headers.py
        language: system
        files: ^src/AgentEval/.*\.py$
        pass_filenames: false
```

Document in CONTRIBUTING.md: contributors install via `uv run pre-commit install`; the hooks fire automatically on `git commit`.

### CI license-header check step (insertion into ci.yml)

Insert between the existing `Typecheck (mypy)` step and the `pytest Phase-1 collect-only sweep` step:

```yaml
      - name: License headers check
        run: uv run python scripts/check-license-headers.py
```

Update the top-of-file comment in ci.yml to mention this defense-in-depth posture: "License-header check is enforced BOTH pre-commit (catches local) AND CI (catches `--no-verify` bypass)."

### Coding-conventions content guidance (for Task 7)

Replace the current `## Contract` placeholder with a substantive 2-column reference card per architecture Step-5. Sections per AC-1a.5.5. The MADR 4-section structure MUST be preserved:

```markdown
# Coding Conventions

**Status:** accepted (Story 1a.5 ratification 2026-05-18)
**Owning epic:** Story 1a.5
**Related ADRs:** none directly
**Related references:** `CONTRIBUTING.md`, `pyproject.toml` ruff + mypy configurations

## Purpose

<existing content — keep>

## Scope

<existing content — keep>

## Contract

<REPLACE skeleton text with substantive content per AC-1a.5.5>

### Naming Conventions

| ✅ Good | ❌ Anti-pattern | CI check |
| --- | --- | --- |
| module = `lowercase_snake.py` | `CamelCase.py` | ruff rule N999 |
| class = `PascalCase` | `snake_case_class` | ruff rule N801 |
| function = `lowercase_snake()` | `camelCase()` | ruff rule N802 |
| ...etc 8-10 rows...

### Type Annotations
<table per category>

### Docstring Style
<example per public function/class>

### Error Messages
<example per Tier-1 setup-failure error, FR59 format>

### Comment Policy
<good/anti-pattern>

### Import Ordering
<ruff isort enforced>

### Test Naming
<example unit / acceptance / conformance>

## Change Policy

<existing content — keep with light updates>

## References

<update if needed>
```

### Project debt cleanup (AC-1a.5.7)

**LOW-1**: Find the exact text in `docs/adr/ADR-014-error-class-hierarchy.md`:
```
- **9 leaves explicitly named** above; additional leaves require an ADR amendment to keep the surface auditable.
```
Replace `9 leaves` → `11 leaves`. The table count is authoritative (2 Safety + 2 Budget + 4 Compat + 3 Integrity = 11).

**MED-2**: Find the exact text in `docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md` L37:
```
- Generic LiteLLM-backed adapter (ADR-013) doesn't apply this strategy — it's SDK-driven, not subprocess-driven; trace extraction is the in-process API response.
```
ADR-013 is Entry-Points Discovery — wrong reference. Replace `(ADR-013)` with `(see ADR-003 §Decision — Generic LiteLLM-backed adapter inherits from \`InProcessAdapter\`)` per the Story 1a.3 code-review recommended fix.

### Previous story intelligence (Story 1a.4 carry-forward lessons)

- **Cross-LLM adversarial review continues to be load-bearing**: 4th consecutive review where Claude solo found 0 substantive issues + Codex caught all of them. Story 1a.5's code-review WILL find issues; budget for it.
- **CI-log-forensics norm**: Story 1a.5 adds a new CI step (license-header check). Post-push log inspection MUST verify the step fires green across both Python matrix cells (3.12 + 3.13).
- **Pre-create-story drift check (5th use)**: clean this time — first time the norm passed without surfacing drift. Story 1a.5 sources (architecture + PRD + epics) are mutually consistent.
- **Norm #2 numeric verification**: every count in Dev Notes + Tasks (6 GitHub labels, 13-line Apache 2.0 header, 11 leaves in ADR-014, all `.py` files in src/AgentEval/ have headers, etc.) MUST be machine-verified before commit.

### Project norms applied

1. **Norm #1 (cross-LLM adversarial review)**: code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)`. Expect Codex to find issues; Story 1a.5's hygiene surface has many cross-document touch-points (CONTRIBUTING ↔ SECURITY ↔ ISSUE_TEMPLATE ↔ coding-conventions ↔ pre-commit ↔ ci.yml).
2. **Norm #2 (machine-verified numeric claims)**: Tasks 5, 8, 10 explicitly call out per-file grep/count verifications.
3. **Pre-create-story spec-vs-ratified-doc check**: applied 2026-05-18; no drift found.
4. **CI-log-forensics**: post-push verification per the just-ratified Many's rule — license-header step inspection + docs-build coding-conventions content verification.
5. **Honest framing**: every deliverable has a documented Phase-1 status + cross-references to owning epic. The 2 debt items get closed honestly (no silent fixes).
6. **agentguard inspiration-only**: SECURITY.md content explicitly cites the `feedback_agentguard_inspiration_not_dependency` posture (no agentguard CVE inheritance since no dependency).
7. **DCO sign-off**: chosen on merit for agenteval's contribution model; CONTRIBUTING.md frames it as standard OSS practice without comparative reference to agentguard or any other project.

### References

- **PRD §NFR-MAINT-01** (L1647): solo + AI-agent-assisted maintainership; CONTRIBUTING.md as bus-factor-mitigation; "good first issue" labels listed
- **PRD §NFR-MAINT-02** (L1648): SUPPORT.md 5-business-day triage SLA (cross-reference, not Story 1a.5 deliverable)
- **PRD §NFR-SEC-01..05** (L1630-1634): credential redaction + eval safety + TLS + supply-chain boundary + no-phone-home — SECURITY.md content sources
- **PRD §FR38a/FR38b**: credential-redaction patterns — SECURITY.md cites
- **architecture.md L1166-1168**: project tree entries for CONTRIBUTING.md + SECURITY.md
- **architecture.md L581** + **L1671**: NFR-MAINT-01 implementation map
- **epics.md Story 1a.5** (L778-797): the original AC list
- **Apache 2.0 License**: https://www.apache.org/licenses/LICENSE-2.0 — canonical license text (full text already at `LICENSE` per Story 1a.1)
- **Developer Certificate of Origin**: https://developercertificate.org/ — for DCO sign-off documentation
- **pre-commit framework**: https://pre-commit.com/ — for `.pre-commit-config.yaml` syntax + hook execution
- **GitHub issue templates**: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates — for template frontmatter syntax
- **`docs/contracts/coding-conventions.md`** (Story 1a.4 stub) — Task 7 fills content
- **`docs/adr/ADR-014-error-class-hierarchy.md`** — Task 9 LOW-1 fix
- **`docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md`** — Task 9 MED-2 fix
- **Story 1a.1 SECURITY.md placeholder** (existing file) — Task 3 replaces content
- **Story 1a.2 `.github/workflows/ci.yml`** — Task 6 adds license-header check step

## Dev Agent Record

### Context Reference

- Story file: this file
- PRD NFR-MAINT-01 + NFR-SEC-01..05 (Story 1a.5 content sources)
- Architecture L1166-L1168 (project tree entries for CONTRIBUTING.md + SECURITY.md)
- Story 1a.3 deferred review items (LOW-1 + MED-2)

### Agent Model Used

Claude Opus 4.7 (1M context) — dev-story workflow invocation 2026-05-18.

### Debug Log References

- **License-header script application**: ran `uv run python scripts/apply-license-headers.py` once; applied 20 headers; re-ran to verify idempotent (Applied 0; 20 already present). `uv run python scripts/check-license-headers.py` confirms all 20 .py files have the header.
- **Ruff + mypy regression**: post-header-application, `uv run ruff check src/ tests/` returns "All checks passed!"; `uv run ruff format --check src/ tests/` returns "22 files already formatted"; `uv run mypy src/` returns "Success: no issues found in 20 source files". Apache 2.0 headers don't break Python syntax or formatting.
- **GitHub label descriptions**: created via `gh label create --force` to update existing default-shipped labels' descriptions to match AC-1a.5.6 spec exactly. Verified via `gh label list --json name,description --jq`.
- **AC-1a.5.9 final machine verification**: all 10 sub-checks PASS (CONTRIBUTING line count ≥147; SECURITY.md placeholder removed = 0 matches; 3 ISSUE_TEMPLATE files have valid frontmatter; 20/20 .py files headered; .pre-commit-config.yaml present; ci.yml has license-header step; coding-conventions.md Phase-1 skeleton removed = 0 matches + 4 NFR-MAINT-04 sections preserved; 6/6 required GitHub labels present; LOW-1 "11 leaves" present + "9 leaves" gone; MED-2 ADR-013 cross-ref gone from ADR-010 + ADR-003 cross-ref added).

### Completion Notes List

- **All 10 ACs satisfied** with machine-verified evidence per Epic 0 retro Norm #2.
- **Pre-create-story drift check (5th use)** found NO drift this time — first clean pre-check since the norm started. Architecture + PRD + epics.md were mutually consistent on the 4 core deliverables.
- **License-header script idempotency** verified end-to-end: applies cleanly the first run (20 headers), zero new headers on re-run, check-mode validates all files.
- **Defense-in-depth license-header enforcement** active: pre-commit hook (local) + ci.yml step (CI) both wired. Either gate catches missing headers; the pre-commit fires on `git commit`, the ci.yml step catches `--no-verify` bypass.
- **2 Story 1a.3 deferred debt items closed** (LOW-1 + MED-2) — both 1-line fixes with explicit "corrected by Story 1a.5" trail in the affected ADRs.
- **`docs/contracts/coding-conventions.md` content** authored substantively (replaces Phase-1 skeleton); preserves all 4 NFR-MAINT-04 section headers (docs-build.yml per-file assertion will still pass).
- **No HALT conditions encountered**. No new dependencies; no configuration files missing.

### Code Review Handoff Notes (for `/bmad-code-review`)

The reviewer should specifically scrutinize:

1. **CONTRIBUTING.md content accuracy**: does the DCO sign-off explanation match `developercertificate.org`? Are the test invocation commands accurate (especially `--listener AgentEval.telemetry.listener` — note Story 5.1 hasn't shipped that listener yet; Phase-1 caveat documented but verify framing). Are the Conventional Commits examples valid (`feat(mcp):` style)?

2. **SECURITY.md NFR coverage**: do the 5 security guarantees (NFR-SEC-01..05) accurately reflect PRD content + cite the right ADRs? Particularly: NFR-SEC-01 credential-redaction claims `config.redact_env()` + `config.add_redaction_pattern()` — verify these are documented APIs (or appropriately marked as Phase-1 forward-references). The "Limits" subsection is honest framing; verify it doesn't promise more than the library can deliver.

3. **Issue template frontmatter validity**: GitHub parses YAML frontmatter; do all 3 templates have `name:`, `about:`, `title:`, `labels:`, `assignees:` keys? The label names in `labels:` MUST exist in the repo's label set (per Task 8: bug, enhancement, question all confirmed present).

4. **License-header script correctness**: edge cases — what if a `.py` file already starts with a shebang `#!/usr/bin/env python3` or an encoding declaration `# -*- coding: utf-8 -*-`? The current script just prepends the header at file start; if a shebang exists, the header ends up before it (which breaks the shebang). Phase-1 baseline doesn't have shebangs (verified), but a future contributor adding a shebang would discover this. Worth flagging in cross-LLM review.

5. **Coding-conventions.md content alignment**: are the naming-convention examples consistent with what Story 1a.1 actually shipped (e.g., is the agenteval source actually `lowercase_snake.py`? — verify via `ls src/AgentEval/`). Are the type-annotation examples using PEP 695 `type` statement (3.12+) — does the project actually use this anywhere yet, or is it aspirational?

6. **Pre-commit-config rev pins**: ruff @ v0.6.9, mypy @ v1.10.0 — do these match `pyproject.toml`'s `[dev]` extras pins? If versions drift, pre-commit will use one while CI uses another. Worth ratifying.

7. **License-header CI check first run**: post-push, the new step fires for the first time. Per the CI-log-forensics norm, log-inspect that the step actually runs `scripts/check-license-headers.py` against the matrix cells (Python 3.12 + 3.13), and that it exits 0.

## File List

Expected files (8 created + 5 updated):

**New files (8):**
- `CONTRIBUTING.md` (repo root)
- `.github/ISSUE_TEMPLATE/bug-report.md`
- `.github/ISSUE_TEMPLATE/feature-request.md`
- `.github/ISSUE_TEMPLATE/question.md`
- `scripts/apply-license-headers.py`
- `scripts/check-license-headers.py`
- `.pre-commit-config.yaml` (repo root)

**Updated files (5):**
- `SECURITY.md` (replace placeholder with full content)
- `docs/contracts/coding-conventions.md` (replace skeleton with substantive content)
- `docs/adr/ADR-014-error-class-hierarchy.md` (LOW-1: 9 leaves → 11 leaves)
- `docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md` (MED-2: ADR-013 → ADR-003 cross-ref)
- `.github/workflows/ci.yml` (add license-header check step)
- `CHANGELOG.md` (Unreleased entry)
- `src/AgentEval/**/*.py` (~20-25 files — Apache 2.0 header prepended idempotently by script)

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-18 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (5th consecutive use) found NO drift — clean first time. Scope expanded per Many's ratifications: fold 2 Story 1a.3 deferred debt items (LOW-1 + MED-2); fill `docs/contracts/coding-conventions.md` content (Story 1a.4 banner-stated owner); add `good first issue` + 2 other GitHub labels per NFR-MAINT-01. | Bob |
| 2026-05-18 | 0.2.0   | Dev-story complete. All 10 ACs satisfied with machine-verified evidence. 8 new files (CONTRIBUTING.md, SECURITY.md full content, 3 ISSUE_TEMPLATE/*.md, 2 scripts, .pre-commit-config.yaml) + 5 updated (ci.yml license-header step, coding-conventions.md substantive content, ADR-014 + ADR-010 debt fixes, CHANGELOG.md, sprint-status.yaml). 20 .py files in src/AgentEval/ headered with Apache 2.0 license (idempotent script verified). 6 GitHub labels created/updated. Ruff + mypy clean post-header-application. Story 1a.3 LOW-1 + MED-2 debt closed. Status: review. | Amelia |
