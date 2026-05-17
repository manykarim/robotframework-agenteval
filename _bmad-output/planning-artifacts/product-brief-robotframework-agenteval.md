---
title: "Product Brief: robotframework-agenteval"
status: "complete"
created: "2026-05-15"
updated: "2026-05-16"
inputs:
  - _bmad-output/planning-artifacts/research/technical-robot-framework-agent-evaluation-library-design-research-2026-05-15.md
audience: "QA / test automation engineers (primary); compliance / audit / risk teams (secondary)"
purpose: "Foundation for PRD"
---

# Product Brief: robotframework-agenteval

## Executive Summary

`robotframework-agenteval` is an open-source Robot Framework library that lets QA and test-automation engineers evaluate AI agents — MCP servers, Claude Code skills, sub-agents, hooks, and full multi-step LLM agents — using the same keyword-driven, BDD-style suites, listeners, and `output.xml` reporting they already run in CI.

Today, every serious agent-eval framework (DeepEval, Ragas, Promptfoo, Inspect AI, LangSmith, Braintrust) assumes a Python-script or hosted-SaaS workflow. None plug into Robot Framework. QA teams asked to test their org's new AI features face a forced choice: maintain a parallel Python eval stack with separate dashboards, or skip rigorous eval entirely. Both are bad answers, and the broader category context — EU AI Act high-risk obligations enforceable **August 2, 2026** with continuous-evaluation and 6-month log-retention requirements — sharpens the cost of skipping for regulated industries (though the AI Act itself is satisfied at the system/QMS level, not by tool selection).

This library closes that gap with a uniform getter+assertion keyword surface (`Get Tool Call Count    ==    3`), three explicit determinism tiers (Static / LLM-deterministic / Agent-non-deterministic), statistical primitives (`Run N Times`, `Pass At K`) instead of brittle polling, and OpenTelemetry GenAI-conventions tracing wired through Robot Framework's listener system. It shares its structural skeleton with the sibling `robotframework-agentguard` project — pattern-discovery risk is retired before MVP-week-one, and design decisions made once apply across the agent* portfolio.

## The Problem

QA and test-automation engineers are being handed AI features to validate, and the existing tools fail them in three ways:

- **Stack fragmentation.** A QA org standardized on Robot Framework now needs a parallel Python pytest stack just for agent evals — different runner, different reports, different CI integration, different on-call dashboards. Result: agent eval becomes a second-class citizen, run irregularly, with results invisible to the rest of the test pipeline.
- **Non-determinism breaks the assertion model.** "Same input → different output" erodes the very premise of CI gates. Without proper statistical handling (Pass@k, controlled re-runs, seeded determinism), teams either over-retry until tests pass by chance (survivorship bias) or accept high flakiness (Google reports ~16% of tests show flakiness; Microsoft tracks 49k flaky tests internally). Neither is acceptable as an audit trail.
- **No native bridge to the eval primitives QA needs.** Trajectory evaluation, tool-call assertions, MCP capability validation, and LLM-as-judge scoring are now mainstream methodology — but they only exist as Python objects in DeepEval/Ragas, not as Robot Framework keywords a QA engineer can call. Writing them as keyword wrappers is doable but ad-hoc, untested, and reinvented per team.

The cost of the status quo: agent quality gates ship late or not at all, regulatory evidence chains live in screenshots and ad-hoc scripts, and the QA function loses ground to ML-engineer-owned tooling that the broader org can't operate.

## The Solution

`robotframework-agenteval` exposes agent evaluation as a first-class Robot Framework library. The on-ramp is the **static-inspection tier**: install the library, point it at your repo's `.mcp.json`, `skills/`, `hooks/`, and sub-agent files, and the very first `.robot` suite runs in milliseconds with zero API keys, zero network, zero LLM cost — a "lint your agent config" experience that rewards installation immediately. From there, the same library scales up into real agent runs without changing tools.

Two complementary evaluation surfaces:

- **Tier 1 — Static inspection (the wedge).** No API key, no network, runs in milliseconds. Validates skill frontmatter, hook configurations, `.mcp.json` server configs, sub-agent definitions, MCP capability declarations — all the file-shape-stable artifacts that agents are configured from. Predicted to be the most-used surface in CI because it's free, deterministic, and gives every install something useful to do on day one. Acts as the funnel into Tiers 2/3.
- **Tiers 2 & 3 — Dynamic agent evaluation (opt-in API keys).** Real MCP tool calls, full agent runs, LLM-as-judge scoring, trajectory matching, tool-call hit-rate / success-rate / unnecessary-call-rate metrics, latency and token assertions — backed by `Run N Times` + `Pass At K` (HumanEval unbiased estimator) for honest non-deterministic assertions instead of single-shot flakes.

**Time-to-first-test target (defined cohort):** on a Linux/macOS dev machine with Python ≥3.12 and `uv` pre-installed, with no corporate proxy or cert friction, against the bundled echo MCP server and using only Tier 1 (no API keys), a developer follows the README and lands their first green eval in **≤ 5 minutes**. The number is a published, walkthrough-timed bar — not a marketing line — and we expect higher medians on Windows/corporate environments, which is why a documented "first-day troubleshooting" guide ships with v1.0.

Every keyword follows the same `(assertion_operator, assertion_expected, message)` triple shape (the pattern proven in `robotframework-browser`), so the entire surface is uniform and predictable. Polling is explicitly banned on non-deterministic keywords — the library raises `PollingDisallowedError` if a user tries — to prevent survivorship-biased pass rates from polluting CI reports.

## What Makes This Different

- **Robot Framework-native, by design.** Not a wrapper, not a CLI shoe-horned in. Listener v3, DynamicCore, AssertionEngine, libdoc reference, `output.xml` integration, BDD syntax — built for the way RF teams actually work. The five existing MCP-eval frameworks (lastmile-ai/mcp-eval, wolfeidau/mcp-evals, @mcp-testing/server-tester, DeepEval MCP, MCPBench) all target Python/Go/TypeScript-native workflows; **zero target Robot Framework**. Clean, defensible niche rather than head-on competition.
- **Statistical determinism, not retry-until-green.** Pass@k with the HumanEval unbiased estimator, temp=0 defaults, a documented polling ban, and an explicit three-tier ACL gate model give CI gates that are honest about uncertainty instead of hiding it. This is what audit-grade eval looks like.
- **Provider-agnostic out of the box.** LiteLLM-backed default adapter (140+ providers, including Ollama and vLLM for local models), with a clean `LLMProviderAdapter` Protocol so a vendor-native SDK can be swapped in later without touching keywords. Separate `CodingAgentAdapter` Protocol with planned implementations for Claude Agent SDK, OpenAI Agents SDK, and a generic LiteLLM-backed runtime — so users aren't locked to one agent framework.
- **Observability built on the GenAI standard.** OpenTelemetry GenAI semantic conventions adopted natively (span hierarchy `invoke_agent → chat → execute_tool`, `gen_ai.*` attributes for model, tokens, finish reasons, tool calls). Memory + JSONL + OTLP exporters. Maps naturally to the EU AI Act Article 12 logging and 6-month retention obligations.
- **Statistical honesty as a default.** The polling ban, Pass@k unbiased estimator, and `temp=0` defaults aren't just features — they're a stance: *CI gates over LLM agents must report honest uncertainty, not retry-until-green theatre.* No competitor articulates this principle by name; it's a memorable banner that compliance teams and engineering leaders both recognize as the mature posture.
- **Shared skeleton with `robotframework-agentguard`.** The structural pattern (DynamicCore composition, `_assertions/` kernel, listener entry point, provider Protocol, tiered keywords, stats module, `.env` config with credential redaction) is shared verbatim with the sibling `robotframework-agentguard` project, also pre-1.0. This is *shared internal pattern reuse*, not battle-tested-library inheritance — but it does retire most pattern-discovery risk and means design decisions made once apply across the agent* portfolio.

## Who This Serves

**Primary: QA / test-automation engineers** who already use Robot Framework — typically in fintech, SaaS, healthcare, BFSI orgs where keyword-driven and BDD automation is the standard. They're being asked to test AI features without ML background, they want declarative test syntax over hand-rolled pytest scaffolding, they need agent-quality gates in their existing pipeline, and they need eval results in the same `output.xml` their leadership already reads. Their "aha moment" is writing `Get Tool Call Names    contains    search_database` in a `.robot` file and seeing it light up in their existing CI dashboard within five minutes of `uv add`.

**Secondary: compliance, audit, and risk teams.** The EU AI Act, the FDA's evolving AI/ML guidance, and internal model-risk frameworks all require continuous evaluation evidence with reproducible artifacts and minimum log retention. These teams don't write tests, but they consume the evidence — and Robot Framework's `output.xml` plus OpenTelemetry trace artifacts give them an audit-friendly chain that hosted SaaS dashboards struggle to export. Reinforces the regulatory positioning and unlocks budget in regulated industries.

## Success Criteria

**Phase 1 (MVP, 6–8 weeks calendar at solo + AI-agent-assisted throughput) — outcome bars:**

*Throughput assumption stated honestly: this is a single-maintainer project executed with heavy use of coding agents (Claude Code et al.) as a force multiplier. The 6–8 week target is calendar time, not isolated person-weeks; if AI-agent productivity assumptions don't hold (debugging on novel integrations, doc grind, RF/MCP edge cases), the realistic slip is +50% and the project re-baselines without ceremony.*

- Time-to-first-test: a QA engineer goes from `uv add robotframework-agenteval` to a passing eval against an echo MCP server in **≤ 5 minutes**, following the README only.
- Test-tier reliability: unit ≥99%, smoke 100%, live-nightly ≥95%.
- Coverage: full MCP spec primitives (tools, resources, prompts) plus static-inspection targets for Claude Code skills, hooks, sub-agents, and `.mcp.json`.

**Phase 2 (4–6 weeks) — capability bars:**
- ≥3 agent runtimes via `CodingAgentAdapter` (Claude Agent SDK, OpenAI Agents SDK, generic LiteLLM).
- ≥6 LLM provider backends usable end-to-end via LiteLLM (OpenAI, Anthropic, Google, Bedrock, Ollama, vLLM at minimum).
- LLM-judge sub-library with calibration cookbook; OTLP trace exporter shipped.

**Adoption bars (with decision implications, not vibes):**
- **Month 6:** ≥ 500 unique installers/month (PyPI), ≥ 3 inbound GitHub issues from non-author users (signal that real installs are hitting reality), ≥ 1 RoboCon 2027 talk submitted, ≥ 1 community blog post or RF-forum thread citing the library. *If two of four miss → trigger a positioning / DX retrospective before Phase 2 investment.*
- **Month 12:** ≥ 2,000 unique installers/month, ≥ 5 public GitHub dependents (production repos importing the library), ≥ 1 RoboCon 2027 talk accepted, ≥ 1 inbound community PR landed. *If majority miss → reframe the brief from "de facto standard" to "niche-but-deep" before further scope expansion.*
- **User-outcome proxies (best-effort from issue tracker, GitHub discussions, voluntary telemetry opt-in):** the published 5-min happy-path walkthrough remains green on every supported Python/OS combination in CI; closed issue ratio of "first install" / "first eval ran" complaints trends down release-over-release; share of installs with at least one Tier-2/3 use rises measurably between v1.0 and v1.x.

## Scope

**In for v1.0 (Phase 1 MVP):**
- Top-level `AgentEval` library (DynamicCore composition).
- MCP keywords (start/connect/stop server, list/call tool, capabilities, schema validation).
- Static-inspection keywords for skills, hooks, sub-agents.
- LiteLLM + Mock providers; generic-only `CodingAgentAdapter`.
- AssertionEngine kernel with three-tier ACL gates and polling ban.
- OpenTelemetry listener + in-memory + JSONL trace backends.
- Metrics keywords (tool-call count/names/hit-rate/success-rate/trajectory/tokens/latency).
- Statistical primitives (`Run N Times`, `Pass At K`).
- YAML scenario loader + `Run Scenario File`.
- Three example `.robot` suites, libdoc reference, README.

**Phase 2:** Claude Agent SDK + OpenAI Agents SDK adapters, LLM-judge sub-library, OTLP exporter, advanced statistics (Mann-Whitney U, Cliff's δ, bootstrap CI).

**Phase 3 (TBD):** LangGraph / CrewAI / AutoGen bridge adapters as separate `[bridges-*]` extras; HumanEval / SWE-bench fixture loaders; sandboxing for agent-generated code.

**Explicitly out of scope:**
- **Not a hosted observability platform.** No dashboards, no human-annotation UI, no regression-tracking SaaS. LangSmith, Braintrust, and Phoenix already do this — this library is strictly the CI/test-runner gating layer that feeds them (or stands alone in air-gapped envs).
- **Not original metric R&D.** Wraps and borrows established methodology — HumanEval Pass@k, BFCL trajectory match, OpenTelemetry GenAI semantic conventions, the wolfeidau/mcp-evals 5-dimension rubric — rather than inventing new scoring approaches.
- **Not a prompt-management harness.** Scope is agents (multi-step, tool-calling, MCP-using). Single-shot prompt A/B testing is Promptfoo's territory.
- **Not for non-Robot-Framework users.** No standalone CLI, no Python-script entry points. If you don't run Robot Framework, this isn't your tool.

## Documentation, DX & Support

Adoption hinges as much on documentation surface and developer experience as on keyword breadth. Day-one deliverables shipped with v1.0:

- **Tutorials, not just reference:** "First agent eval in 5 minutes" walkthrough (timed and published), recipe gallery (≥ 8 worked examples covering MCP tool assertions, trajectory checks, judge scoring, scenario YAML), CI-integration cookbook (GitHub Actions, GitLab CI), and a "Coming from DeepEval / Promptfoo" migration mapping for users switching stacks.
- **Error messages that teach:** every domain error (notably `PollingDisallowedError`) ships with the recommended alternative inline, with copy-pasteable `.robot` snippets. AssertionEngine failures wrap with library-specific context so users see *what evaluation* failed, not just *which assertion*.
- **First-day troubleshooting guide:** Windows/corporate-environment caveats (Python version managers, PyPI proxy/cert), `uv` alternatives, MCP-server bring-up failures, common API-key/`.env` mistakes — explicitly addressed because the QA-engineer install environment is rarely the friendly Linux dev box.
- **Maintenance commitment:** issue-triage SLA (best-effort 5 business days for triage; security issues prioritized), public roadmap, semver discipline. **Bus-factor posture stated honestly:** initial maintainership is solo + AI-agent-assisted, not a team — adopting orgs that need vendor SLAs or indemnification should pair with a paid-support arrangement or fork. Contributor onboarding (`CONTRIBUTING.md`, "good first issue" labels, agent* portfolio shared-pattern docs) is treated as a first-class deliverable to grow the maintainer base over time.

## Technical Approach (high-level)

Python ≥3.12, `uv` + `hatchling` build, `pyproject.toml`-only. Pinned dependencies on `robotframework>=7.4,<9.0`, `robotframework-pythonlibcore`, `robotframework-assertion-engine`, the official `mcp` Python SDK, and `LiteLLM>=1.83` behind a thin Protocol adapter. Optional extras (`[claude]`, `[openai-agents]`, `[otlp]`, `[judge]`, `[lint]`, `[bench]`) keep the install minimal and degrade gracefully if absent. Sync keyword surface with an internal `_run_async()` bridge — explicitly avoiding both RF 6.1+ experimental async and the `robotframework-async` third-party. Apache 2.0. CI matrix: Python 3.12 + 3.13 on Linux + macOS, with `tests/unit` always-on, `tests/integration` (`@pytest.mark.live`) on demand, and `tests/acceptance` `.robot` suites tagged `smoke / tier1 / tier3` for graduated CI cost. PyPI publish via `uv publish` with GitHub Actions OIDC trusted publishing.

## Vision

Become the **de facto standard** for agent evaluation in the Robot Framework community: the library a QA team reaches for the moment their org ships an AI feature, the reference cited in RoboCon talks and the Robot Framework forum, the library that proves keyword-driven testing is not just compatible with the AI-agent era but actively well-suited to it. Long-term, anchor a coherent `robotframework-agent*` portfolio (`agentguard` for safety, `agenteval` for quality, future siblings as the space matures) sharing the same DynamicCore skeleton and conventions — turning Robot Framework into the highest-leverage place for cross-functional teams (QA, compliance, ML) to gate AI agents before they ship.
