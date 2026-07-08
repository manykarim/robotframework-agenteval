# Spec: documentation-accuracy

## ADDED Requirements

### Requirement: Keyword counts match the shipped surface
`README.md` and `docs/index.md` SHALL state the same keyword total and library count, and that
total SHALL equal the actual number of unique keywords shipped across the libraries (as reported
by libdoc). A CI check SHALL fail when the documented counts diverge from the derived count.

#### Scenario: Counts reconciled
- **WHEN** a user reads the keyword-count claims in `README.md` and `docs/index.md`
- **THEN** both state the same number, and that number matches the libdoc-derived unique keyword
  count (56 at the time of the finding; re-derived at implementation)

#### Scenario: Future drift is caught in CI
- **WHEN** a new keyword ships without the documented counts being updated
- **THEN** the docs-build CI check fails

### Requirement: README keyword tables list every shipped keyword
The README keyword tables SHALL include every public keyword, including the 6 currently missing:
`Stat.Mann Whitney U`, `Stat.Cliff Delta`, `Stat.Bootstrap Confidence Interval`,
`MCP.Compare Tool Discoverability`, `Skill.Get Activation Pass At K`,
`Skill.Compare Discoverability`.

#### Scenario: Missing keywords added
- **WHEN** a user searches the README tables for any of the 6 named keywords
- **THEN** each appears in the table for its library with a one-line description

### Requirement: README links only to content that exists
Every directory or page linked from `README.md` SHALL contain real content.
`docs/troubleshooting/` SHALL be populated by aggregating the per-recipe Symptom/Cause/Fix tables
into a browsable page; `docs/coming-from/` and `docs/scenarios/` SHALL either receive real
content or have their README links and empty directories removed.

#### Scenario: Troubleshooting page exists and aggregates recipes
- **WHEN** a user follows the README troubleshooting link
- **THEN** they land on a page listing Symptom/Cause/Fix entries aggregated from the recipes,
  each linking back to its source recipe

#### Scenario: No links to empty directories
- **WHEN** every link in `README.md` is resolved
- **THEN** none targets an empty directory

### Requirement: Recipe descriptions match recipe content
The README recipe table SHALL describe each recipe consistently with the recipe file itself; the
current persona mislabels (table says Devon/Raj/Many where recipe files use Priya and Mei) SHALL
be resolved by describing recipes by what they demonstrate rather than by persona-journey slots.

#### Scenario: No contradictory persona labels
- **WHEN** a user reads the README recipe table entry for any recipe and then opens the recipe
- **THEN** the table's description matches the recipe's content, with no conflicting persona
  attribution

### Requirement: All dryrun-eligible recipe code blocks pass
Every dryrun-eligible fenced `robotframework` code block in `docs/recipes/*.md` SHALL pass
`robot --dryrun` via the existing extraction harness
(`tests/integration/recipes/test_all_recipes_dryrun.py`). The 4 blocks currently skip-listed in
`_KNOWN_BROKEN_BLOCKS` SHALL be fixed against the shipped keyword surface and removed from the
skip list, leaving it empty.

#### Scenario: Broken blocks fixed and unskipped
- **WHEN** the recipe dryrun harness runs at CI
- **THEN** all 8 eligible blocks pass and `_KNOWN_BROKEN_BLOCKS` is empty
