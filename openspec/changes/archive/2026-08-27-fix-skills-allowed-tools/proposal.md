## Why

`Skill.Should Be Valid Frontmatter` rejects `allowed-tools` whenever it is written as
anything other than a YAML list, which blocks real, spec-valid skills. Root cause
confirmed in `src/SkillsLibrary/_parser.py::validate_frontmatter_structure` (L168-176):
it requires a `list`, so any string form trips the `not isinstance(list)` branch.

**Correcting the issue's premise (found in review).** Issue #19 asserted that the
Agent Skills spec accepts a *comma*-separated string. It does not. The authoritative
spec defines `allowed-tools` as a **space-separated string** (with tool-scoping
syntax), example `allowed-tools: Bash(git:*) Bash(jq:*) Read`; Claude Code documents a
space-separated string **or** a YAML list (`allowed-tools: Read Grep`). So the real bug
is broader than "accept commas": the library rejects the *space-separated* spec form
too, and a naive comma-splitter would actively corrupt it (`"Read Grep"` → one bogus
token) and break scoped tools like `Bash(git:*)`.

Two secondary hazards, both confirmed:
- `parse_frontmatter` returns the **raw** dict (`_parser.py:126`), and
  `Skill.Get Allowed Tools` does `list(... .get("allowed-tools", []))`
  (`__init__.py:110`) — a bare string there character-splits into
  `['R','e','a','d', ...]`. So the value must be normalized to a real `list[str]`.
- `Skill.Should Be Valid Frontmatter` takes a **dict** and calls
  `validate_frontmatter_structure(frontmatter)` directly (`__init__.py:127-140`); only
  file getters go through `parse_frontmatter`. So normalizing only in the parser leaves
  the standalone validator still rejecting the string forms.

## What Changes

- **Accept the space-separated (spec), comma-separated (compatibility), and YAML-list
  forms, via a parenthesis-aware tokenizer.** Add a shared
  `_normalize_allowed_tools(value) -> list[str]` helper in `_parser.py`. For a string,
  split on whitespace **or** commas **only at parenthesis depth 0**, so tool-scoping
  syntax with internal spaces or commas (`Bash(git add:*)`, `WebFetch(a.com,b.com)`) is
  preserved as one token; tokens are stripped, empties dropped. A `list` must be
  all-strings (unchanged raise otherwise). Any other scalar (`int`/`bool`/`float`)
  still raises. The space form is the spec form; the comma form is accepted as a
  documented compatibility extension (the reporter's corpus uses commas, most likely
  carried over from Claude Code *slash-command* frontmatter, which is comma-separated).
- **Normalize at both entry points.** Call the shared helper from **both**
  `parse_frontmatter` (so file getters + `Get Frontmatter` see the normalized list) and
  `validate_frontmatter_structure` (so a directly-passed dict is also accepted and the
  new guarantee holds regardless of provenance). `Get Allowed Tools` then reads a real
  `list[str]` — the char-split hazard is gone.
- **Keep the genuine-mistype guard.** A non-string, non-list value still fails loud, so
  the validator's mistyped-field contract is preserved for real mistakes.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `skills-testing`: ADD a requirement that `allowed-tools` accepts the space-separated
  (spec), comma-separated (compatibility), and YAML-list forms, normalizing all to an
  equivalent list of tool strings — preserving tool-scoping syntax and never splitting
  inside parentheses — exposed identically by the getters and the validator, while a
  genuinely mistyped value still fails validation.

## Impact

- **Code:** `src/SkillsLibrary/_parser.py` — new parenthesis-aware
  `_normalize_allowed_tools`, called from `parse_frontmatter` **and**
  `validate_frontmatter_structure` (which then asserts over a normalized list). Update
  the fix-hint string (L172-175).
- **Tests:** `tests/surfaces/skills/test_optional_fields.py` —
  `test_present_but_mistyped_optional_still_raises` (L58-64) currently writes
  `allowed-tools: Read, Write` and asserts it *raises*; this **codifies the bug** and
  must flip to assert normalization to `['Read','Write']`, plus a genuinely-mistyped
  case (e.g. `allowed-tools: 5`) to keep the raise branch covered. `test_frontmatter.py`
  list-form assertions stay green.
- **Docs:** the `Get Allowed Tools` / `Should Be Valid Frontmatter` / `Get Frontmatter`
  docstrings note all three accepted forms (and that `Get Frontmatter` now returns the
  normalized list); `CHANGELOG.md` (widening under the `provisional` label = minor bump).
- **Out of scope:** de-duplicating repeated tools; validating tool-scope grammar
  (`Bash(git:*)`) beyond preserving it as an opaque token; the
  `disable-model-invocation` branch; any agent/judge-mode Skills keyword.

**Framing note:** the "17 of 17 skills fail" figure in issue #19 is an unverified,
reporter-supplied statistic — the repository has no such corpus (only a one-skill
fixture + one synthetic case), so it is cited as motivation, not as evidence of
spec-conformance.
