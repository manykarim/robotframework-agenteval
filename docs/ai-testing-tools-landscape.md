# Testing Tools & Frameworks for LLMs, Agents & the Agentic Ecosystem

A landscape summary of tools and frameworks for testing **LLMs, Agents, Coding Agents, Agent Skills, MCP Servers, Hooks, and SubAgents**.

> ⭐ Star counts fetched live from GitHub on **2026-07-08**.

---

## 1. LLM Evaluation (Model / Output Level)

| Name | Description | URL | Key Features | ⭐ Stars |
|---|---|---|---|---|
| **DeepEval** | Pytest-style open-source LLM evaluation framework ("unit tests for LLMs") | https://github.com/confident-ai/deepeval | 40+ metrics (G-Eval, hallucination, faithfulness), agent trajectory metrics (tool correctness, plan adherence, task completion), pytest CI/CD integration, auto-instrumentation for Pydantic AI / LangChain / LlamaIndex, span-level component evals | 16,717 |
| **RAGAS** | Reference-free evaluation framework for RAG pipelines | https://github.com/explodinggradients/ragas | Faithfulness, context precision/recall, answer relevance; agent metrics (Tool Call Accuracy/F1, goal accuracy); reference-based & reference-free modes; synthetic test-set generation | 14,721 |
| **LM Evaluation Harness** | EleutherAI's standard harness for offline benchmark testing of foundation models | https://github.com/EleutherAI/lm-evaluation-harness | 60+ academic benchmarks (MMLU, HellaSwag, TruthfulQA, HumanEval), model comparison pre-selection, post-fine-tuning regression checks | 13,214 |
| **Promptfoo** | Declarative (YAML) prompt testing, regression testing & red teaming | https://github.com/promptfoo/promptfoo | Side-by-side prompt/model comparison, assertions, CI/CD gates, red-team plugin library, local & provider-agnostic | 23,034 |
| **TruLens** | Instrumentation + feedback-function based evaluation for LLM apps | https://github.com/truera/trulens | Feedback functions (groundedness, relevance), RAG triad evaluation, tracing, comparison dashboards | 3,431 |
| **Langfuse** | Open-source (self-hostable) LLM engineering platform: tracing, evals, prompt management | https://github.com/langfuse/langfuse | OTel-based tracing, LLM-as-judge & custom evals, datasets, prompt management, agent-eval cookbooks (incl. Pydantic AI + MCP), self-hosting | 30,697 |
| **Arize Phoenix** | Open-source AI observability & evaluation (tracing-first) | https://github.com/Arize-ai/phoenix | Detailed trace debugging for RAG/agents, LLM-judge evals of full tool-calling sequences, OTel-native, experiments & datasets | 10,455 |
| **MLflow (3.x)** | ML/GenAI lifecycle platform with LLM & agent evaluation | https://github.com/mlflow/mlflow | Built-in judges (safety, correctness, relevance, groundedness), custom judges, trajectory-based scorers, trace capture, framework-agnostic (LangGraph, CrewAI, ADK, Pydantic AI) | 26,929 |
| **LangSmith** | Commercial eval + observability platform (LangChain ecosystem) | https://smith.langchain.com *(closed source)* | Human/heuristic/LLM-judge/pairwise evaluators, trajectory evaluation, annotation queues, online & offline evals, OTel ingestion | – |
| **Braintrust** | Commercial eval platform with human-in-the-loop workflows | https://www.braintrust.dev *(closed source)* | Custom scorers, dataset management, HITL review, CI integration | – |

---

## 2. Agent Evaluation (Trajectory Level)

| Name | Description | URL | Key Features | ⭐ Stars |
|---|---|---|---|---|
| **Pydantic Evals** | Code-first eval framework from the Pydantic team (part of pydantic-ai repo) | https://github.com/pydantic/pydantic-ai | Case/Dataset/Evaluator/Experiment model (pytest-like), deterministic + LLM-judge evaluators, **span-based evaluation of tool calls & execution flow via OpenTelemetry**, Logfire integration, CI deploy gates | 18,274 |
| **Scenario (LangWatch)** | Simulation-based agent testing: simulated users drive multi-turn conversations | https://github.com/langwatch/scenario | Framework-agnostic (one `call()` adapter), no datasets required, judge at any conversation turn, scripted simulations, adapters for Pydantic AI / LangGraph / CrewAI | 913 |
| **AgentEvals (LangChain)** | Trajectory evaluators for agents | https://github.com/langchain-ai/agentevals | Final-response grading, trajectory match vs. reference workflows, LLM-judge trajectory scoring, component-level testing | 639 |
| **MLflow Agent Evaluation** | Trajectory scorers + tracing (see above) | https://github.com/mlflow/mlflow | Full execution-graph capture, tool-choice/argument validation, error-recovery assessment | 26,929 |
| **Langfuse Agent Evals** | Agent evaluation on top of Langfuse tracing (see above) | https://github.com/langfuse/langfuse | Trajectory, single-step and final-output evaluation patterns; Pydantic AI + MCP agent cookbook | 30,697 |
| **Galileo** | Commercial agent evaluation & runtime protection platform | https://galileo.ai *(closed source)* | Agent GPA scorers (tool selection, plan quality, logical consistency, execution efficiency), observability + runtime guardrails | – |

**Common metric layers:** final output → trajectory (tool choice, arguments, step order, reasoning) → system (tokens, latency, cost, failure recovery).

---

## 3. Coding Agent Benchmarks & Harnesses

| Name | Description | URL | Key Features | ⭐ Stars |
|---|---|---|---|---|
| **SWE-bench** | De-facto standard benchmark: resolving real GitHub issues | https://github.com/SWE-bench/SWE-bench | 5 variants (original, Verified, Pro, Multilingual, Live), containerized test execution, patch-based scoring. ⚠️ Known contamination & flawed-test issues at frontier level | 5,371 |
| **Terminal-Bench (2.x)** | Stanford benchmark for terminal/CLI agents in Docker sandboxes | https://github.com/laude-institute/terminal-bench | 16 task categories (SWE, security, data science, debugging…), difficulty tiers, reference scaffold (Terminus-2), harness-sensitivity well documented | 2,427 |
| **SWE-agent** | Reference agent scaffold for SWE-bench-style issue resolution | https://github.com/SWE-agent/SWE-agent | Agent-computer interface design, mini-swe-agent variant, widely used baseline harness | 19,734 |
| **OpenHands** | Open-source production coding-agent platform (also used as eval harness) | https://github.com/All-Hands-AI/OpenHands | Full dev-environment agent (browser, terminal, editor), common baseline in papers | 79,971 |
| **Aider (Polyglot benchmark)** | CLI pair-programming tool with multi-language editing benchmark | https://github.com/Aider-AI/aider | Polyglot benchmark suite (many languages), edit-format success metrics, leaderboard | 47,182 |
| **LiveCodeBench** | Contamination-resistant coding benchmark | https://github.com/LiveCodeBench/LiveCodeBench | Continuously harvests fresh LeetCode/AtCoder/CodeForces problems after training cutoffs, date-annotated problems | 904 |
| **OSWorld** | Benchmark for GUI/desktop computer-use agents | https://github.com/xlang-ai/OSWorld | 369 tasks on real Linux/Windows/macOS desktops, environment-state-based scoring | 3,000 |

**Key caveat:** harness/scaffold effects cause 7–20 pp score differences on identical models — always build a domain-specific suite (100–200 tasks) instead of trusting leaderboards.

---

## 4. Agent Skills Testing

| Name | Description | URL | Key Features | ⭐ Stars |
|---|---|---|---|---|
| **skill-creator (Anthropic Skills repo)** | Official skill authoring + eval tooling for Claude Agent Skills | https://github.com/anthropics/skills | Evals in `evals/evals.json` (prompt, expected output, input files), subagent-per-test isolation, grading with evidence (`grading.json`), benchmark mode (pass rate, tokens, time), blind A/B comparator agents (skill vs. skill / skill vs. no-skill), trigger-tuning analysis, HTML review viewer, CI-pluggable | 159,383 |
| **agentskills.io eval guide** | Eval file format & iteration workflow documentation | https://agentskills.io/skill-creation/evaluating-skills | Clean-context runs, iteration workspaces, baseline (no-skill) comparison methodology | – |

**Distinct test dimensions:** output quality (evals), regression after model updates (benchmark mode), skill obsolescence (base model passes without skill), and **trigger precision** (false-positive/negative activation).

---

## 5. MCP Server & Tool Testing

### Protocol / Functional Level

| Name | Description | URL | Key Features | ⭐ Stars |
|---|---|---|---|---|
| **MCP Inspector** | Official interactive dev tool for testing/debugging MCP servers | https://github.com/modelcontextprotocol/inspector | React UI + protocol proxy, stdio/SSE/streamable-http, tool/resource/prompt invocation, protocol validation, JSON-RPC logs, auth flows. Dev-loop tool — no CI/team features | 10,308 |
| **MCPJam Inspector** | Testing & evaluation platform for MCP servers, MCP apps & ChatGPT apps | https://github.com/MCPJam/inspector | All Inspector features **plus**: SDK for programmatic assertions, CLI for CI (GitHub Actions), LLM-driven evals with expected tool calls across multiple models, accuracy tracking over time, OAuth checks, spec conformance, multi-server chat, trace view, team workspaces | 2,053 |
| **FastMCP** | Python MCP framework with built-in testing support | https://github.com/jlowin/fastmcp | In-memory client for pytest (no subprocess), typed tool definitions, ideal base for the unit-test layer of a 3-layer test pyramid (unit → integration → evals) | 26,038 |

### Benchmark Level

| Name | Description | URL | Key Features | ⭐ Stars |
|---|---|---|---|---|
| **MCPMark** | Stress-testing benchmark in real MCP environments (EVAL SYS / LobeHub / NUS) | https://github.com/eval-sys/mcpmark | Notion/GitHub/Filesystem/Postgres/Playwright environments, version-pinned "Verified" task set, isolated sandboxes, auto-resume, unified metrics | 438 |
| **MCP-Bench** | Accenture benchmark: LLM agents on 28 live MCP servers / 250 tools | https://github.com/Accenture/mcp-bench | Fuzzy-instruction tool retrieval, multi-hop trajectory planning, cross-server orchestration, rule-based + rubric LLM-judge scoring | 493 |
| **MCPEval** | Salesforce: auto-generating evaluation queries per MCP server | https://github.com/SalesforceAIResearch/MCPEval | Automated query generation, fine-grained server performance assessment | 154 |
| **LiveMCPBench** | Large-scale MCP toolset benchmark ("ocean of tools") | https://github.com/icip-cas/LiveMCPBench | Tests agent tool-navigation in large, dynamic MCP ecosystems (beyond ~10-server setups) | 103 |

---

## 6. Hooks Testing

No dedicated framework exists — hooks are deterministic scripts, so classical testing applies:

| Approach | Description | Tooling |
|---|---|---|
| **Unit tests** | Feed synthetic JSON hook-event payloads on stdin; assert on exit codes and stdout (block/allow decisions) | pytest, bats |
| **Integration tests** | Run Claude Code headless (`claude -p`) in CI with prompts known to trigger the hook event; assert on transcript/side effects | Claude Code CLI + CI |
| **Negative/guard tests** | Attempt a forbidden action (e.g. SQL write past a PreToolUse guard) and assert it's blocked | pytest + hook scripts |

> 💡 **Gap/opportunity:** an RF library firing synthetic hook events and asserting on decisions (fit for `robotframework-agenteval`) would be novel in this space.

---

## 7. SubAgent Testing

Also convention-driven rather than tool-driven:

| Approach | Description | Tooling |
|---|---|---|
| **Isolation as primitive** | Each subagent invocation is hermetic (clean context) — natural test boundary; skill-creator already uses subagents *as* parallel eval runners | skill-creator, Claude Code |
| **Delegation-routing tests** | Does the orchestrator delegate to the right subagent for a prompt? Headless runs asserting Task-tool invocations | Claude Code headless + assertions |
| **Config-drift checks** | Subagents do **not** inherit parent skills — verify explicit `skills:` preloading in frontmatter | lint/CI check |
| **Span-based scoring** | Subagent calls appear as child spans → per-subagent metrics via trace evaluation | Pydantic Evals (OTel), DeepEval (`next_*_span`), MLflow, Langfuse |

### Adversarial / Red Teaming (agents & multi-agent)

| Name | Description | URL | Key Features | ⭐ Stars |
|---|---|---|---|---|
| **DeepTeam** | Red-teaming framework for LLMs & agents (built on DeepEval) | https://github.com/confident-ai/deepteam | 50+ vulnerabilities (OWASP Top 10, NIST AI RMF), 20+ attack methods (jailbreaks, prompt injection, encoding obfuscation), single- & multi-turn, local LLM-judge pass/fail scoring, no dataset needed | 2,106 |
| **PyRIT** | Microsoft's Python Risk Identification Toolkit for GenAI | https://github.com/Azure/PyRIT | Multi-turn attack strategies (Crescendo, TAP, Skeleton Key), multimodal (text/audio/image/video), orchestrator architecture | 77 ⚠️* |
| **garak** | NVIDIA's LLM vulnerability scanner | https://github.com/NVIDIA/garak | Probe library (jailbreaks, leakage, toxicity, encoding attacks), plugin architecture, report generation | 8,364 |
| **Inspect AI** | UK AI Safety Institute's evaluation framework | https://github.com/UKGovernmentBEIS/inspect_ai | Composable solvers/scorers, sandboxed tool use, agent evals, widely used for safety evaluations | 2,314 |

\* *Azure/PyRIT star count as reported by GitHub on 2026-07-08 — unusually low, possibly a repo migration/reset artifact; verify before citing.*

---

## Quick-Reference: Mapping to the Agentic QA Orchestrator Stack

| Layer | Recommended primary tool | Why |
|---|---|---|
| Agent execution evals (Slice 1) | **Pydantic Evals + Logfire** | Already on Pydantic AI 2.0; span-based evals align with production OTel traces; pytest/CI-native |
| rf-mcp regression gate | **MCPJam Inspector (CLI/SDK)** + FastMCP in-memory pytest | Protocol conformance + tool-selection evals per PR; tests what MCP Inspector can't (does the model pick the right tool?) |
| Escalation/HITL flows | **Scenario (LangWatch)** | Simulated multi-turn users exercise Delegation/Supervision/Escalation incl. `ApprovalRequired` paths |
| Trajectory metrics | **DeepEval** (Pydantic AI auto-instrumentation) | Tool correctness, plan adherence, task completion as CI assertions |
| Safety/robustness | **DeepTeam** (+ garak/PyRIT for depth) | Prompt-injection & multi-turn adversarial sims against agents |
| Hooks & SubAgents | **Custom (pytest/bats + headless runs)** | No established framework — white space for robotframework-agenteval |
