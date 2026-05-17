---
title: "Product Brief Distillate: robotframework-agenteval"
type: llm-distillate
source: "product-brief-robotframework-agenteval.md"
created: "2026-05-16"
purpose: "Token-efficient context for downstream PRD creation"
companion_artifacts:
  - "_bmad-output/planning-artifacts/product-brief-robotframework-agenteval.md"
  - "_bmad-output/planning-artifacts/research/technical-robot-framework-agent-evaluation-library-design-research-2026-05-15.md"
---

# Distillate: robotframework-agenteval

Dense, theme-grouped overflow context. Each bullet is standalone — assume the PRD workflow loads only this file, not the full brief or research doc.

## Product identity (one-line)

- Open-source Robot Framework library exposing AI-agent evaluation (MCP servers + Claude Code skills/sub-agents/hooks + multi-step LLM agents) as native RF keywords. Apache 2.0. PyPI. Maintainer: solo + AI-agent-assisted.

## Audience

- **Primary:** QA / test-automation engineers already using Robot Framework, typically in fintech / SaaS / healthcare / BFSI; declarative-syntax preference; being handed AI features to test without ML background.
- **Secondary:** compliance / audit / risk teams who consume eval evidence (output.xml + OTel traces) but don't write tests. Atmospheric only — not load-bearing for procurement; AI Act compliance happens at QMS level, not via tool selection.

## Hard technical decisions (locked, do not re-litigate in PRD)

- **Stack:** Python ≥3.12, `uv` + `hatchling`, `pyproject.toml`-only (PEP 621/735). Apache 2.0.
- **Pinned core deps:** `robotframework>=7.4,<9.0`, `robotframework-pythonlibcore` (DynamicCore), `robotframework-assertion-engine`, official `mcp` Python SDK (pinned `>=1.0,<2.0` due to spec churn), `LiteLLM>=1.83`, `pydantic`, `pyyaml`, `jsonschema`, `python-dotenv`, `opentelemetry-api/sdk`, `scipy`, `numpy`.
- **Optional extras:** `[claude]`, `[openai-agents]`, `[otlp]`, `[judge]`, `[lint]`, `[bench]` — lazy-load; missing extras degrade gracefully with clear ImportError.
- **Architectural skeleton:** lifted from sibling `robotframework-agentguard` — DynamicCore composition, `_assertions/` kernel, OTel listener entry point, provider Protocol, tiered keywords with polling ACL, stats module, `.env` config with credential redaction. Both projects are pre-1.0; this is shared internal pattern reuse, not battle-tested inheritance.
- **Module layout:** `src/AgentEval/{library.py, _assertions/, providers/, coding_agent/, telemetry/, mcp/, skills/, hooks/, subagents/, scenarios/, metrics/, stats/, judge/}` — bounded sub-libraries lazy-loaded.
- **Two separate Protocols:** `LLMProviderAdapter` (chat completions, default LiteLLM) and `CodingAgentAdapter` (full agent runs — Claude Agent SDK, OpenAI Agents SDK, Generic-via-LiteLLM). Provider-agnostic guarantee comes from the Generic adapter; unblocks Ollama/vLLM users on day one.
- **Async strategy:** sync keyword surface, internal `_run_async()` bridge using `asyncio.run()` with worker-thread fallback for nested loops. `nest_asyncio` opt-in only.
- **Listener:** OpenTelemetry GenAI semantic conventions adopted natively. Span hierarchy `invoke_agent → chat → execute_tool` with `gen_ai.*` attributes. RF Listener v3 registered via `[project.entry-points."robot.listener"]`, opt-in via `telemetry=True` library arg. Backends: memory (default) + JSONL file + OTLP exporter (Phase 2).
- **MCP transports:** stdio (default local), Streamable HTTP (recommended remote, supersedes deprecated SSE). In-memory transport for offline tests. SSE kept as legacy client only.
- **Three-tier keyword ACL:** Tier 1 = static (no API key, deterministic); Tier 2 = LLM-deterministic (temp=0, fixed seed); Tier 3 = agent-non-deterministic. ACL gates enforced in `_assertions/` kernel.
- **Polling ban on Tier 2/3:** raises `PollingDisallowedError` if `polling=` argument is passed. Hard rule, not a warning. Inherited from agentguard ADR-019.
- **AssertionEngine `validate` operator:** disabled by default (uses `eval()`, security risk). Opt-in via `__init__(allow_validate_operator=True)`. Inherited from agentguard ADR-013.
- **Config precedence:** library `__init__` args → environment vars (`AGENTEVAL_*` for library, LiteLLM-conventional `OPENAI_API_KEY` etc. for providers) → `.env` file → defaults. Defaults: `provider=litellm`, `telemetry=True`, `trace_backend=memory`, `allow_validate_operator=False`, `default_temperature=0.0`. Mandatory `config.redact_env()` pre-trace-write.
- **Test strategy (three tiers):**
  - `tests/unit` — Mock provider only, always-CI.
  - `tests/integration` — `@pytest.mark.live` with real LiteLLM/MCP, on-demand/nightly.
  - `tests/acceptance` — `.robot` suites tagged `smoke / tier1 / tier3`, smoke + tier1 always, tier3 nightly.
- **CI matrix:** Python 3.12 + 3.13 on Linux + macOS. PyPI publish via `uv publish` + GitHub Actions OIDC trusted publishing.

## Keyword shape conventions

- **Universal idiom:** every `Get X` keyword accepts `(assertion_operator, assertion_expected, message)` triple. Bare call → plain getter. With operator → inline assertion. Pattern proven in `robotframework-browser`. Replaces legacy `Should X` style.
- **Statistical primitives:** `Run N Times` (samples), `Pass At K` (HumanEval unbiased estimator: `1 - C(n-c, k) / C(n, k)`). Both accept AssertionEngine triple.
- **Metric vocabulary (locked):** `tool_calls`, `tool_call_count`, `hit_rate`, `success_rate`, `unnecessary_call_rate`, `trajectory`, `tokens`, `latency`, `edit_ratio`. Each maps 1:1 to a `Get X` keyword.

## Phase 1 MVP scope (in for v1.0, 6–8 weeks calendar at solo + AI-agent-assisted throughput)

- Top-level `AgentEval(DynamicCore)` library.
- `mcp/` keywords: Start/Connect/Stop MCP Server, List/Call MCP Tool, Get MCP Capabilities, Validate MCP Tool Schema.
- `skills/` + `hooks/` + `subagents/` static-inspection keywords (~6–8 each).
- `providers/` LiteLLM + Mock.
- `coding_agent/` Generic-only (LiteLLM-backed).
- `_assertions/` kernel with tier ACL gates and polling ban.
- `telemetry/` OTel listener + in-memory + JSONL backends.
- `metrics/` keywords for tool-call count/names/hit-rate/success-rate/trajectory/tokens/latency.
- `stats/` Run N Times + Pass At K.
- `scenarios/` YAML loader + `Run Scenario File`.
- Three example `.robot` suites, libdoc reference, README, "First agent eval in 5 minutes" walkthrough.
- Tutorials, recipe gallery (≥8 worked examples), CI cookbook (GitHub Actions, GitLab CI), "Coming from DeepEval / Promptfoo" migration mapping.
- First-day troubleshooting guide (Windows / corporate-env caveats).

## Phase 2 scope (4–6 weeks)

- `coding_agent/claude.py` — Claude Agent SDK subprocess JSON-lines bridge + in-process MCP.
- `coding_agent/openai_agents.py` — `Runner.run_streamed` + stream-event capture.
- `judge/` sub-library: rubric loader, `LLM Judge Score`, `LLM Judge Pairwise`, calibration cookbook.
- OTLP trace exporter.
- Advanced statistics: Mann-Whitney U, Cliff's δ, bootstrap CI.

## Phase 3 scope (TBD, deferred)

- LangGraph / CrewAI / AutoGen bridge adapters as separate `[bridges-*]` extras.
- HumanEval / SWE-bench fixture loaders.
- Sandboxing for Tier-3 agent-generated code (Docker / ephemeral worktree).
- BFCL trajectory match port from agentguard `tool_calls/`.

## Explicit non-goals (do not propose in PRD)

- **NOT a hosted observability platform.** No dashboards, no human-annotation UI, no regression-tracking SaaS. LangSmith / Braintrust / Phoenix own that surface. This library is strictly the CI/test-runner gating layer.
- **NOT original metric R&D.** Wraps established methodology (HumanEval Pass@k, BFCL trajectory match, OpenTelemetry GenAI semconv, wolfeidau/mcp-evals 5-dim rubric).
- **NOT a prompt-management harness.** Scope is agents (multi-step, tool-calling, MCP-using). Single-shot prompt A/B testing is Promptfoo's territory.
- **NOT for non-RF users.** No standalone CLI, no Python-script entry points. RF-only.

## Rejected alternatives (do not re-propose)

- **`Should X` keyword pattern** — legacy RF idiom; AssertionEngine getter+assertion replaces it.
- **`async def` keywords using RF 6.1+ experimental async support** — RF async still rough, complicates listener interactions (RF issue #4803).
- **Depending on `robotframework-async` third-party** — unclear maintenance; trivial `_run_async()` bridge sufficient.
- **Replace LiteLLM with native vendor SDKs** — LiteLLM is correct for library scope (140+ providers, native local-model). Protocol seam allows future swap without keyword changes.
- **Phase-0 design-partner gating with kill criteria** — explicitly chosen against in brief; recruit on PyPI signal instead, accept "build it and see" risk.
- **"Evidence Pack" first-class compliance product surface** — opportunity reviewer suggested it; user kept compliance positioning atmospheric. Don't promote in PRD.
- **Portfolio-first / dedicated portfolio section** — opportunity reviewer suggested it; user kept portfolio framing in Vision only. Don't elevate in PRD.

## Scenario YAML schema (synthesized from wolfeidau/mcp-evals + lastmile-ai/mcp-eval)

- **Top-level keys:** `model`, `provider`, `agent`, `temperature`, `seed`, `mcp_servers` (map of name → `command` + `args` + `transport` OR `url` + `transport`).
- **`evals` list,** each entry: `name`, `description`, `prompt`, `repeat`, plus an `expect` block with `tools_called`, `tool_call_count` (`>=`/`<=`), `tool_success_rate`, `content_contains`, `response_time_ms`, `pass_at_k` (`{k, predicate, threshold}`).
- **Optional `judge` block:** `dimensions` list (default 5: accuracy, completeness, relevance, clarity, reasoning), `rubric` with `must_have`, `pass_threshold` (default ≥3.0).

## Static-inspection file shapes

- **Skill/sub-agent `.md`:** YAML frontmatter (`name`, `description`, `disable-model-invocation`, `allowed-tools`).
- **Hooks:** under `settings.json` `hooks.<event>` (`PreToolUse`/`PostToolUse`/`Stop`) or inline in skill frontmatter.
- **MCP servers:** `.mcp.json` with `command`/`args`/`env`/`transport`. Live introspection via MCP `tools/list`.

## Risk register (severity / likelihood)

- **MCP spec churn** — High / Medium. Mitigation: pin `mcp>=1.0,<2.0`; track Tasks primitive proposal.
- **OTel GenAI semconv changes** — Medium / Low. Mitigation: internal facade, not direct attribute references throughout codebase.
- **LiteLLM breaking changes** — Medium / Medium. Mitigation: pin minor floor; Protocol isolation; fallback adapter on roadmap.
- **Robot Framework 8.x release** — Low / Medium. Mitigation: pin `>=7.4,<9.0`; track 8.x preview.
- **Claude Agent SDK plan/billing change June 15, 2026** — Low / Low. Mitigation: optional `[claude]` extra; not load-bearing for MVP.
- **Test flakiness from non-determinism** — High / Medium. Mitigation: `temp=0` default + `Pass At K` + polling ban.
- **Credential leakage in trace artifacts** — Medium / High. Mitigation: mandatory `redact_env()` + CI fixture check.
- **Async bridge nested-loop edge cases** — Medium / Low. Mitigation: worker-thread fallback.
- **Single-maintainer / bus-factor** — High / High. Mitigation stated in brief: contributor onboarding as first-class deliverable, paid-support / fork option for orgs needing SLA.
- **Competitive response (DeepEval / Promptfoo / Inspect AI ship RF binding)** — Medium / Medium. Mitigation: structural defensibility via depth of RF idiom (listener integration, libdoc, AssertionEngine), not first-mover claim.

## Untested assumptions (PRD should design validation for these)

- QA engineers want to write agent evals in `.robot` syntax themselves rather than handing the work to a Python team. Risk: AI testing may organizationally route to ML/platform engineers regardless of QA's tooling.
- 5-min time-to-first-test is achievable on the defined cohort. Risk: Windows / corporate envs likely 20–60 min; first-touch failure is unrecoverable.
- Polling ban + Pass@k is a feature, not friction users route around. Risk: users from flaky-test cultures may experience `PollingDisallowedError` as obstacle and fork.
- 6–8 week MVP at solo + AI-agent-assisted throughput is realistic. Risk: stated +50% slip buffer; PRD should define re-baseline triggers.
- "De facto standard" addressable market is meaningful. Risk: RF QA-using population may be small; PRD should size with PyPI install stats of `robotframework`, `robotframework-browser`, RoboCon attendance.

## Competitive intelligence (preserve for PRD positioning)

- **Direct MCP-eval frameworks (none target RF):** lastmile-ai/mcp-eval (Python, namespaced `Expect.*` DSL, OTel, LLM-judge), wolfeidau/mcp-evals (Go, YAML scenarios, 5-dim 1–5 rubric, ≥3.0 pass), @mcp-testing/server-tester (TS, Playwright fixtures), DeepEval MCP (Python), MCPBench (Python benchmark corpus).
- **Adjacent eval frameworks:** DeepEval ("pytest for LLMs", 50+ metrics, Python-only), Ragas (RAG-focused), LangSmith / LangChain Evals (hosted SaaS, vendor lock-in to LangChain stack), Promptfoo (CLI+YAML), Inspect AI (UK AI Safety Institute Python SDK), Braintrust (managed platform), TruLens, OpenAI Evals, Phoenix/Arize, MLflow LLM evaluate, Patronus AI.
- **Existing RF AI namespace (crowded but orthogonal):** `robotframework-aiagent`, `robotframework-roboai`, `robotframework-ai`, `rf-mcp` — these all let `.robot` files USE LLMs in tests. None provide structured EVALUATION of AI agents. Differentiation must be unambiguous.
- **Demand signals (May 2026):** OpenAI publishes MCP eval cookbook; five MCP-eval frameworks emerged in <12 months; LiteLLM at ~40k stars with 140+ providers; 57% of orgs have LLM agents in production.
- **EU AI Act timing:** high-risk obligations (Art. 9, 11, 12, 19, 26) enforceable Aug 2, 2026. Continuous-evaluation + 6-month log retention requirements. Code of Practice draft finalizing June 2026. Real category tailwind, but tool-selection-neutral: AI Act is satisfied at QMS / governance level.
- **QA pain-point quotes:** non-determinism "breaks the entire premise of assertion-based testing"; 3-word system-prompt change shifts behavior across thousands of unanticipated scenarios; Google reports ~16% of tests show flakiness, Microsoft tracks 49k flaky tests; QA teams report being asked to own AI features without ML background.

## Documentation, DX & support deliverables (v1.0 day-one)

- README with quick-start, library overview, link to walkthrough.
- libdoc reference (auto-generated, RF-native).
- "First agent eval in 5 minutes" walkthrough — timed and published, regressed in CI.
- Recipe gallery (≥8 examples): MCP tool assertions, trajectory checks, judge scoring, scenario YAML, statistical assertions, static inspection of each artifact type.
- CI integration cookbook (GitHub Actions, GitLab CI examples).
- "Coming from DeepEval / Promptfoo" migration mapping.
- First-day troubleshooting guide: Windows/corporate caveats, `uv` alternatives (pip, pipx), PyPI proxy/cert workarounds, MCP-server bring-up failures, common `.env` mistakes.
- Error-message UX standard: `PollingDisallowedError` ships with copy-pasteable `Run N Times` + `Pass At K` snippet inline; AssertionEngine failures wrapped with library-specific context.
- `CONTRIBUTING.md`, "good first issue" labels, agent* portfolio shared-pattern docs.
- Public roadmap, semver discipline, issue-triage SLA (best-effort 5 business days; security prioritized).
- Honest bus-factor posture in maintenance docs.

## Success metrics summary (decision-implicating, not vanity)

- **Phase 1 outcome:** 5-min time-to-first-test achieved on published cohort + test-tier reliability (unit ≥99%, smoke 100%, live-nightly ≥95%) + full MCP primitive coverage + static-inspection coverage of skills/hooks/sub-agents/.mcp.json.
- **Phase 2 capability:** ≥3 agent runtimes via `CodingAgentAdapter` + ≥6 LLM provider backends via LiteLLM + judge sub-library + OTLP exporter.
- **Month 6 adoption:** ≥500 unique installers/month + ≥3 inbound GitHub issues from non-author users + ≥1 RoboCon 2027 talk submitted + ≥1 community blog/forum thread. Two-of-four miss → DX/positioning retrospective before Phase 2.
- **Month 12 adoption:** ≥2,000 unique installers/month + ≥5 public GitHub dependents + ≥1 RoboCon 2027 talk accepted + ≥1 inbound community PR landed. Majority miss → reframe vision from "de facto standard" to "niche-but-deep".

## Open questions for PRD

- Concrete Phase-1 cut-list if 6–8 week target slips (which features defer to Phase 1.5 hardening sprint?).
- Scenario YAML schema versioning strategy and schema-validation error UX.
- LLM-judge calibration methodology (Phase 2) — what cookbook delivers, what it does not promise.
- Telemetry opt-in: any anonymous usage signal (install count by Python/OS, keyword popularity) the library could collect to inform User-outcome bars, or strictly off-by-default forever?
- Versioning compatibility commitments across RF 7.4–8.x window.
- Decision on whether to vendor a tiny LiteLLM fallback wrapper for MVP if LiteLLM availability degrades.
