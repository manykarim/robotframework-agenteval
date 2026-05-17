# Security Policy

Per NFR-SEC-04 + the references from [MAINTAINERS.md](./MAINTAINERS.md) and [SUPPORT.md](./SUPPORT.md), this document specifies how to report security issues in **robotframework-agenteval**.

> **⚠️ PLACEHOLDER — full policy lands in Story 1a.5.** This minimal disclosure surface exists so that the dead links in MAINTAINERS.md / SUPPORT.md (created by Story 1a.1) have something to resolve to. Story 1a.5 (Project Hygiene — CONTRIBUTING + SECURITY + Issue Templates + License Headers) authors the authoritative version per the spec text quoted below.

## How to report a security issue

**Do NOT use public GitHub Issues for security reports.** Use one of:

- **GitHub private security advisories** for this repository — go to the repository's "Security" tab, click "Report a vulnerability". This is the preferred channel; it provides an embargo'd discussion thread.
- **Direct email** to the maintainer (see [MAINTAINERS.md](./MAINTAINERS.md)).

## What to include

A useful report includes:

- agenteval version (output of `agenteval --version` once Epic 8b ships the CLI)
- Robot Framework version + Python version + OS
- Minimal `.robot` file or Python snippet that reproduces the issue
- Expected secure behavior + observed behavior
- Suspected severity (informational / low / medium / high / critical) — final triage is the maintainer's call

## Triage SLA

- **Acknowledgement**: ≤7 days from report
- **Embargo period**: ≤90 days by default (negotiable for cases needing coordinated disclosure or upstream fixes)
- **Credit**: reporters who request it are credited in the CHANGELOG entry for the fix

## Forthcoming content (Story 1a.5 deliverable)

Per the Story 1a.5 spec in `_bmad-output/planning-artifacts/epics.md`:

> SECURITY.md exists at the repo root specifying responsible disclosure policy: report channel (private GitHub security advisory), expected acknowledgement time (≤7 days), embargo period (≤90 days), credential-redaction guarantee (FR38a/b — traces never contain raw credentials in published reports).

The credential-redaction guarantee (FR38a/b) + the security disclosure process language Story 1a.5 ratifies will replace this placeholder.
