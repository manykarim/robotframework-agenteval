## ADDED Requirements

### Requirement: SkillsLibrary parses and validates skill frontmatter deterministically

`SkillsLibrary` SHALL parse a skill's Markdown frontmatter and provide Tier-1 getters and a validator for its fields (name, description, allowed tools, disable-model-invocation) with fail-loud handling of missing or mistyped fields.

#### Scenario: Read a frontmatter field

- **WHEN** a user calls `Skill.Get Allowed Tools` on a valid skill file
- **THEN** the library returns the declared tool list

#### Scenario: Invalid frontmatter fails validation

- **WHEN** a user calls `Skill.Should Be Valid Frontmatter` on a skill missing a required field
- **THEN** the assertion fails and names the missing field

### Requirement: Skill activation is testable in agent mode with pass@k

`SkillsLibrary` SHALL provide agent-mode keywords that decide whether a skill activates for a given prompt, an activation pass@k over repeated trials, and a `Should Activate For` assertion. These keywords SHALL be Tier-3 and SHALL resolve their adapter through the shared spine. Activation detection SHALL be a single shared implementation, not per-keyword copies.

#### Scenario: Assert a skill activates for a prompt

- **WHEN** a user runs `Skill.Should Activate For` with a prompt that should trigger the skill
- **THEN** the keyword drives the agent and passes only if the skill activated

#### Scenario: Activation pass@k over trials

- **WHEN** a user runs `Skill.Get Activation Pass At K` with k over N trials
- **THEN** the keyword reports the pass@k estimate with a confidence interval

### Requirement: Skill activation is testable in LLM-judge mode

`SkillsLibrary` SHALL provide a Tier-2 activation check that uses the shared LLM judge to decide whether a response reflects the skill's guidance, rather than relying only on a case-insensitive substring match. This SHALL be the honest LLM mode for the Skills surface.

#### Scenario: Judge-based activation decision

- **WHEN** a user requests a judge-based activation check for a response and a skill
- **THEN** the library asks the judge whether the response applied the skill and returns a decision with justification

### Requirement: Skill discoverability is scorable

`SkillsLibrary` SHALL provide a discoverability keyword that scores how well a skill's description surfaces it to a model for a set of tasks. Cross-arm A/B benchmarking, blind grading, and the skill-obsolescence verdict SHALL NOT be included in the base library.

#### Scenario: Score discoverability

- **WHEN** a user runs `Skill.Get Discoverability` for a skill over a task set
- **THEN** the library returns a discoverability score for that skill
