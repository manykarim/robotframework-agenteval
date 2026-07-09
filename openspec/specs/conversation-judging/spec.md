# conversation-judging Specification

## Purpose
TBD - created by archiving change add-multi-turn-conversation-testing. Update Purpose after archive.
## Requirements
### Requirement: Judge.Get Score accepts a turn result (documented) and a transcript (extended)

`Judge.Get Score` SHALL continue to accept a single `AgentRunResult` — which
already makes per-turn judging work, since a conversation turn's `result` IS
an `AgentRunResult` — and its documentation SHALL state the per-turn usage
explicitly. The keyword SHALL additionally accept a `ConversationTranscript`
as `result=`; in that case the judge prompt SHALL render the full role-tagged
transcript (all user and agent turns in order) instead of a single
`response_text`, using a shared transcript renderer. Rubric loading,
`JudgeScore` shape, guardrails, and the calibration discipline (κ≥0.7 gate)
SHALL be unchanged.

#### Scenario: Judging a single turn
- **WHEN** `${r2} =    Send Message    ${conv}    Make it business class` is
  followed by `Judge.Get Score    result=${r2}    rubric=${CURDIR}/rubrics/upsell.md`
- **THEN** the judge SHALL score that turn's response and return a `JudgeScore`
  with the standard fields

#### Scenario: Judging a whole transcript
- **WHEN** `${t} =    Get Conversation Transcript    ${conv}` is passed as
  `Judge.Get Score    result=${t}    rubric=${CURDIR}/rubrics/goal-completion.md`
- **THEN** the composed judge prompt SHALL contain every turn's role and
  content in chronological order, and a single `JudgeScore` SHALL be returned
  for the conversation as a whole

### Requirement: Judge Turn Should Pass convenience assertion

The system SHALL provide `Judge Turn Should Pass    ${conv}    rubric=<path>
turn=-1    judge_adapter=generic    judge_model=<model>` — an un-namespaced
assertion-style keyword (matching the existing `... Should ...` assertion
convention) that scores the selected agent turn (negative indices count from
the end; default `-1` = last agent turn) via the same path as
`Judge.Get Score` and FAILS the test when `pass_threshold_met` is false,
reporting the numeric score and the judge's reasoning in the failure message.
It SHALL be annotated Tier-2 and budget-guarded identically to
`Judge.Get Score`.

#### Scenario: Passing turn passes the test
- **WHEN** the judge scores the last agent turn at/above the rubric threshold
- **THEN** `Judge Turn Should Pass    ${conv}    rubric=${RUBRIC}` SHALL pass

#### Scenario: Failing turn fails with score and reasoning
- **WHEN** the judge scores the selected turn below the rubric threshold
- **THEN** the keyword SHALL fail and the failure message SHALL include the
  numeric score, the threshold, and the judge's reasoning text

#### Scenario: Turn selection by index
- **WHEN** `Judge Turn Should Pass    ${conv}    rubric=${RUBRIC}    turn=0`
  is executed on a 3-agent-turn conversation
- **THEN** the FIRST agent turn SHALL be the one scored

#### Scenario: Out-of-range turn index is a clear setup failure
- **WHEN** `turn=5` is requested on a conversation with 2 agent turns
- **THEN** the keyword SHALL fail with a message naming the requested index
  and the available agent-turn count, without making any LLM call

