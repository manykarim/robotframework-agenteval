# Support

Per NFR-MAINT-02, this document specifies how to ask for help with **robotframework-agenteval**.

## Where to ask

- **Bug reports + feature requests**: [GitHub Issues](https://github.com/manykarim/robotframework-agenteval/issues). Use the issue templates (bug-report / feature-request / question) — they pre-fill the structured prompts that maintainers need to triage efficiently.
- **Security issues**: do NOT use public Issues. See [SECURITY.md](./SECURITY.md) for the private-disclosure channel.
- **General usage questions**: GitHub Issues with the `question` template, or post-1.0 release a community discussion channel TBD.

## Triage SLA

- **Initial triage** (acknowledgment + label assignment): within 5 business days, best-effort, subject to maintainer availability.
- **Security issues**: ≤7 days acknowledgement (per SECURITY.md), ≤90 days embargo by default.
- **PR reviews**: best-effort; the project's solo + AI-agent-assisted posture means PR-volume-load shapes turnaround.

## Before opening an issue

1. Check existing issues (open + closed) for prior discussion.
2. Read the relevant `docs/recipes/` entry if your question is "how do I...".
3. Read the relevant `docs/contracts/` entry if your question is about expected behavior.
4. For bug reports: include your `agenteval --version` output (post-CLI implementation), RF version, Python version, OS, a minimal reproducing `.robot` file, expected behavior, and actual behavior.

## What's NOT supported

Per the project's solo posture (see [MAINTAINERS.md](./MAINTAINERS.md)):

- Real-time chat or pager-style support.
- Custom integrations beyond what the documented contracts ship.
- Backporting fixes to pre-1.0 versions.
- macOS in Phase 1 (D2.1 architect waiver — deferred to Phase-1.5; see `docs/adr/ADR-016` carry-over context).
