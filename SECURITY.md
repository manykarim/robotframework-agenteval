# Security Policy

This document specifies how to **report security issues** in `robotframework-agenteval` + the **security guarantees** the library makes to its consumers. Per [NFR-SEC-01..05](_bmad-output/planning-artifacts/prd.md) + the references from [MAINTAINERS.md](./MAINTAINERS.md) and [SUPPORT.md](./SUPPORT.md).

## Reporting a Security Issue

**Do NOT use public GitHub Issues for security reports.**

Use one of these private channels:

- **GitHub private security advisory** (preferred): go to the repository's "Security" tab → "Advisories" → "Report a vulnerability". This provides an embargo'd discussion thread visible only to the reporter + maintainers.
- **Direct email** to the maintainer (see [MAINTAINERS.md](./MAINTAINERS.md) for the address).

### What to include in your report

A useful report includes:

- **agenteval version** (output of `agenteval --version` once Epic 8b ships the CLI; for Phase-1 pre-1.0 builds, the git commit hash + branch suffices)
- **Robot Framework version** + **Python version** + **OS** (Linux distribution + kernel version)
- **Minimal `.robot` file or Python snippet** that reproduces the issue
- **Expected secure behavior** + **observed behavior**
- **Suspected severity** (informational / low / medium / high / critical) — final triage is the maintainer's call
- **CVSS vector** if you have one (optional; helps prioritization)

### What NOT to do

- Do NOT file a public GitHub Issue or PR that discloses the vulnerability before coordinated disclosure.
- Do NOT include working exploit code in non-encrypted email channels.
- Do NOT test the vulnerability against production systems you don't own — agenteval is a library; consumers run their own CI.

## Disclosure SLA

| Phase | Target | Notes |
| --- | --- | --- |
| **Acknowledgement** | ≤7 calendar days from initial report | Maintainer confirms receipt + assigns a tracking issue (in the embargo'd advisory thread). |
| **Triage + initial assessment** | ≤14 calendar days | Severity + scope + remediation path documented in the advisory thread. |
| **Embargo period (default)** | ≤90 calendar days from acknowledgement | Coordinated disclosure with reporter. Extensions negotiable for cases needing upstream MCP-spec or dependency fixes. |
| **CVE assignment** (if applicable) | During or before public disclosure | Via GitHub's private advisory CVE flow. |
| **CHANGELOG credit** | At fix-release time | Reporters who request credit are named in the `## Security` section of the release's CHANGELOG entry. Reporters who request anonymity are honored. |

Solo + AI-agent-assisted maintainership ([MAINTAINERS.md](./MAINTAINERS.md)) means the SLA is best-effort. Orgs requiring contracted SLA or indemnification should pair with a paid-support arrangement or fork.

## Security Guarantees

agenteval makes the following structural security guarantees to its consumers. Each is enforced via conformance suite tests + CI checks where machine-verifiable.

### NFR-SEC-01: Credential Redaction (FR38a/b)

The library **will never persist user-provided credentials** (API keys, OAuth tokens, vendor credentials) to disk or trace artifacts in their original form. All credentials will be routed through `config.redact_env()` and user-extensible patterns via `config.add_redaction_pattern()` before any serialization.

> **Phase-1 status:** **forward-reference.** `config.redact_env()` + `config.add_redaction_pattern()` are NOT yet shipped — they are Epic 5 Story 5.3 (Evidence Block Redaction Wiring) deliverables. The conformance oracles for FR38a/b are Epic 1b Story 1b.5 deliverables. Phase-1 baseline (Story 1a.1 src/AgentEval/ scaffolding) does NOT yet enforce credential redaction; the binding guarantee activates when Epic 5 lands. Consumers running pre-Epic-5 builds MUST NOT pass real credentials through the library's surface.

**Forthcoming implementation (Epic 5+):**

- The OTel trace exporter (Epic 5 Story 5.3) will redact known API-key patterns + user-supplied regexes from span attributes.
- The Evidence Block format (per [`docs/contracts/evidence-block-format.md`](docs/contracts/evidence-block-format.md)) will apply the same redaction to `traces[].request_body`, `traces[].response_body`, and any `metadata.*` fields containing credential-shaped substrings.
- The conformance suite will verify unknown-shape redaction via FR38a/b oracles (Epic 1b Story 1b.5).

**Limits:** the library can only redact patterns it recognizes (built-in regex set) or that consumers register via `add_redaction_pattern()`. Custom credential formats not matching either path may slip through; consumers are responsible for registering their own patterns.

### NFR-SEC-02: No `eval()` on User Input

The library **never calls `eval()` on user-provided strings** except via the explicitly-opted-in AssertionEngine `validate` operator (`__init__(allow_validate_operator=True)`, default `False`, per FR43 + [ADR-014 `ValidateOperatorDisallowed`](docs/adr/ADR-014-error-class-hierarchy.md)).

All other AssertionEngine matchers (`equals`, `contains`, `greater_than`, etc.) use safe comparison operators. CI test asserts no `eval()` calls exist on user-input paths in default-configured library.

### NFR-SEC-03: TLS in Transit

All LLM provider traffic uses **TLS in transit** (delegated to LiteLLM / provider SDKs). The library does NOT relax certificate validation or expose any HTTP-without-TLS opt-out for provider endpoints.

MCP transports:

- **Streamable HTTP** transport uses TLS.
- **`stdio` and in-memory** transports are local-process-only by design (no network egress).

### NFR-SEC-04: Supply-Chain Trust Boundary

agenteval **never auto-downloads, installs, or auto-updates vendor CLI binaries** (`claude`, `codex`, `copilot`, `goose`, `pi`, `opencode`). The user explicitly installs binaries per FR47.

**Trust boundary statement:** the library trusts vendor binaries on `$PATH` to the same level the user does. Compromised vendor binaries are out of scope for agenteval's threat model — consumers are responsible for the integrity of their tooling.

> **Note on `robotframework-agentguard`:** per the project's [`feedback_agentguard_inspiration_not_dependency`](docs/adr/ADR-001-architectural-influences-catalog.md) working norm, agentguard is INSPIRATION ONLY — agenteval has no agentguard dependency, no agentguard CVE inheritance, and no obligation to track agentguard's security advisories. Reviewed patterns are catalogued in [`ADR-001`](docs/adr/ADR-001-architectural-influences-catalog.md) with explicit divergence rationale where agenteval's security posture differs.

### NFR-SEC-05: No Phone-Home

The library **does NOT phone home**. Only the following network egress is possible:

- **LLM provider endpoints** (per user-configured providers — explicit setup required).
- **OTLP endpoints** (Phase 2, opt-in via `[otlp]` extra + explicit endpoint configuration).

The library `__init__(telemetry=False)` will eliminate all OTel listener egress.

> **Phase-1 status:** **forward-reference.** The `__init__(telemetry=False)` Library kwarg is wired by Story 1a.6 (FR44). The `Assert No Egress To` conformance fixture lands in Epic 1b Story 1b.5. Phase-1 baseline (commit `90d6f5c`) ships only Story 1a.1's `src/AgentEval/cli.py` Phase-1 placeholder + 3 security stubs — no OTel listener, no network egress paths exist yet to disable.

The conformance suite will verify this via the `Assert No Egress To` fixture in default-configured + `telemetry=False` configurations once the relevant stories land.

## CodeQL Continuous Scanning

The repository runs **CodeQL static analysis** on every PR + push to `main` + a weekly full-repo scan, per [`.github/workflows/security-scan.yml`](.github/workflows/security-scan.yml). Findings appear in the GitHub Security tab. CodeQL queries use the `security-and-quality` query suite.

Spike + skill code (`_bmad-output/spikes/**`, `.claude/skills/**`, `_bmad/**`) is excluded from CodeQL scanning via [`.github/codeql/codeql-config.yml`](.github/codeql/codeql-config.yml) — this is non-shippable code that doesn't affect consumers.

## Dependency Updates + CVE Posture

agenteval uses **exact pins** for security-critical dependencies (per [ADR-004 hosted-MCP observation](docs/adr/ADR-004-hosted-mcp-observation.md) Consequences):

- `mcp==1.27.1`
- `robotframework==7.4.2`
- `robotframework-pabot==5.2.2`
- `anyio==4.13.0`

Other production dependencies use range pins with sane upper bounds. CVE disclosures affecting pinned deps trigger a patch-bump release; consumers SHOULD subscribe to GitHub releases for notification.

## Acknowledgements

Security reporters who request credit are listed here once a fix ships. Anonymous reports are honored.

(No reports as of Phase 1.)
