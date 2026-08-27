## Context

`allowed-tools` has three real forms that should be equivalent inputs. Confirmed
against source and the upstream spec:

- **The upstream format is space-separated, not comma-separated.** The Agent Skills
  spec (agentskills.io/specification) defines `allowed-tools` as a "space-separated
  string of pre-approved tools," example `allowed-tools: Bash(git:*) Bash(jq:*) Read`;
  Claude Code documents a space-separated string or a YAML list (`allowed-tools: Read
  Grep`). Issue #19's claim that the spec accepts a comma-separated string is incorrect
  — verified by fetching the spec.
- `_parser.py::validate_frontmatter_structure` (L168-176) accepts only the list form;
  `yaml.safe_load("Read Grep")` and `yaml.safe_load("Read, Grep")` both yield a scalar
  `str`, tripping the `not isinstance(list)` branch.
- `parse_frontmatter` returns the **raw** parsed dict (L126); no normalization exists.
- `Skill.Get Frontmatter` (`__init__.py:71-83`) returns the raw mapping.
  `Skill.Get Allowed Tools` (L98-110) returns `list(... .get("allowed-tools", []))` —
  a bare string char-splits. `Skill.Should Be Valid Frontmatter` (L127-140) calls
  `validate_frontmatter_structure(frontmatter)` on a **caller-supplied dict**, not via
  `parse_frontmatter`; only `_read_and_validate` (L142-146) goes through the parser.
- No typed frontmatter model exists; frontmatter is a plain `dict[str, Any]`.

## Goals / Non-Goals

**Goals:**

- All three forms (space per spec, comma per compatibility, YAML list) validate and are
  exposed identically as a `list[str]`, with tool-scoping syntax preserved.
- Normalization is consistent across every getter **and** the standalone validator.
- A genuinely mistyped value (non-str, non-list) still fails loud.

**Non-Goals:**

- Validating tool-scope grammar beyond preserving each scoped token intact.
- De-duplicating tools; changing other frontmatter fields; touching agent/judge modes.

## Decisions

### D1 — A parenthesis-aware tokenizer (chosen), split on whitespace or comma

Add `_normalize_allowed_tools(value) -> list[str]`:

- `str` → tokenize: scan characters tracking parenthesis depth; a run of whitespace or
  a comma at **depth 0** ends a token; whitespace/commas at depth > 0 are kept inside
  the token. Strip tokens, drop empties. So:
  - `"Bash(git:*) Bash(jq:*) Read"` → `['Bash(git:*)', 'Bash(jq:*)', 'Read']` (spec form)
  - `"Read, Grep"` and `"Read,Grep"` and `"Read Grep"` → `['Read', 'Grep']`
  - `"Bash(git add:*)"` → `['Bash(git add:*)']` (internal space preserved)
  - `"WebFetch(a.com,b.com)"` → `['WebFetch(a.com,b.com)']` (internal comma preserved)
  - `""` / whitespace-only → `[]`
- `list` → require every element be `str`; return as-is (else raise, unchanged).
- other scalar (`int`/`bool`/`float`) → raise `InvalidConfigError` (mistyped).

**Why paren-aware.** Splitting on whitespace *or* comma covers the spec form and the
reporter's compatibility form in one pass, but a naive split would corrupt scoped tools
that contain a space or comma inside parentheses. Depth-0-only splitting preserves them.

**Space is the spec form; comma is a compatibility extension.** The spec mandates
space; the reporter's real corpus uses comma (most likely from Claude Code slash-command
frontmatter). Accepting both — while normalizing to one canonical `list[str]` — is
lenient on input, spec-conformant on the space form, and corrupts nothing. Documented as
"space per spec; comma also accepted for compatibility."

### D2 — Normalize at BOTH parse and validate (shared idempotent helper)

Because `Should Be Valid Frontmatter` runs `validate_frontmatter_structure` on a
caller-supplied dict (not via the parser), normalizing only in `parse_frontmatter`
would leave the standalone validator still rejecting the string forms — contradicting
the new SHALL. So the shared helper is called by **both**:

- `parse_frontmatter` normalizes on read → file getters and `Get Frontmatter` see the
  normalized list; `Get Allowed Tools`'s `list(...)` receives a real list (char-split
  hazard gone).
- `validate_frontmatter_structure` normalizes (idempotently) before its list-of-str
  assertion → a directly-passed dict with any accepted form is accepted.

The helper is idempotent (a `list[str]` in → the same list out), so calling it in both
places is safe. `Get Frontmatter`'s docstring shifts from "raw parsed mapping" to
"normalized parsed mapping" for `allowed-tools`; under the `provisional` label this is a
minor bump.

### D3 — Flip the test that codifies the bug + keep the mistype guard

`test_optional_fields.py::test_present_but_mistyped_optional_still_raises` (L58-64)
writes `allowed-tools: Read, Write` and asserts it raises; it must flip to assert
normalization to `['Read','Write']`. A distinct genuinely-mistyped case (e.g.
`allowed-tools: 5`) is added so the raise branch — currently the only guard on that path
— stays covered.

### D4 — Spec anchoring + honest motivation

`skills-testing/spec.md` is silent on the accepted forms (does not mandate list-only),
so no requirement is contradicted; a focused requirement is ADDED. The "17 of 17"
figure is labeled an unverified reporter statistic (no such corpus in-repo), used as
motivation, not as evidence of conformance.

## Risks / Trade-offs

- **Behavior widening:** previously-rejected input now succeeds — backward-compatible
  for users, but flips one in-repo test (D3), which lands in the same commit.
- **`Get Frontmatter` contract shift** (D2) — docstring updated; `provisional` minor bump.
- **Compatibility comma** is non-spec; documented as an explicit extension, not "the
  Agent Skills spec." The paren-aware tokenizer prevents it from corrupting scoped tools.
- **`provisional` label:** `SkillsLibrary` is `provisional`
  (`docs/contracts/stability-surface.md`); widening/normalizing is a minor bump.
- No new dependency (stdlib string handling only).

## Migration Plan

Additive/widening, no API change. The space and comma forms start validating and all
three forms expose the same list. One internal test's expectation flips. Rollback is a
revert.

## Open Questions

- **OQ1:** Coerce explicit `null` (`allowed-tools:` → `None`) to `[]`, or keep raising
  (chosen — a present-but-null field is likely an authoring error)? `get_allowed_tools`
  already defaults only the *absent* key.
- **OQ2:** De-duplicate repeated tools (`Read, Read`)? The YAML-list form does not
  dedupe today; keeping parity means no dedupe. Out of scope unless requested.
