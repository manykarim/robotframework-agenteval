## 1. Normalize allowed-tools with a parenthesis-aware tokenizer

- [x] 1.1 Add `_normalize_allowed_tools(value) -> list[str]` in `src/SkillsLibrary/_parser.py`: for a `str`, tokenize by scanning characters and tracking parenthesis depth — a run of whitespace or a comma at **depth 0** ends a token; whitespace/commas at depth > 0 stay inside the token; strip tokens, drop empties (empty/whitespace → `[]`). For a `list`, require all-str (else raise). For any other scalar, raise `InvalidConfigError`.
- [x] 1.2 Call `_normalize_allowed_tools` from `parse_frontmatter` (so file getters + `Get Frontmatter` return the normalized list) **and** from `validate_frontmatter_structure` (so a directly-passed dict is accepted regardless of provenance). The helper is idempotent, so calling it in both places is safe.
- [x] 1.3 Simplify `validate_frontmatter_structure` (L168-176) to normalize then assert over the resulting list; update the fix-hint string (L172-175) to mention all three accepted forms (space per spec, comma for compatibility, YAML list).
- [x] 1.4 Confirm `Skill.Get Allowed Tools` (`__init__.py:110`) now receives a real list (no `list(str)` char-split) and `Skill.Get Frontmatter` returns the normalized dict; update the docstrings (L76 / L101-110 / L132-134) to note all three forms and that `Get Frontmatter` returns the normalized `allowed-tools` list.

## 2. Tests (`tests/surfaces/skills/`)

- [x] 2.1 Flip `test_optional_fields.py::test_present_but_mistyped_optional_still_raises` (L58-64): `allowed-tools: Read, Write` now normalizes to `['Read','Write']` (not raises).
- [x] 2.2 Add a genuinely-mistyped case (e.g. `allowed-tools: 5`) asserting `InvalidConfigError` still raises — keeps the raise branch covered.
- [x] 2.3 Add normalization cases across all three forms: space (spec) `Bash(git:*) Bash(jq:*) Read` → `['Bash(git:*)','Bash(jq:*)','Read']`; comma `Read, Grep` / `Read,Grep` → `['Read','Grep']`; single `Read` → `['Read']`; YAML list unchanged; empty/whitespace → `[]`.
- [x] 2.4 Add tool-scoping-preservation cases: `Bash(git add:*)` (internal space) → `['Bash(git add:*)']`; `WebFetch(a.com,b.com)` (internal comma) → `['WebFetch(a.com,b.com)']` — NOT split.
- [x] 2.5 Add a **direct-validator** case (F-SKILL-2): call `Should Be Valid Frontmatter` on a dict built with a space/comma string (not via `Get Frontmatter`) and assert it passes — proving normalization happens in the validator too.
- [x] 2.6 Confirm the list-form assertions in `test_frontmatter.py` and the `VALID_SKILL` fixture stay green; a list with a non-string element still raises.

## 3. Docs + close out

- [x] 3.1 Note the widening in `CHANGELOG.md` (space/comma/list forms all accepted; comma is a documented compatibility extension; `provisional` minor bump).
- [ ] 3.2 Full local gate (ruff / ruff format / mypy / license / contract-sections / doc-count / doc-render / keyword-examples / pytest / robot).
- [ ] 3.3 `openspec validate fix-skills-allowed-tools --strict`; archive after implementation lands + gates green.
