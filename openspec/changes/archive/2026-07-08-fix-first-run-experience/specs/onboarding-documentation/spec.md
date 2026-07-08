# Spec: onboarding-documentation

## ADDED Requirements

### Requirement: Skill frontmatter fields documented in the README
The README SHALL document the 4 required skill frontmatter fields (`name`, `description`,
`allowed-tools`, `disable-model-invocation`) with a minimal complete `SKILL.md` example, so a
user can author a valid skill file without reading libdoc HTML source or test fixtures.

#### Scenario: Frontmatter authorable from README alone
- **WHEN** a user copies the README's minimal `SKILL.md` example and runs the scaffolded skill
  validation suite against it
- **THEN** validation passes without consulting any other source

### Requirement: Hook config input schema documented
The documentation SHALL specify the hook `settings.json` input schema that
`HooksLibrary.Get Config` accepts (flat entries with `command`, plus optional `args`, `timeout`,
`matcher`) with a valid example, and SHALL explicitly state that the real Claude Code nested
`settings.json` hook format is not yet accepted (referencing the separate change that will add
it).

#### Scenario: Valid config writable from docs alone
- **WHEN** a user writes a hook config file following the documented schema and example
- **THEN** `Get Config` parses it without `InvalidHookConfigError`

#### Scenario: Real-Claude-Code divergence disclosed
- **WHEN** a user reads the hook config documentation
- **THEN** it warns that a real Claude Code `settings.json` will currently be rejected and points
  to the tracked follow-up

### Requirement: Mock-to-live-model path documented
The docs SHALL include a "Running against a real model" page covering provider selection, the
model string format, which API-key environment variables each supported provider reads, a minimal
copy-paste example, and the cost guardrail, linked from the README quick start.

#### Scenario: User switches from mock to live
- **WHEN** a user who has the scaffold running on the mock provider follows the page's steps with
  a valid API key
- **THEN** they reach a working live-provider invocation without consulting sources outside the
  documented pages

### Requirement: .env.example names the API-key variables
`.env.example` SHALL include commented entries for the API-key environment variables live
providers require (at minimum `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`), with a note on how they
reach the provider layer.

#### Scenario: API keys discoverable in .env.example
- **WHEN** a user opens `.env.example` looking for where to put an API key
- **THEN** they find the named key entries and a pointer to the real-model page

### Requirement: User-facing docs are jargon-free and tier-light
`README.md`, `docs/index.md`, and `docs/recipes/*.md` SHALL NOT contain internal
project-management identifiers (Story/Epic/FR/ADR/DF-X-SY/C-numbers, persona-journey slot labels,
review-provenance notes); where a design rationale deserves a reference, it SHALL be linked by
topic. The determinism-tier system SHALL appear in first-run docs only as a short note linking to
its full documentation. Identifiers remain permitted in ADRs, `docs/contracts/`, maintainer docs,
and `_bmad-output/`.

#### Scenario: README free of internal identifiers
- **WHEN** `README.md`, `docs/index.md`, or any `docs/recipes/*.md` is searched for
  Story/Epic/FR/ADR/DF-/C-number identifier patterns
- **THEN** no matches remain in prose or code comments

#### Scenario: Tier system de-emphasized
- **WHEN** a first-run user reads the README quick start
- **THEN** determinism tiers appear only as a brief note with a link, not as a prerequisite
  concept
