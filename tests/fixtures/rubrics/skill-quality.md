# Skill Quality Rubric

Canonical Phase-1 rubric example for Story 12.1 unit + integration tests
+ Recipe Gallery #4 three-tier validation flow.

## Criteria

- correctness: Did the agent produce the requested output without obvious errors?
- completeness: Did the agent address all parts of the user prompt?
- tool-use-appropriateness: Did the agent invoke tools when needed (and refrain when not)?
- response-clarity: Is the agent's response well-structured and easy to read?

## Threshold

Pass if numeric_score >= 7.0

## Examples

### Example 1 — Pass

Prompt: "List the 3 largest files in /tmp."
Response: Includes 3 file paths with sizes; uses `du` or `ls -lS`.
Score: 9.0 (correctness, completeness, appropriate tool use).

### Example 2 — Fail

Prompt: "Open the file foo.py and explain its purpose."
Response: "I can't open files." (Despite having a file-read tool available.)
Score: 3.0 (refused the task despite having appropriate tools).
