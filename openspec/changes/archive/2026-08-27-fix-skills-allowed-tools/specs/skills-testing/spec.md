## ADDED Requirements

### Requirement: allowed-tools accepts the space, comma, and list forms

`SkillsLibrary` SHALL accept `allowed-tools` written as a space-separated string (the
Agent Skills spec form, e.g. `Bash(git:*) Bash(jq:*) Read`), a comma-separated string
(accepted as a documented compatibility extension), or a YAML list of strings, treating
all three as equivalent inputs. All SHALL be normalized to the same list of tool
strings by splitting on whitespace or commas **only at parenthesis depth 0**, so
tool-scoping syntax containing an internal space or comma (e.g. `Bash(git add:*)`,
`WebFetch(a.com,b.com)`) is preserved as a single token. Every frontmatter reader —
`Skill.Get Allowed Tools`, `Skill.Get Frontmatter`, and `Skill.Should Be Valid
Frontmatter` — SHALL observe the normalized list regardless of whether the frontmatter
was parsed from a file or supplied directly as a dict, so a caller never sees the raw
string or a character-split of it. A genuinely mistyped value (a scalar that is neither
a string nor a list of strings, e.g. a number) SHALL still fail validation with
`InvalidConfigError`.

#### Scenario: The space-separated spec form is accepted and normalized

- **WHEN** a user validates or reads a skill whose frontmatter declares
  `allowed-tools: Bash(git:*) Bash(jq:*) Read`
- **THEN** validation passes and `Skill.Get Allowed Tools` returns
  `['Bash(git:*)', 'Bash(jq:*)', 'Read']`, preserving each scoped token intact

#### Scenario: The comma-separated compatibility form is accepted and normalized

- **WHEN** a user reads a skill whose frontmatter declares `allowed-tools: Read, Grep`
- **THEN** `Skill.Get Allowed Tools` returns `['Read', 'Grep']`

#### Scenario: The YAML list form is unchanged

- **WHEN** a user reads a skill whose frontmatter declares `allowed-tools` as a YAML
  list
- **THEN** `Skill.Get Allowed Tools` returns that list unchanged

#### Scenario: A scoped token with an internal separator is not split

- **WHEN** `allowed-tools` contains a scoped token with an internal space or comma
  (e.g. `Bash(git add:*)` or `WebFetch(a.com,b.com)`)
- **THEN** that token is preserved whole and not split at the internal separator

#### Scenario: The standalone validator accepts a directly-supplied dict

- **WHEN** a user calls `Skill.Should Be Valid Frontmatter` on a frontmatter dict built
  directly (not via `Skill.Get Frontmatter`) whose `allowed-tools` is a space or comma
  string
- **THEN** validation passes, because the validator normalizes the value itself

#### Scenario: A genuinely mistyped value still fails

- **WHEN** a user validates a skill whose `allowed-tools` is a non-string, non-list
  scalar (e.g. a number) or a list containing a non-string element
- **THEN** `Skill.Should Be Valid Frontmatter` fails with `InvalidConfigError` naming
  the field
