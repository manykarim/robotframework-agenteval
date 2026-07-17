# Recipe 6: CI integration

**I want to** run my agenteval suites in CI — the free deterministic checks on
every push, and the model-backed checks on a schedule or before a release.

The trick is the tier split. Tier-1 keywords need no API keys and run in
milliseconds, so they belong on every commit. Tier-2 and Tier-3 keywords call a
model, so they belong behind a secret and a budget. Two jobs, one pipeline.

## Job 1 — deterministic gate (every push, no secrets)

Tier-1 keywords across all four libraries run on the base install alone. This is
your fast, keyless gate: skill frontmatter, MCP config and schemas, SubAgent
config drift, and hook decisions.

```yaml
# .github/workflows/agenteval.yml
name: agenteval

on: [push, pull_request]

jobs:
  deterministic:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install robotframework-agenteval
      - run: robot --xunit results.xml tests/tier1/
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agenteval-results
          path: results.xml
```

`robot --xunit results.xml` is Robot Framework's own JUnit-XML output — GitHub's
test reporters, GitLab, and Jenkins all read it natively. Robot exits non-zero
when any test fails, so the job fails the way CI expects.

Tag your deterministic tests so they're easy to select:

```robotframework
*** Test Cases ***
Skill Frontmatter Is Valid
    [Tags]    tier1
    ${fm}=    Skill.Get Frontmatter    ${CURDIR}/skills/web-search.md
    Skill.Should Be Valid Frontmatter    ${fm}
```

```bash
robot --include tier1 tests/
```

## Job 2 — model-backed checks (scheduled, behind a secret)

Tier-2 (judge) and Tier-3 (agent) keywords need the `[llm]` extra and a model.
Run them on a schedule or before a release, where the cost buys real confidence
— not on every push.

```yaml
  model-backed:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install 'robotframework-agenteval[all]'
      - run: robot --xunit results.xml tests/tier23/
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          AGENTEVAL_MODEL: anthropic/claude-sonnet-4-6
```

The generic adapter reads the model from `AGENTEVAL_MODEL` (or a per-keyword
`model=`), and LiteLLM reads the provider key from its usual environment
variable. Add the `on: schedule:` trigger to the workflow to run this nightly:

```yaml
on:
  push:
  pull_request:
  schedule:
    - cron: "0 6 * * *"
```

## Why the split

- **Tier 1 on every push** — deterministic, keyless, fast. This is where config
  drift and malformed skills get caught, and it costs nothing to run constantly.
- **Tier 2 and Tier 3 on a schedule** — they call a model, so they carry a cost
  and a little variance. Gate a release on them; don't block a typo-fix PR on a
  nightly's worth of agent calls.

Keeping a suite keyless where it can be is the honest default: don't pay a model
to check something a file parser already knows.

## See also

- [Recipe 1](./01-first-eval-in-five-minutes.md) — the local version of Job 1.
- [Recipe 4](./09-testing-claude-code-hooks.md) — an all-Tier-1 suite, ideal for Job 1.
