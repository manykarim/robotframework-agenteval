# Story 1a.5 Code Review Findings (2026-05-18)

**Reviewers:** Claude Opus 4.7 + Codex CLI 0.117.0 (gpt-5.4) — adversarial cross-LLM-family pair per Epic 0 retro Norm #1.

**Verdict:** **Changes Requested** — 6 MED + 3 LOW findings. All are content-accuracy / configuration-correctness issues; no structural problems. Several are claim-vs-reality drift (CONTRIBUTING.md or SECURITY.md asserts something the code doesn't yet deliver) that the hygiene story surfaces by virtue of being the first comprehensive contributor-facing prose.

---

## Methodology

1. **Claude independent re-verification** of Story 1a.5's 6 dev gates — all PASSED (file presence, license-header script idempotent, ruff + mypy clean, pre-commit-config YAML valid, ci.yml has license-header step, 6/6 GitHub labels active).

2. **Codex CLI adversarial pass** via GitHub MCP — Codex fetched the 8 hygiene files + pyproject.toml + ruff.toml + CI workflows from `90d6f5c`, plus searched for cited APIs (`config.redact_env`, etc.) + DCO workflow + PR template. Codex caught **9 findings**.

3. **Claude spot-verified all 9 Codex findings locally** — all confirmed real.

**5th consecutive cross-LLM review where Claude solo found 0 substantive issues + Codex caught real ones.** Same-family blind spot pattern continues to be load-bearing.

---

## Findings

### MEDIUM (6)

#### MED-1: SECURITY.md cites APIs that don't exist in src/AgentEval/ yet (Phase-1 forward-references)

**File:** `SECURITY.md` §Security Guarantees (specifically NFR-SEC-01, NFR-SEC-05 sections)

**Issue:** SECURITY.md is written in present tense around APIs and behaviors that don't ship in `src/AgentEval/` yet:
- `config.redact_env()` — does not exist; future Epic 5 deliverable
- `config.add_redaction_pattern()` — does not exist
- `__init__(telemetry=False)` listener-disable — `cli.py` is a Phase-1 placeholder per Story 1a.1
- "Conformance suite verifies via `Assert No Egress To` fixture" — conformance harness lands in Epic 1b Story 1b.5

**Recommended fix:** Either (a) rewrite each guarantee with explicit `**Phase-1 status:** forward-reference; concrete enforcement lands in <epic>` framing, or (b) move the forward-referenced details under a §Future-state guarantees subsection and keep §Current-state to what actually ships. **Option (a) is simpler.**

---

#### MED-2: `uv run pre-commit install` fails — `pre-commit` not in `[dev]` extras

**File:** `pyproject.toml` `[project.optional-dependencies]` `dev = [...]`; `CONTRIBUTING.md` L20

**Issue:** CONTRIBUTING.md tells contributors to run `uv run pre-commit install` as part of setup. But `pre-commit` is not in `pyproject.toml`'s `[dev]` extras (which currently lists `pytest`, `pytest-cov`, `ruff`, `mypy`, `robotframework-pabot`). A clean `uv sync --all-extras` install does not provide `pre-commit`; the command will error.

**Recommended fix:** Add `pre-commit>=3.0,<5.0` to `pyproject.toml`'s `[dev]` extras. Re-run `uv lock` to update `uv.lock`.

---

#### MED-3: CONTRIBUTING.md "DCO check enforces this in CI" is not backed by any workflow

**File:** `CONTRIBUTING.md` L82

**Issue:** CONTRIBUTING.md states "The DCO check enforces this in CI." But there is no DCO workflow in `.github/workflows/` — none of the 7 ratified workflows (ci, security-scan, conformance, nightly-live, dogfood-integration, docs-build, release) check for `Signed-off-by:` trailers.

**Recommended fix:** Two options:
- **Option A (recommended for honest framing):** Soften the wording: "PRs without DCO sign-off will be requested to amend during review." Add a follow-up TODO to wire a DCO check workflow (e.g., `wagoid/commitlint-github-action` or a custom regex script) — track as project debt.
- **Option B:** Add a DCO workflow now. Lightweight script-based check (~20 lines of YAML) that asserts every commit in the PR has a `Signed-off-by:` trailer matching the commit author email.

---

#### MED-4: License-header check uses substring match — false-pass risk

**Files:** `scripts/apply-license-headers.py` L42; `scripts/check-license-headers.py` L28

**Issue:** Both scripts use `if LICENSE_MARKER in content:` where `LICENSE_MARKER = "Licensed under the Apache License"`. This is a substring search anywhere in the file. A stray comment or docstring containing that phrase (e.g., a unit test that asserts on error messages containing the phrase, or documentation about licensing) would cause:
- `apply-license-headers.py` to SKIP applying the canonical header (file falsely appears to have one already).
- `check-license-headers.py` to FALSELY PASS (file appears compliant).

**Recommended fix:** Validate the canonical header block at the **file prologue** (first ~13 lines), not anywhere. E.g., assert that the first 13 lines starting from line 1 (or after shebang/encoding — see MED-5) match the canonical header line-for-line.

---

#### MED-5: License-header script breaks shebangs + PEP 263 encoding declarations

**File:** `scripts/apply-license-headers.py` L43

**Issue:** The script blindly prepends header at byte 0. Future `.py` files starting with `#!/usr/bin/env python3` or `# -*- coding: utf-8 -*-` would have these lines DEMOTED below the license header — breaking the shebang (Python requires shebang on line 1) and the PEP 263 encoding cookie (must be in line 1 or 2).

Phase-1 baseline has none — verified by `grep -rE '^#!' src/AgentEval/` returning nothing. But this is a forward-looking script that should handle future cases (Epic 8b ships the `agenteval` CLI which may add `#!/usr/bin/env python3` to entry scripts).

**Recommended fix:** Read first 2 lines; if line 1 is a shebang OR encoding-cookie OR line 2 is encoding-cookie, preserve them at the top and insert the license header AFTER. Same logic in `check-license-headers.py` when validating prologue.

---

#### MED-6: `docs/contracts/coding-conventions.md` cites ruff N-series rules that aren't enabled

**Files:** `docs/contracts/coding-conventions.md` naming-conventions table; `ruff.toml`

**Issue:** The coding-conventions naming table claims:
- `module = lowercase_snake.py` → enforced by `ruff N999`
- `class = PascalCase` → enforced by `ruff N801`
- `function = lowercase_snake()` → enforced by `ruff N802`
- `variable = lowercase_snake` → enforced by `ruff N806`

But `ruff.toml`'s `[lint] select = [...]` does NOT include `"N"` (the pep8-naming ruleset). So none of those rules are actually checked. The doc overstates machine enforcement.

**Recommended fix:** Two options:
- **Option A (recommended — backs the convention with real enforcement):** Add `"N"` to `ruff.toml`'s `[lint] select`. Test by running `uv run ruff check src/ tests/` — if any existing code triggers N-series failures, fix or grandfather via per-file-ignores. Phase-1 codebase is small (~20 .py files); the impact should be minimal.
- **Option B:** Rewrite the table's "Enforcement" column to "convention; not auto-enforced" for those rows. Honest framing per `feedback_honest_framing` memory.

---

### LOW (3)

#### LOW-7: CONTRIBUTING.md testing command `robot --listener AgentEval.telemetry.listener` is dead today

**File:** `CONTRIBUTING.md` L39

**Issue:** The testing section lists `uv run robot --listener AgentEval.telemetry.listener tests/` as a contributor command. But `src/AgentEval/telemetry/listener.py` does not exist in commit `90d6f5c` — Story 5.1 (Epic 5) ships it. A contributor copy-pasting today gets an `ImportError` from RF.

**Recommended fix:** Mark the command as `# Phase-2 (Epic 5 Story 5.1 deliverable; not runnable yet)` inline. Or move it to a dedicated "Forthcoming" subsection.

---

#### LOW-8: CONTRIBUTING.md "PR template enforces" but no PR template file exists

**File:** `CONTRIBUTING.md` L67

**Issue:** CONTRIBUTING.md says "Every PR description SHOULD link to a GitHub issue (or a planning artifact). The PR template enforces this." But no `.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE.md` exists in the repo. The "enforces" claim is unsupported.

**Recommended fix:** Two options:
- **Option A:** Add a `.github/pull_request_template.md` with sections for issue link + summary + test plan + checklist. ~30 lines.
- **Option B:** Soften wording: "PR descriptions SHOULD link to a GitHub issue. A PR template will land in a future hygiene cleanup."

---

#### LOW-9: Pre-commit `rev:` pins drift from CI's resolved versions

**File:** `.pre-commit-config.yaml` L10 (ruff `rev: v0.6.9`) + L17 (mypy `rev: v1.10.0`); `pyproject.toml` `[dev]` extras (ruff `>=0.6,<1.0`, mypy `>=1.10,<2.0`)

**Issue:** Pre-commit hooks hard-pin ruff 0.6.9 + mypy 1.10.0; project env + CI use floating ranges. `uv sync` may resolve ruff to a newer 0.6.x or 0.7.x (allowed by `<1.0` cap) — local pre-commit hits a different version. Behavior could diverge subtly (especially as ruff adds new rules per minor).

**Recommended fix:** Either (a) align by pinning ruff + mypy exactly in `pyproject.toml` `[dev]` extras (matches the spike-validated-version pattern from `mcp`/`robotframework`/`pabot`/`anyio`), or (b) replace the pre-commit-mirror hooks with `repo: local` entries that invoke `uv run ruff` / `uv run mypy` — uses the project's resolved environment. **Option (b) is the cleanest.**

---

## Triage summary

| Severity | Count | Findings | Scope |
|---|---|---|---|
| MED | 6 | MED-1 (SECURITY APIs), MED-2 (pre-commit dev extras), MED-3 (DCO CI claim), MED-4 (substring match), MED-5 (shebang handling), MED-6 (ruff N-series) | 2 content-accuracy + 2 script-hardening + 2 config-correctness |
| LOW | 3 | LOW-7 (listener command), LOW-8 (PR template), LOW-9 (rev pin drift) | All CONTRIBUTING.md or config-alignment |

**Cross-LLM coverage:** Claude solo 0 / Codex 9. 5th consecutive review with the same blind-spot pattern.

## Recommended action

Apply contract-internal MED-1 + MED-3 + MED-4 + MED-5 + MED-6 (~30-line patch set across 4 files). MED-2 is a 1-line pyproject.toml edit + `uv lock` re-run. LOW-7 + LOW-8 are inline tweaks. LOW-9 is the cleanest "use uv run via repo: local" refactor.

Total estimated patch work: ~50 lines across 6 files. No structural code changes.
