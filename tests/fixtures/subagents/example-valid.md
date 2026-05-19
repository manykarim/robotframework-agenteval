---
name: example-valid-subagent
description: A canonical valid sub-agent fixture used by Story 2.2 unit + RF integration tests. Verifies the 2 required frontmatter fields (`name`, `description`) per PRD FR3 plus the 2 optional fields (`tools`, `model`) parse correctly when present.
tools:
  - read_file
  - run_tests
model: claude-sonnet-4-6
---

# Example Valid Sub-Agent

This sub-agent body is intentionally deterministic — no timestamps, no
randomized identifiers. The frontmatter parser only reads the YAML block
between the `---` delimiters per PRD FR3.

## Phase-1 contract

`Subagent.Get Frontmatter` returns the parsed YAML as a dict. The dict
ALWAYS contains `name` + `description`; it MAY contain `tools` +
`model` when those optional fields are present (they are here).
