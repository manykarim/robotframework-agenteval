---
name: example-valid-skill
description: A canonical valid skill used by Story 2.1 unit + RF integration tests. Verifies all 4 required frontmatter fields (name, description, allowed-tools, disable-model-invocation) parse correctly + the NFR-PERF-02 ≤ 50 ms latency target on the 5 KB-class reference fixture for Tier-1 static-inspection keywords.
allowed-tools:
  - read_file
  - write_file
  - search_database
  - run_tests
disable-model-invocation: false
---

# Example Valid Skill

This skill body is intentionally long enough to push the total file size into the
target range used by NFR-PERF-02's "typical 5 KB skill .md" benchmark wording.
The frontmatter parser only reads the YAML block between the `---` delimiters,
so the body content has no semantic impact on `Skill.Get Frontmatter`. Padding
follows below.

## Section 1: Why this fixture exists

Story 2.1 ships the first 5 Tier-1 static-inspection keywords + the first
adversarial-review-validated skill `.md` parser. The Phase-1 contract is that
the keywords read ONLY the frontmatter; the body is a pass-through. Future
epics that exercise the body (e.g., Skill Get Activation Decision in Epic 7
per PRD FR4) will treat the body content as input to a model-API-key-gated
classifier, NOT as input to a static-inspection routine.

## Section 2: What the fixtures cover

The Story 2.1 acceptance criteria require three fixtures:

1. example-valid.md (this file) — all 4 required fields present + correctly
   typed; the YAML parses without error; the structural validator returns
   silently.
2. example-malformed-yaml.md — the YAML between the `---` delimiters does
   not parse; the parser raises `InvalidSkillFrontmatterError` with a
   line number from `yaml.YAMLError.problem_mark.line`.
3. example-missing-fields.md — valid YAML but missing the `name` field;
   the structural validator raises `InvalidSkillFrontmatterError` listing
   the missing field.

## Section 3: Determinism contract

Per FR31a + Story 1b.6 determinism-contract.md: this fixture's bytes are
deterministic. There are no timestamps, no random values, no auto-generated
identifiers. The same bytes parse to the same dict across every run on
every supported Python interpreter. This determinism is what makes the
conformance suite's fixture-replay model reliable for Tier-1 keywords.

## Section 4: Tool allowlist examples

The `allowed-tools` field shows the canonical tool-name shape: short
lowercase tokens separated by underscores, no namespacing prefix, no
version suffix. Future skill authors should follow the same shape so the
allowlist remains scannable at a glance + remains comparable across
similar skills via simple set-equality.

## Section 5: disable-model-invocation semantics

When `disable-model-invocation: true` the skill is meant to be used by a
human or by a deterministic pipeline; the model layer is bypassed. When
`disable-model-invocation: false` (this fixture's value) the model layer
may dispatch to the skill via the standard tool-invocation pathway. The
Phase-1 keywords surface this bool as-is; downstream layers (Epic 7's
activation classifier; Epic 4's runtime dispatcher) interpret it.

## Section 6: padding

This section pads the file to land near the 5 KB benchmark size used in
the NFR-PERF-02 latency target wording. The fixture-replay model assumes
parser performance is roughly linear in file size for the typical skill
size range (≤ 50 KB); the 5 KB number is the median observed during the
PRD interview phase. Larger fixtures may be added later to verify the
linear-scaling assumption; for Story 2.1 the 5 KB-class fixture is the
golden-path reference.

Padding text continues. The padding has no meaning beyond its byte
count. The structural validator does not read the body. The frontmatter
parser does not read past the closing `---`. The body content can change
across stories without changing any test outcomes; the fixture's bytes
need only be stable across runs to satisfy FR31a determinism.

End of fixture.
