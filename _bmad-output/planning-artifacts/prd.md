---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
status: complete
releaseMode: phased
classification:
  projectType: developer_tool
  domain: general
  subdomain: ai_agent_quality_engineering
  complexity: high
  complexityNote: "focused — at integration boundary (MCP/OTel/coding-agent SDKs/async bridge), not the core; template treated as menu not checklist"
  projectContext: greenfield
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-robotframework-agenteval.md
  - _bmad-output/planning-artifacts/product-brief-robotframework-agenteval-distillate.md
  - _bmad-output/planning-artifacts/research/technical-robot-framework-agent-evaluation-library-design-research-2026-05-15.md
documentCounts:
  briefs: 2
  research: 1
  brainstorming: 0
  projectDocs: 0
workflowType: prd
projectType: greenfield
project_name: robotframework-agenteval
user_name: Many
date: 2026-05-16
userProvidedContext:
  - source: "user input @ step-01"
    type: "user story"
    persona: "Agent Skill writer"
    text: |
      As an Agent Skill writer, I want to evaluate if my skill is triggered by a prompt
      in a reliable way to ensure the given task is solved using the provided information
      and scripts.
    notes: |
      Introduces a persona not explicitly named in the brief (skill authors evaluating
      their own skills, distinct from QA engineers evaluating someone else's agents).
      Exercises all three tiers in one flow: Tier-1 (validate skill frontmatter +
      allowed-tools), Tier-3 (Pass@k over varied prompts to assert skill is invoked),
      Tier-2 (LLM-judge: did the skill use the provided info/scripts correctly?).
      Surface during Personas + Requirements steps.

  - source: "user input @ step-02 party-mode"
    type: "product focus statement"
    text: |
      Focus of product shall be that QA Engineers, Agent Skills Developers, MCP Developers,
      Agent Developers can start testing their products easily to ensure they deliver a
      good quality. The test methods and keywords shall be simple enough for usage and
      validation. Too complex benchmarks that cannot be checked cleanly do not help.
      Focus of the product is to be agent agnostic and simplicity. But still powerful and
      thorough test of proper end2end agentic workflows and validation of collected metrics.
    notes: |
      EXPANDS audience from brief's primary-only (QA engineers) to FOUR developer personas.
      Establishes load-bearing tension: simplicity-for-everyday-usage AND
      validation-legibility AND powerful E2E agentic-workflow testing.
      Party-mode example personas surfaced by Sally: Priya (QA), Devon (Skill dev),
      Mei (MCP dev), Raj (Agent dev). Carry into Personas step verbatim if useful.

  - source: "party-mode roundtable @ step-02"
    type: "design principle"
    text: |
      DESIGN PRINCIPLE (Sally + Amelia convergence):
      Simplicity != feature poverty. Simplicity = legibility of pass/fail.
      Every keyword must be debuggable by the persona who wrote it. If a failure
      requires understanding the eval engine, the keyword is too clever and must be
      split or downgraded.
    notes: |
      Promote to load-bearing product principle in the PRD. Drives the AC below
      and the Tier-2 trap call-out.

  - source: "party-mode roundtable @ step-02 (Amelia)"
    type: "acceptance criterion (verbatim)"
    id: "AC-SIMPLICITY-01"
    text: |
      Every assertion keyword in the core library MUST, on both pass and fail, write to
      the Robot Framework log a self-contained evidence block containing (a) the exact
      threshold compared, (b) the observed value, (c) the raw agent artifact (response,
      trajectory, or tool-call trace) that produced it, such that a reviewer can determine
      pass/fail correctness without re-running the test or consulting external dashboards.

  - source: "party-mode roundtable @ step-02 (Sally)"
    type: "scope clarification"
    label: "Tier-2 trap"
    text: |
      Tier-2 (LLM-deterministic) is the REAL simplicity breaking point — not Tier-3.
      Tier-3 advertises its non-determinism honestly; Tier-2 hides it (semantic-equivalence
      keywords that secretly run a judge LLM with a threshold + seed + rubric).
      Implication: Tier-2 keywords need STRONGER legibility requirements than Tier-3,
      reversing the brief's implicit framing.

  - source: "party-mode roundtable @ step-02 (Amelia)"
    type: "scope rule"
    label: "10-keyword core lid"
    text: |
      Core API surface fits in <=10 keywords. Proposed core set (memorize-or-fail bar):
        1. Connect Agent (adapter-agnostic: MCP URL | Claude skill path | CLI cmd | HTTP)
        2. Send Prompt
        3. Run Scenario    ${yaml}
        4. Agent Response Should Contain
        5. Agent Response Should Match Schema
        6. Tool Call Should Have Occurred    ${tool_name}
        7. Trajectory Should Match    ${expected_steps}
        8. Latency Should Be Below    ${ms}
        9. Cost Should Be Below    ${usd}
        10. Evaluate With Judge    ${rubric}    min_score=${n}
      Pass@k stays in core (single keyword, well-understood). Mann-Whitney U, Cliff's δ,
      bootstrap CI, BFCL trajectory port, judge-calibration cookbook all move to an
      opt-in `agenteval-advanced` extras group (or sub-library).

  - source: "user input @ step-02 (resolves Amelia-vs-Winston disagreement)"
    type: "design decision"
    label: "Lazy-load all keywords + short sub-library namespace prefixes"
    text: |
      All keywords lazy-loaded (Winston pattern, borrowed from agentguard, evaluated on merit). BUT make the
      sub-library names short and clear so users can write namespaced keywords
      directly via AssertionEngine in their .robot files:

        Skill.Get Description    *=    Test Skill
        MCP.Get Tools            *=    Find Locator

      The `*=` is AssertionEngine's glob/wildcard match (one of several inline
      assertion operators). Namespace prefixes (Skill., MCP., Hook., Subagent.,
      Scenario., Metric., Stat., Judge.) become the discoverability mechanism —
      users find keywords via prefix, not via flat surface or autocomplete pressure.
    notes: |
      Resolves the round-2 disagreement: Amelia wanted ≤10 flat keywords; Winston
      wanted lazy-loaded sub-libraries. Many's resolution honors both — lazy-loaded
      sub-libraries with SHORT prefix names so the user-facing surface is still
      discoverable. PRD constraint: every sub-library prefix must be ≤8 chars and
      pronounceable. The 10-keyword "core" Amelia proposed becomes "the core that
      every persona learns first," not "the total surface" — surface is unbounded
      but discoverable by namespace.

  - source: "user input @ step-02"
    type: "user story + new product capability"
    persona: "MCP Developer"
    text: |
      As an MCP Developer I want to know if different coding agents and LLMs can
      even find my tools, when giving them a task — so that I can validate whether
      my tool docstrings and MCP server instructions are clear enough for real-world
      agent use.
    notes: |
      NEW PRODUCT CAPABILITY not in brief or distillate: **Tool Discoverability /
      Findability evaluation**. Different from tool *correctness* (does the tool
      work) — this is tool *findability* (does the LLM/agent select it given a
      natural-language task).
      Implementation shape (Tier 3 / agent-non-deterministic): run real agents +
      multiple models against a set of tasks, observe whether the target tool is
      called, report success rate per (model × task) cell. Statistical via Pass@k.
      Depends on: tool name, docstring quality, parameter schema descriptions,
      MCP server instructions text.
      Proposed keyword shape (illustrative, not locked):
        MCP.Tool Should Be Discoverable    tool=search_db    by_models=claude,gpt-4
                                           with_tasks=${task_list}    pass_at_k=0.8
      This belongs in Phase 1 (it's a core MCP-developer story) and reinforces
      the agent-agnosticism principle — must work across ≥2 coding-agent runtimes
      to be meaningful.

  - source: "party-mode roundtable @ step-02 (Sally)"
    type: "product tagline / framing"
    label: "Tool Discoverability tagline"
    text: |
      "Debugging discoverability is debugging vocabulary."
      The Tool Discoverability keyword exists to teach MCP developers that when
      agents don't pick their tools, the bug is in the WORDS (docstring, tool name,
      parameter descriptions, server instructions) — not in the tool's implementation.
      Surface in docs as the user-facing tagline for this keyword.

  - source: "party-mode roundtable @ step-02 (Amelia)"
    type: "acceptance criterion (verbatim)"
    id: "AC-DISCOVER-01"
    text: |
      MCP.Tool Should Be Discoverable MUST emit a single self-contained evidence
      block containing: tool name, pass@k vs threshold, per-model cohort table with
      Wilson CI, per-task verdict matrix, failed-task prompts with agent's alternative
      tool picks and docstring-under-test snippet, comparator delta if set, and
      reproducibility footer (model versions, server sha, task_list hash, seed) —
      sufficient for an MCP developer to identify the failing docstring without
      consulting external logs.

  - source: "party-mode roundtable @ step-02 (Sally + Amelia + Orchestrator resolution)"
    type: "design rule"
    label: "Discoverability output legibility"
    text: |
      stdout headline of MCP.Tool Should Be Discoverable shows the cohort heatmap
      WITHOUT confidence intervals (Sally's call: CI's wide-noisy on N=10 trials
      distract more than inform). Wilson CI lives in the JSON artifact and surfaces
      in --verbose / debug mode. Headline = "who failed what"; the math depth is
      one click away for the statistically curious.

  - source: "party-mode roundtable @ step-02 (Amelia)"
    type: "scope (Phase 1 / Phase 2)"
    label: "Tool Discoverability Phase 1 strip"
    text: |
      Phase 1 MVP for Tool Discoverability:
        - ≤2 models in by_models (defaults: claude-sonnet, gpt-4o-mini)
        - User-supplied task_list ONLY (no auto-task generation)
        - Aggregation: pass@k + Wilson CI (no SciPy dependency added for this)
        - Single comparator (compare_to=<one tool>)
        - Parallelism: asyncio.gather only (no Ray/Dask)
        - Output: stdout + JSON artifact (no HTML report)
      Cut to Phase 2:
        - Auto-task generation from docstrings
        - Multi-model statistical significance (Mann-Whitney already Phase 2)
        - Docstring A/B side-by-side rendering
        - Judge-model calibration for "did it actually USE the tool correctly"
      Cut entirely (explicit non-goal):
        - LLM-generated docstring auto-rewrites — crosses from EVALUATION into
          AUTHORING; different product, different trust model (Sally's framing)

  - source: "advanced-elicitation pre-mortem @ step-02"
    type: "blind spot / action item"
    label: "Persona inflation correction"
    text: |
      The "four developer personas" framing is likely 2.5 people in disguise:
      Agent Skill Developer + Agent Developer = same engineer testing different
      artifacts on different days; MCP Developer is also an Agent Developer
      wearing a server hat. Honest count: QA Engineer (evaluates other people's
      agents) + Agent Developer (builds + evaluates own agents, three modes:
      Skill / MCP / Multi-step Agent).
    notes: |
      In the Personas step, collapse to TWO primary personas. Carry the three
      "modes" (Skill / MCP / Agent) as scenarios under the Agent Developer
      persona, not as separate personas with parallel epics. Prevents
      duplicated stories, fragmented examples, 4× golden-path maintenance.

  - source: "advanced-elicitation pre-mortem @ step-02"
    type: "blind spot / risk register addition"
    label: "AI-agent productivity is near-zero on RF/MCP/OTel-internal surfaces"
    text: |
      Solo + AI-agent-assisted timeline assumes coding-agent productivity
      compounds. But Robot Framework + MCP Python SDK + OTel GenAI semconv +
      RF Listener v3 + AssertionEngine + agent-eval-framework internal patterns are
      ALL under-represented in coding-agent training data. AI agents will be
      slowest exactly where this library lives. The 6–8 week MVP target is
      most at risk on the surfaces (async bridge, listener wiring, OTel
      custom attributes, AssertionEngine adapter) being banked on for AI
      acceleration.
    notes: |
      Add to PRD Risk register with severity High / likelihood High.
      State explicitly in timeline rationale that AI productivity is ASSUMED
      NEAR-ZERO on these surfaces; re-baseline weekly. The honest 6–8 weeks
      becomes 6–8 weeks for AI-friendly surfaces (docs, scenario YAML, test
      fixtures) + person-time-dominated weeks for AI-unfriendly surfaces.

  - source: "advanced-elicitation pre-mortem @ step-02"
    type: "limitation / known-issue documentation requirement"
    label: "Tool Discoverability vocabulary asymmetry"
    text: |
      The "debugging discoverability is debugging vocabulary" tagline cuts
      both ways. For domain-specific jargon (medical, legal, industrial),
      the bug may be in the AGENT'S TRAINING DATA, not the docstring. Tool
      Discoverability risks teaching users to dumb their domain vocabulary
      down to match what coding agents already know — wrong lesson for
      specialized industries.
    notes: |
      MCP.Tool Should Be Discoverable docs MUST surface this asymmetry as a
      known limitation. Failure-evidence block should hint when the missed
      task vocabulary is itself domain-rare ("competing tools picked were
      all common DB verbs; your jargon may be outside training data").
      Don't ship as if vocabulary fixes are universal.

  - source: "advanced-elicitation red-team @ step-02"
    type: "moat-defensibility finding"
    label: "Editorial taste is the moat, not the code"
    text: |
      If a competitor (DeepEval / Promptfoo / Inspect AI) ships an RF binding
      tomorrow, copyable in a weekend: AC-DISCOVER-01, AC-DISCOVER-02, the
      10-keyword lid, namespace prefixes, the cost guardrail. The ONLY real
      moat among captured ACs is AC-SIMPLICITY-01 (evidence-block legibility)
      because it's an EDITORIAL commitment, not a feature. The fork can copy
      the code; it can't copy the discipline.
    notes: |
      Action: write the ADRs and docs FIRST, before the code. Editorial
      taste compounds into trust; code compounds into dependencies. The PRD
      should explicitly fund doc + ADR time as P1 deliverables, not
      "after MVP" polish.

  - source: "advanced-elicitation first-principles @ step-02"
    type: "process correction"
    label: "Classification is inert metadata, not a template driver"
    text: |
      developer_tool / general / high + 8 scaffolding overrides + 7 captured
      product principles + 4 ACs = we invented a custom category 3 rounds ago.
      The classification ceased to drive PRD section selection; it's now
      UTM-tag metadata for downstream tooling that may not exist.
    notes: |
      Stop optimizing classification. Treat it as inert annotation. The REAL
      PRD scaffold is the override block + captured user-provided context
      already in this frontmatter. Drive steps 2b through 11 from THIS
      content, not from CSV-derived section names.

  - source: "advanced-elicitation pre-mortem (bonus) @ step-02"
    type: "Phase 1 acceptance criterion + reference targets"
    id: "AC-DOGFOOD-01"
    text: |
      The library MUST be capable of replacing the existing custom end-to-end
      tests in Many's two reference projects by end of Phase 1:
        - https://github.com/manykarim/rf-mcp                (MCP server project)
        - https://github.com/manykarim/robotframework-agentskills  (Agent skills project)
      Both projects today contain custom end-to-end tests that collect agent
      metrics and perform non-deterministic evaluations. Phase 1 success
      means a .robot suite using robotframework-agenteval can subsume those
      custom tests at parity or better — same assertions, same metrics, same
      determinism guarantees, less custom code.
    notes: |
      These are not hypothetical dogfood targets — they are concrete, existing
      projects with existing custom test code that proves both (a) latent
      demand and (b) a falsifiable scope bar. Goes far beyond a generic
      "eat your own dog food" line.
      Use these repos as:
        - Phase 1 scope ground-truth: every metric / assertion the custom
          tests perform MUST have a library equivalent before MVP ships.
        - Real-world reference scenarios for the brief's "first 5 minutes"
          walkthrough and the recipe gallery.
        - Free design-partner feedback loop (Many uses agenteval to test his
          own libraries; bugs surface naturally).
        - PRD Requirements step: cross-reference the EXISTING tests in these
          repos to drive functional requirements rather than inventing from
          first principles. Reduces scope-creep risk.
      Cross-reference these repos during PRD Step 4+ (Functional Requirements
      and Scope). WebFetch / clone them when generating FRs to ensure parity.

  - source: "party-mode roundtable @ step-04 (Amelia + Many resolution)"
    type: "acceptance criterion (verbatim)"
    id: "AC-SIMPLICITY-02"
    text: |
      Keyword idiom rules:
      (a) Sub-libraries (any namespace-prefixed keyword): MUST use
          getter+AssertionEngine matcher form. Boolean `Should Be X`
          keywords are PROHIBITED in sub-libraries.
      (b) Core keywords (no namespace prefix): MAY use ergonomic
          `Should Be X` / `Should Have X` form for the everyday-user
          surface. The core is intentionally NOT capped at 10. For every
          ergonomic core keyword, a paired `Get X` getter MUST exist
          returning the underlying value, suitable for programmatic /
          composed use with AssertionEngine operators.

  - source: "party-mode roundtable @ step-04 (Amelia)"
    type: "keyword rename decisions (carry into FRs)"
    label: "AC-SIMPLICITY-02 enforcement: sub-library renames"
    text: |
      Sub-library keyword renames adopted (per AC-SIMPLICITY-02a):
        - MCP.Tool Should Be Discoverable  ->  MCP.Get Tool Discoverability
          (returns pass@k float; AC-DISCOVER-01 evidence block applies)
        - Skill.Should Be Activated         ->  Skill.Get Activation Decision
          (returns boolean; assert via AssertionEngine ==/!= matchers)
        - Skill.Validate Frontmatter        ->  Skill.Get Frontmatter
          (returns dict) + pair with `Should Be Valid Frontmatter` matcher
        - Stat.Pass At K                    ->  Stat.Get Pass At K
          (returns float 0..1; assert via AssertionEngine >=/<= matchers)
        - Trajectory.Should Match           ->  drop the prefix; this is
          a CORE ergonomic keyword (`Trajectory Should Match`) paired
          with core getter `Get Trajectory`.

  - source: "party-mode roundtable @ step-04 (Many directive)"
    type: "design decision"
    label: "Core keyword set: paired getters + no strict count cap"
    text: |
      The "10-keyword core" cap from Step 2 is RELAXED. Many's directive:
      "Ergonomics is important. But ensure each ergonomic 'Should Be'
      Keyword also offers a consistent 'Getter' Keyword following the
      AssertionEngine Pattern." Core size is no longer pinned to a number;
      the memorize-or-fail concept is preserved as the everyday surface
      bar, not a count. Paired getters are required (AC-SIMPLICITY-02b).

      Paired core keyword set as of Step 4:
        - Connect Agent                     (action; returns agent handle)
        - Send Prompt                       (action; returns response handle)
        - Run Scenario                      (action; returns run result handle)
        - Agent Response Should Contain     <-> Get Agent Response
        - Agent Response Should Match Schema<-> Get Agent Response + matcher
        - Tool Call Should Have Occurred    <-> Get Tool Calls + Should Contain matcher
        - Trajectory Should Match           <-> Get Trajectory
        - Latency Should Be Below           <-> Get Latency
        - Cost Should Be Below              <-> Get Cost Total  [NEW: added per Journey 5; Metric.Get Cost Total also added]
        - Evaluate With Judge               <-> Get Judge Score  [Phase 2 only]

  - source: "party-mode roundtable @ step-04 (Amelia + Many)"
    type: "Phase 1 / Phase 2 split decision"
    label: "Devon skill validation flow: Phase 1 = Tier-1+3 subset; full three-tier = Phase 2"
    text: |
      Devon's three-tier skill validation flow (Tier-1 frontmatter +
      Tier-3 activation Pass@k + Tier-2 Judge rubric) is split:
        - Phase 1: Tier-1 + Tier-3 subset ships. Sufficient to catch
          most skill regressions (frontmatter typos + activation drift).
        - Phase 2: Tier-2 Judge.Get Score with rubric ships, completing
          the three-tier story.
      Rationale: keeps Phase 1 scope honest (Judge sub-library remains
      Phase 2 per locked roadmap); preserves the "two tiers are enough
      to earn the install" insight from Sally's elicitation.

  - source: "party-mode roundtable @ step-04 (Paige)"
    type: "documentation deliverable commitment"
    label: "Recipe Gallery as Phase 1 first-class deliverable"
    text: |
      Recipe gallery is a Phase 1 first-class deliverable, not "after MVP"
      polish. Initial seed: 8 Phase 1 recipes (numbered 1-8) mirroring the
      six user journeys + 2 capability-only recipes (Tier-1 MCP, CI nightly
      integration). 5 Phase 2 recipe stubs are pre-named so the docs IA is
      visible from day one. Each recipe targeted at <=1 page with runnable
      code + evidence-block screenshot + next-step link. Replaces the
      verbose journey walkthroughs that previously bloated the PRD.

      The user journeys section in the PRD body is intentionally TIGHT
      (~120-170 words per journey + one Lesson line). Rich step-by-step
      walkthroughs live in the recipe gallery, not the PRD.

  - source: "party-mode roundtable @ step-04 (Paige)"
    type: "runtime error message text (verbatim)"
    label: "PollingDisallowedError revised wording"
    text: |
      The PollingDisallowedError raised on Tier-2/Tier-3 keywords receiving
      `polling=` MUST use the following text shape (Paige's revision):

        PollingDisallowedError: Polling defeats deterministic evaluation.
        Use Stat.Get Pass At K to express tolerance for flakiness instead.
        Example:  ${runs}=  Stat.Run N Times  10  <your assertion>
                  Stat.Get Pass At K  ${runs}  k=8  >=  0.8
        See ADR-003: docs/adr/003-polling-ban.md

      The error MUST link to the ADR. The ADR is user-facing product
      education, not architecture archaeology.

  - source: "party-mode roundtable @ step-04 (Sally)"
    type: "narrative authoring principle"
    label: "Every user journey requires a 'nearly quits' beat"
    text: |
      User journey documentation MUST include a friction beat where the
      user almost gives up before recovering. Smooth/heroic journeys are
      marketing copy, not journeys. This is the editorial standard
      applied during PRD authoring (Sally's call) and carries into the
      recipe gallery (recipes 1-8 each must show the friction moment,
      not just the happy path).

  - source: "advanced-elicitation first-principles @ step-02 (deferred for confirmation)"
    type: "open structural question"
    label: "Is Tier 2 a category error?"
    text: |
      Three-tier model from the brief: Tier-1 Static / Tier-2 LLM-deterministic /
      Tier-3 Agent-non-deterministic. Sally exposed Tier 2 as the "real
      simplicity breaking point" because temp=0 does NOT yield true determinism
      across model versions, providers, snapshot dates. Question worth
      pursuing in Step 4 (Requirements) or via ADR: should Tier 2 fold into
      Tier 3 with a "low-variance" annotation, leaving a two-tier hierarchy
      (Static vs Statistical)? Or does the determinism gradient warrant
      preserving three tiers for ACL-gate purposes?
    notes: |
      Not actioning now — flagged as open structural question for later in
      the workflow. Many can decide whether the brief's three-tier ACL is
      load-bearing or whether a two-tier model would be sharper.

  - source: "party-mode roundtable @ step-02 (Amelia)"
    type: "cost guardrail (acceptance criterion)"
    id: "AC-DISCOVER-02"
    text: |
      MCP.Tool Should Be Discoverable MUST accept a max_cost_usd argument
      (default: 5.00, per keyword invocation, NOT per suite). Pre-flight:
      estimate projected cost from len(models) × len(tasks) × trials × avg_tokens_est;
      if projected > max_cost_usd → SKIP with message
      "projected $X.XX > max_cost_usd=$5.00; raise limit or reduce task_list".
      Mid-run: cumulative token meter → hard-stop + partial-result FAIL at
      1.1 × max_cost_usd. Same guardrail pattern should generalize to other
      Tier-3 keywords that fan out across models/trials.

  - source: "party-mode roundtable @ step-08 (Amelia + Winston + Mary)"
    type: "architecture decision (load-bearing)"
    label: "Tier-1 CodingAgentAdapter cap as principle, not number (ADR-005)"
    text: |
      1st-party adapter ceiling: "≤2 adapters per vendor + 1 generic escape hatch."
      Not an absolute number. Current Tier-1 set instantiates the rule at 6:
        Anthropic: Claude Code CLI (Phase 1) + Claude Agent SDK (Phase 2)
        OpenAI:    OpenAI Agents SDK (Phase 2) + Codex CLI (Phase 2)
        GitHub:    Copilot CLI (Phase 2) — empirically verified Tier-1-grade
        Universal: Generic via LiteLLM (Phase 1)
      New vendors (Mistral, xAI, etc.) can add up to 2 adapters each before
      scope tightening; new vendor entries require explicit Tier-1 promotion
      via ADR. See ADR-005 in adr-backlog-from-prd.md.

  - source: "party-mode roundtable @ step-08 (Amelia + Winston)"
    type: "architecture decision"
    label: "CodingAgentAdapter Protocol internal class split (ADR-006)"
    text: |
      Single public `CodingAgentAdapter` Protocol; internal base classes:
        - InProcessAdapter: SDK-driven (full-fidelity defaults)
        - SubprocessAdapter (ABC): CLI-driven, hooks _spawn / _parse_event / _finalize
      SubprocessAdapter is contributor-facing API (Phase 1 deliverable for
      community CLI adapter authors to reuse subprocess lifecycle + JSONL parsing
      + timeout handling). Protocol is the boundary contract.

  - source: "party-mode roundtable @ step-08 (Amelia)"
    type: "architectural pattern (load-bearing)"
    label: "Hosted-MCP universal trace observation (ADR-007)"
    text: |
      When the library spawns the MCP server the agent connects to (any
      `mcp_servers=` path), the library records every `tools/call` server-side
      regardless of which agent invoked it. Default for any keyword that uses
      mcp_servers=. Source field on ToolCallTrace tells users whether trace is
      adapter-extracted or MCP-observed. This rescues agents the library has no
      adapter for (OpenCode, future CLI agents) — as long as their tool calls
      flow through the library-hosted MCP server. Pi explicitly does NOT
      benefit (no MCP by design).
      NOTE: framing decision — hosted-MCP is a clever recipe, not novel
      methodology. NOT promoted to Innovation section (per elicitation
      finding 8); stays in adapter-matrix subsection only.

  - source: "advanced-elicitation FMA @ step-08 (post-party-mode)"
    type: "acceptance criterion (verbatim, ADR-008)"
    id: "AC-CONFORMANCE-01"
    text: |
      Conformance suite (tests/conformance/) MUST include fidelity oracles —
      golden-trace fixtures recorded from deterministic mock agent runs against
      a fixed scenario. Each adapter under test must produce output matching
      the golden fixture's structure AND values, with documented allowable
      variations (e.g., latency_ms > 0 rather than exact). Adapter emitting
      all-zero latency_ms or hallucinated sequence_index fails the suite.
      Adapter that lies about source="hosted_mcp" fails when fixture source
      attribution is verified. Conformance suite ships in Phase 1 as CONTRACT
      PUBLICATION (so community adapter authors have a runnable target Day 1),
      not for consistency enforcement (P1 has only 2 adapters).

  - source: "advanced-elicitation FMA @ step-08 (post-party-mode)"
    type: "acceptance criterion (verbatim, ADR-009)"
    id: "AC-CONFORMANCE-02"
    text: |
      AgentRunResult.metadata.completeness: Literal["complete", "truncated",
      "partial"] field is REQUIRED. Adapters MUST emit "truncated" when the
      agent exits non-zero mid-stream OR when their event parser fails to reach
      a terminal event. Conformance suite injects truncation (e.g., kills mock
      subprocess mid-run) and asserts the adapter reports it. An adapter that
      always claims "complete" is silently broken — oracle catches this.

  - source: "advanced-elicitation FMA @ step-08 (post-party-mode)"
    type: "acceptance criterion (verbatim, ADR-010)"
    id: "AC-MCP-OBSERVE-01"
    text: |
      Every AgentRunResult from a keyword using mcp_servers= MUST populate
      metadata.mcp_coverage: Literal["hosted_in_process",
      "subprocess_with_observer", "external_mixed"]. (3-value enum per
      ratified ADR-016 D1 trust-floor + D4 adapter contract, 2026-05-17.
      Original draft was 4 values; superseded by ADR-016 spike findings.)
      Metric keywords (Get Tool Call Count, Get Tool Hit Rate, etc.) raise
      IncompleteTraceError on "external_mixed"
      unless user explicitly opts in via allow_external_mcp_blind=True.
      Adapter implementations MUST detect "external MCP in play" — for CC CLI:
      parse ~/.claude.json + project .mcp.json before run. For Copilot CLI:
      parse ~/.copilot/mcp-config.json. Detection-failure default is
      "external_mixed" (safer than "library_only"). Loud refusal beats silent
      half-truth.

  - source: "advanced-elicitation FMA @ step-08 (post-party-mode)"
    type: "acceptance criterion (verbatim, ADR-008)"
    id: "AC-MCP-OBSERVE-02"
    text: |
      MCP observer validates the negotiated MCP spec version at session start.
      If outside the library's tested range (mcp>=1.0,<2.0), observer raises
      UnsupportedMCPVersionError rather than silently producing empty tool_calls
      lists. Conformance suite injects a future-spec mock server to verify this
      gate fires. Each library release pins the supported MCP spec version
      range; users on cutting-edge MCP servers get a clear error pointing to
      a library upgrade path.

  - source: "advanced-elicitation FMA @ step-08 (post-party-mode)"
    type: "acceptance criterion (verbatim, ADR-012)"
    id: "AC-MCP-OBSERVE-03"
    text: |
      MCP observer scopes traces per-RF-test by reading the Listener v3 test_id
      from RF context. Each test gets a unique library-hosted MCP server
      instance by default. Library __init__(mcp_per_test=False) opts out for
      users who explicitly want shared instances; documented trade-off:
      cross-test trace pollution under pabot. Listener fixture in
      tests/conformance/ verifies isolation under parallel execution.
      Trade-off: MCP server startup adds ~100-500ms per test depending on
      server. Acceptable for Tier 1/2 (rarely parallelized); Tier 3 (heavily
      parallelized via Pass@k) should consider mcp_per_test=False with
      documented pollution caveat.

  - source: "user input @ step-08 + WebFetch + local empirical validation 2026-05-16"
    type: "scope correction (CodingAgentAdapter Tier-1 promotion)"
    label: "GitHub Copilot CLI promoted from 'deferred' to Tier-1 Phase 2 (ADR-013)"
    text: |
      Initial party-mode assessment flagged Copilot CLI as "not agentic, no
      traces, F-rated reliability" (deferred). User directive to verify
      empirically led to:
        1. WebFetch of https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference
        2. Local check: GitHub Copilot CLI v1.0.9 installed at /home/many/.nvm/versions/node/v24.13.0/bin/copilot
        3. ~/.copilot/ inspection: configured, mcp-config.json present, session-state/ + logs/ populated
      Empirical findings:
        - Highly agentic (multi-turn, autopilot mode, subagent delegation)
        - JSONL session events at ~/.copilot/session-state/{uuid}/events.jsonl
        - Live JSONL via -p + --output-format=json (programmatic mode)
        - Full MCP support: ~/.copilot/mcp-config.json + --additional-mcp-config + --add-github-mcp-tool
        - Permissions surface: --allow-all-tools, --allow-all-paths, --allow-all-urls, --allow-tool[=tools]
        - ACP (Agent Client Protocol) server mode via --acp (out of immediate scope)
        - Plain-text logs at ~/.copilot/logs/process-{ts}-{pid}.log (secondary to events.jsonl)
      Promotion: Tier-1 Phase 2 adapter, parity with Claude Code CLI in capabilities.
      Adapter strategy (ADR-013): live JSONL primary + post-hoc events.jsonl fallback.
      Pin copilot CLI version range >=1.0.9,<2.0.

  - source: "party-mode roundtable @ step-08 (Amelia)"
    type: "design decision"
    label: "ToolCallTrace Protocol-level shape"
    text: |
      Tool-call telemetry shape defined ONCE at the Protocol layer so every
      adapter (1st-party or community) speaks the same telemetry dialect:

        @dataclass(frozen=True)
        class ToolCallTrace:
            name: str
            args: dict[str, Any]
            result: Any
            error: Optional[str]
            latency_ms: float
            sequence_index: int
            source: Literal["adapter", "hosted_mcp"]

      Every Metric.* keyword reads from list[ToolCallTrace]. The `source`
      field tells users (and downstream metric logic) whether trace fidelity
      is adapter-extracted or MCP-observed. Conformance suite asserts every
      adapter emits this shape AND verifies fidelity per AC-CONFORMANCE-01.

  - source: "party-mode roundtable @ step-08 (Mary; refinement to elicitation collapse)"
    type: "design decision (revises prior persona collapse)"
    label: "Third persona: Agent Surface Author + persona-split test (ADR-014)"
    text: |
      Three primary personas (revises post-elicitation collapse from 2 → 3):
        - QA Engineer (Priya): evaluates pre-existing agents
        - Agent Surface Author (Devon Skill, Mei MCP): ships skills + MCP
          servers + prompts INTO pre-built coding agents (Claude Code, Codex,
          GitHub Copilot CLI, Pi, etc.)
        - Agent Developer (Raj): builds multi-step agent orchestrations from
          scratch via SDK paths (Claude Agent SDK, OpenAI Agents SDK, Generic
          LiteLLM)
      Persona-split test (locked, applies to future persona decisions):
        "A persona is split from another when downstream artifacts (epics,
        stories, capability surfaces) require different CAPABILITIES — not
        when different PEOPLE happen to use different TOOLS."
      Three-way split survives the test: Skill. + MCP. keywords (Surface
      Author) vs. Run Scenario + Trajectory. + scenario YAML (Agent Developer)
      are genuinely different downstream capability surfaces.
    notes: |
      Follow-up to earlier "Persona inflation correction" finding from
      elicitation pre-mortem (which collapsed personas from 4 to 2). Mary's
      directive about CLI agents added new information (different build
      surface, not just different tools) that the pre-mortem didn't consider.
      Refinement, not contradiction — both findings were right at the time.

  - source: "advanced-elicitation FMA @ step-08"
    type: "engineering rule (never-bundle)"
    label: "Vendor binaries are never bundled"
    text: |
      Library ships adapter wrappers ONLY. Vendor binaries (claude, codex,
      copilot, goose Rust binary, opencode runtime, pi Node.js binary) must
      be present on user's $PATH. Library adapter:
        - validates binary presence at adapter instantiation
        - validates binary version range at first invocation (raises
          UnsupportedBinaryVersionError if outside pinned range)
        - never downloads, installs, or auto-updates binaries
      Posture is engineering hygiene; non-negotiable.

  - source: "party-mode roundtable @ step-08 + WebFetch validation"
    type: "community tier categorization"
    label: "Pi (earendil-works/pi-coding-agent) Tier-2 community"
    text: |
      Pi is a Node.js terminal coding agent (npm install -g @earendil-works/pi-coding-agent).
      Source: https://pi.dev/
      Categorization: Tier 2 community adapter, JSON-RPC output mode for trace
      extraction. Key constraint: "No MCP" is a deliberate design choice in Pi.
      Hosted-MCP universal trace observation fallback (AC-MCP-OBSERVE-01 / ADR-007)
      does NOT apply to Pi-specific workflows. Pi users get adapter-extracted
      traces via JSON-RPC mode only. AgentRunResult.metadata.mcp_coverage="no_mcp"
      for Pi runs.

  - source: "party-mode roundtable @ step-08"
    type: "deferred adapter (tracked gap)"
    label: "GitHub Copilot CLI was initially deferred — REVERSED post-empirical-validation"
    text: |
      Initial assessment (party-mode round 1): Copilot CLI is "not agentic"
      (gh copilot suggest/explain is one-shot); deferred until Copilot Agent
      mode exposes structured CLI traces.
      REVERSED 2026-05-16 after user directive + empirical validation: actual
      Copilot CLI (v1.0.9) is FULLY agentic with autopilot mode, MCP support,
      JSONL session events. Initial assessment was based on outdated/incomplete
      panel knowledge. See "GitHub Copilot CLI promoted from 'deferred' to
      Tier-1 Phase 2 (ADR-013)" entry above for full evidence trail.

  - source: "party-mode roundtable @ step-08 (Paige's polling-ban rewrite)"
    type: "runtime error message text (verbatim)"
    label: "PollingDisallowedError revised wording (Paige rewrite)"
    text: |
      PollingDisallowedError raised on Tier-2/Tier-3 keywords receiving
      `polling=` MUST use the following text shape (revises original wording):

        PollingDisallowedError: Polling defeats deterministic evaluation. Use
        Stat.Get Pass At K to express tolerance for flakiness instead.
        Example:  ${runs}=  Stat.Run N Times  10  <your assertion>
                  Stat.Get Pass At K  ${runs}  k=8  >=  0.8
        See ADR-003: docs/adr/003-polling-ban.md

      The error MUST link to the ADR. ADR is user-facing product education,
      not architecture archaeology.

  - source: "party-mode + advanced-elicitation roundtable @ step-09"
    type: "FR-list-shape decision (load-bearing)"
    label: "FR rewrite — 44 → 65 FRs across 11 capability areas; testability rule applied globally"
    text: |
      Functional Requirements expanded and restructured during party-mode at Step 9:
        - Count: 44 → 65 FRs.
        - Capability areas: 8 → 11 (added 9. Reporting/CI/First-Run-Experience,
          10. Honest Failure Reporting, 11. Determinism Contract & Stability
          Surface as doc-deliverable capabilities).
        - Splits applied (Amelia's call): FR9 → FR9a/b; FR12 → FR12 + FR13a-f
          (per-adapter); FR17 → FR17a/b/c; FR29 → FR29a/b/c; FR30 → FR30a/b/31a/b;
          FR33 → FR33a/b; FR34 → FR34a/b; FR36 → FR36a/b; FR23 → FR23a/b.
        - Net-new FRs (Mary's merit-worthy adds + Sally's first-run + visual contract):
          FR18 (agenteval new-adapter scaffold), FR39 (RunManifest), FR49 (JUnit
          XML), FR50 (non-zero exit codes), FR51 (trace ID in report), FR52
          (agenteval init), FR54 (terminal run summary), FR55 (cohort heatmap
          format), FR56 (polling-error testability checklist), FR57 (conformance
          report shape), FR58 (OTel trace visual contract), FR59 (Tier-1 setup
          diagnostics), FR60-62 (Honest Failure Reporting), FR63-65 (Determinism
          Contract + Stability Surface + Exit Criteria docs).
        - Phase boundary correction: FR10 split into FR10a (Phase 1 per-adapter
          discoverability) + FR10b (Phase 2 cross-adapter comparison with
          Mann-Whitney) — comparability requires ≥2 fully-shipped Tier-1
          runtimes, Phase 1 has only Generic stub + CC CLI.

  - source: "advanced-elicitation @ step-09 (Amelia, accepted as rule)"
    type: "testability rule (load-bearing for all future FR work)"
    label: "FR observability rule"
    text: |
      Every Functional Requirement MUST specify the observable behavior that
      proves it exists — exact keyword name + arguments, error class + message,
      or measurable output shape. "Per AC-X" pointer-style FRs are non-compliant.
      ACs define pass/fail criteria; FRs define the observable. Architecture
      step (bmad-create-architecture) and epic/story breakdown should keep the
      FR↔AC link symmetric: every AC has an FR that names how to test the AC,
      and every FR has an observable behavior in the conformance suite (FR45)
      or library-level test suite.

  - source: "user empirical input @ step-10 (NFR-PERF-03 revision)"
    type: "empirical performance datum (load-bearing for NFR + architecture)"
    label: "MCP server startup: bundled-echo vs user-provided heavy servers"
    text: |
      User-provided first-party MCP servers under test (e.g., rf-mcp, robotmcp,
      robotframework-agentskills-shipped servers) take SEVERAL SECONDS to start
      because they bootstrap Robot Framework + library state + MCP protocol
      handshake. Initial NFR-PERF-03 budget of ≤500ms was wrong for any
      non-trivial server; revised at Step 10 into split budgets:
        - NFR-PERF-03a: bundled echo MCP server ≤200ms (library-controlled,
          must stay lightweight to support 5-min time-to-first-test bar).
        - NFR-PERF-03b: user-provided MCP servers — no startup cap; several
          seconds is acknowledged and accepted, NOT a defect.
        - NFR-PERF-03c: MCP protocol handshake (post-startup) ≤500ms (library/
          SDK-controlled; bar-able).
        - NFR-PERF-03d: documented cost-vs-isolation trade-off matrix via
          `mcp_per_test=True|"suite"|False` with new value "suite" introduced
          for heavy-server reuse with documented per-test trace caveat.
    notes: |
      Architecture step downstream should design the MCP observer + lifecycle
      to support the three mcp_per_test modes from day one. The "suite" value
      is a Phase 1 addition driven by this empirical input. Recipe Gallery
      recipe #5 (rf-mcp / robotframework-agentskills dogfood replacement)
      MUST surface the trade-off matrix prominently — without it the dogfood
      replacement story is intolerably slow under default per-test scope.

  - source: "user input @ step-10 (defensive add) + NFR-PERF-06 / FR11b"
    type: "new acceptance criterion + capability"
    label: "Time-guardrail keyword argument (max_runtime_seconds) — parallels max_cost_usd"
    text: |
      Tier-3 fan-out keywords MUST accept max_runtime_seconds keyword argument
      (default None, opt-in). When set:
        - Pre-flight: estimate (mcp_startup × n_servers × n_trials +
          agent_runtime × n_trials); raise RuntimeBudgetExceededError if
          projected > limit BEFORE any agent invocation.
        - Mid-run: cumulative wall-clock meter; hard-stop + RuntimeBudgetExceeded
          at 1.1× limit.
      Rationale: cost guardrail (FR11 / AC-DISCOVER-02) catches token spend
      but not wall-clock latency. Under heavy MCP servers + Pass@k re-runs,
      runtime can compound silently to hour-scale without budget signal.
      This guardrail is the time-dimension twin of the cost guardrail; both
      should be defaulted-off (opt-in) so they don't surprise low-trial users
      but available for production CI safety nets.
      Captured as FR11b in the Functional Requirements section.

  - source: "party-mode @ step-09 (Mary's findings; integrity caveat)"
    type: "process integrity note for downstream agents"
    label: "Mary's party-mode citations were fabricated — findings extracted on merit only"
    text: |
      During the Step 9 party-mode FR review, Mary cited upstream PRD sections
      ("Goals §3.1, §3.2, §3.3", "Persona doc §4.4") and Journey personas
      ("Maya" in Journey 2, "Sam" in Journey 4, "Lin" in Journey 5, "Toni" in
      Journey 6) that DO NOT EXIST in the actual PRD. The real Journey personas
      are Priya (J1+J2), Mei (J3), Devon (J4), Raj (J5), Inês (J6); the PRD has
      no "Goals §3.x" or "Persona doc §4.4."
      Mary's FINDINGS that were merit-extracted into the FR rewrite (FR18, FR39,
      FR49, FR50, FR51, FR59 + FR10 phase split) stand on their own; they are
      NOT "promised upstream" as Mary framed them. Future workflow agents
      reviewing this PRD should treat references to PRD-internal sections with
      verification, not trust. Recommendation for future bmad-party-mode runs:
      cross-check cited sections against the actual artifact before extracting
      findings as "the spec promises X."

  - source: "advanced-elicitation ADR backlog @ step-08"
    type: "sidecar artifact reference"
    label: "ADR backlog seeded from PRD"
    text: |
      10 ADR seeds (ADR-005 through ADR-014) saved as standalone artifact at
      _bmad-output/planning-artifacts/adr-backlog-from-prd.md.
      Status: Proposed (to be ratified at Phase 1 close).
      Architecture step (bmad-create-architecture) should ingest this file as
      input; final ratified ADRs live in docs/adr/ with formal numbering once
      Phase 1 implementation begins.
      Informed by patterns reviewed in robotframework-agentguard (one reference among
      others; agenteval evaluates each on merit and may diverge):
        ADR-001 DynamicCore composition (borrowed from agentguard)
        ADR-002 AssertionEngine adoption (borrowed from agentguard)
        ADR-003 Polling ban on Tier-2/3 (borrowed from agentguard, referenced in
                PollingDisallowedError text)
        ADR-004 `validate` operator disabled by default (borrowed from agentguard)
      New from PRD work:
        ADR-005 Tier-1 adapter cap rule
        ADR-006 CodingAgentAdapter Protocol internal class split
        ADR-007 Hosted-MCP universal trace observation pattern
        ADR-008 Conformance suite fidelity oracles
        ADR-009 AgentRunResult.metadata.completeness required
        ADR-010 AgentRunResult.metadata.mcp_coverage + IncompleteTraceError
        ADR-011 MCP spec version validation
        ADR-012 Per-test MCP server scope (Listener v3 test_id)
        ADR-013 Copilot CLI adapter trace extraction strategy
        ADR-014 Three-persona model + persona-split test
---

# Product Requirements Document - robotframework-agenteval

**Author:** Many
**Date:** 2026-05-16

## Executive Summary

`robotframework-agenteval` is an open-source Robot Framework library that lets QA engineers and agent developers evaluate AI agents — MCP servers, Claude Code skills, sub-agents, hooks, and multi-step LLM agents — using the same keyword-driven `.robot` suites, listeners, and `output.xml` reporting they already run in CI. It targets a real, narrow gap: five MCP-eval frameworks emerged in <12 months (DeepEval, lastmile-ai/mcp-eval, wolfeidau/mcp-evals, @mcp-testing/server-tester, MCPBench) — *zero* target Robot Framework. Teams running RF acceptance suites today either bolt on a parallel Python eval stack or skip rigorous agent eval entirely.

The product is shaped around one load-bearing principle: **simplicity is legibility of pass/fail.** Every assertion keyword writes a self-contained evidence block — threshold, observed value, raw agent artifact — so a reviewer determines correctness without re-running the test or consulting external dashboards. A 10-keyword memorize-or-fail starter set drives the everyday experience; lazy-loaded sub-libraries with short namespace prefixes (`MCP.`, `Skill.`, `Hook.`, `Stat.`, …) make the full surface discoverable without flooding autocomplete. Statistical honesty is the default — polling banned on non-deterministic keywords, Pass@k unbiased estimator (HumanEval), `temp=0` baseline, OpenTelemetry GenAI semantic conventions for trace recording. Agent-agnosticism is structurally enforced via two Protocols (`LLMProviderAdapter` over LiteLLM's 140+ providers including local Ollama/vLLM; `CodingAgentAdapter` over Claude Agent SDK / OpenAI Agents SDK / generic-via-LiteLLM).

This is a **credible 0.x project**, not a 1.0 spec — the project draws on patterns reviewed in `robotframework-agentguard` (one reference among others) but evolves independently, maintainership is solo + AI-agent-assisted (honest about AI productivity being near-zero on RF/MCP/OTel-internal surfaces), and two existing repos with custom end-to-end agent tests — [`rf-mcp`](https://github.com/manykarim/rf-mcp) and [`robotframework-agentskills`](https://github.com/manykarim/robotframework-agentskills) — serve as concrete dogfood targets and a falsifiable Phase 1 scope bar: by end of Phase 1, those custom tests are replaceable by `.robot` suites using this library at parity or better. The bet is not on novel methodology (Pass@k, BFCL trajectory match, LLM-as-judge, OTel GenAI semconv are all borrowed); it is on **editorial discipline** — that an RF-native library shaped by the legibility principle becomes the way the RF community gates AI agents, before competitors notice the niche.

### What Makes This Special

- **The only RF-native agent-eval option.** All existing eval frameworks (DeepEval, Ragas, Promptfoo, Inspect AI, LangSmith, Braintrust, Phoenix) assume Python-script or hosted-SaaS workflows. None plug into Robot Framework's keyword-driven syntax, listener v3, libdoc, or `output.xml`. The five MCP-eval frameworks target Python/Go/TypeScript exclusively. Niche is clean, defensible *as long as the editorial taste holds* — see below.
- **Simplicity = legibility, codified as an acceptance criterion.** `AC-SIMPLICITY-01` makes evidence-block legibility a contract, not an aspiration: every assertion logs the exact threshold, the observed value, and the raw agent artifact (response, trajectory, or tool-call trace) that produced the verdict. Tier-2 ("LLM-deterministic") keywords get *stronger* legibility requirements than Tier-3 because they hide non-determinism behind seemingly simple assertions.
- **Statistical honesty as a default.** Polling banned on Tier-2 and Tier-3 keywords (raises `PollingDisallowedError`) to prevent survivorship-bias in CI gates. Pass@k uses the HumanEval unbiased estimator. `temp=0`, optional fixed `seed`. Advanced statistics (Mann-Whitney U, Cliff's δ, bootstrap CI, judge calibration) live behind an opt-in `agenteval-advanced` extra — they don't pollute the core surface.
- **Agent-agnostic by construction, not by promise.** Two Protocols separate LLM I/O from full agent runs. LiteLLM's `LLMProviderAdapter` covers 140+ providers including local Ollama/vLLM on day one; the Generic `CodingAgentAdapter` runs against any LiteLLM-backed model without depending on vendor SDKs. Claude Agent SDK and OpenAI Agents SDK adapters are optional extras.
- **Tool Discoverability — a Phase 1 capability no competitor ships.** Evaluates whether different agents and models *find and pick* an MCP tool given natural-language tasks, surfacing failed-task prompts + competing tool picks + docstring under test in a single evidence block (`AC-DISCOVER-01`). Cost-guarded by default (`max_cost_usd=5.00` per invocation). Tagline: *debugging discoverability is debugging vocabulary.*
- **Editorial taste is the moat — and the code is the proof.** A competitor (DeepEval, Promptfoo, Inspect AI) could ship a Robot Framework binding in a weekend; what they cannot trivially copy is the legibility commitment, the polling ban, the Tier-2 trap call-out, the cost-guardrail default, the 10-keyword lid. ADRs and docs are first-class Phase 1 deliverables — not "after MVP" polish.
- **Concrete dogfood loop.** [`rf-mcp`](https://github.com/manykarim/rf-mcp) and [`robotframework-agentskills`](https://github.com/manykarim/robotframework-agentskills) already maintain custom end-to-end agent tests with non-deterministic eval. The Phase 1 success bar (`AC-DOGFOOD-01`) is that those custom tests are replaceable by `.robot` suites using this library at parity. Free design feedback; falsifiable scope; non-hypothetical credibility.

## Innovation: Narrow and Honest

This product is excellent execution of existing patterns — not a new paradigm. Agent-eval methodology (HumanEval Pass@k, BFCL trajectory match, LLM-as-judge, OTel GenAI semantic conventions) is borrowed. Architectural patterns are reviewed across multiple references — `robotframework-agentguard` is one such reference (no dependency, free to diverge), alongside `wolfeidau/mcp-evals`, `lastmile-ai/mcp-eval`, OpenTelemetry GenAI semconv, and others. The keyword surface uses `robotframework-pythonlibcore` and `robotframework-assertion-engine` as-is. No DSL was invented; the scenario YAML format is synthesized from `wolfeidau/mcp-evals` + `lastmile-ai/mcp-eval`. Per Sally's red-team finding: *editorial taste is the moat, not the code* — a competitor could ship an RF binding in a weekend. The bet is on disciplined execution and combination, not on novel methodology.

Two narrow surfaces *are* genuinely novel (no competitor ships them) — both already documented elsewhere in this PRD rather than re-explained here:

- **`MCP.Get Tool Discoverability` as a first-class eval primitive** — see `AC-DISCOVER-01` (Success Criteria > Technical Success) and Journey 3 (User Journeys). No other agent-eval framework ships a built-in assertion for *"does this agent / model find and pick my MCP tool given natural-language tasks?"* Existing frameworks observe tool selection as an outcome; this library asserts it as a contract with statistical thresholds and cost guardrails.
- **`AC-SIMPLICITY-01` + `AC-SIMPLICITY-02` as codified product contracts** — see Success Criteria > Technical Success and User Journeys > Journey Requirements Summary. The "evidence-block legibility" requirement and the "sub-library getter+matcher with core ergonomic carve-out + paired-getter rule" are editorial *stances* no other eval framework has articulated. The novelty is the commitment, not the technical sophistication.

These two are the only places "innovation" framing applies honestly. Everywhere else, the right framing is "carefully executed combination of mature components."

## Project Classification

| Dimension | Value | Note |
|---|---|---|
| **Project Type** | `developer_tool` | Robot Framework PyPI library; primary surface is keywords, not Python classes |
| **Domain** | `general` | CSV bucket; chosen for honest scaffolding fit |
| **Subdomain (annotation)** | `ai_agent_quality_engineering` | Real positioning; library applies scientific methods (Pass@k, Wilson CI, judge rubrics) without being a scientific-computing tool |
| **Complexity** | `high` (focused) | Justified at the integration boundary (MCP spec churn, OTel GenAI semconv experimental, three coding-agent SDK adapters, async-sync bridge, statistical primitives); architectural pattern-discovery risk reduced by drawing on reviewed references including `robotframework-agentguard` |
| **Project Context** | `greenfield` | No existing implementation; two adjacent repos serve as dogfood/reference targets |

**Honest framing of classification's role:** classification is treated as **inert metadata** for downstream tooling — *not* as a driver for which PRD sections to include. The real scaffold for this PRD is the captured context, principles, and acceptance criteria in this document's frontmatter (`userProvidedContext`), accumulated through brief → distillate → research → party-mode → advanced-elicitation. CSV-derived sections (`migration_guide`, `accuracy_metrics`, `computational_requirements`, operational NFRs) are dropped or renamed where they misframe a focused 0.x library; new sections (Stability Surface, scenario YAML schema contract, agent-adapter matrix, statistical-determinism contract, 0.x→1.0 exit criteria) are added because the product genuinely needs them.

## Success Criteria

### User Success

Three primary personas, each with a defined "this earned its install" moment. Persona splits follow the **persona-split test (ADR-014):** a persona is split from another when downstream artifacts (epics, stories, capability surfaces) require *different capabilities*, not when *different people* happen to use *different tools*. The three personas survive this test — each maps to a genuinely different keyword surface and capability set.

- **QA Engineer (evaluates pre-existing agents).** Drops `uv add robotframework-agenteval` into an existing RF acceptance project; writes one `.robot` test against a target MCP server or skill in **under 5 minutes** on the published happy path; sees a green or red verdict in `output.xml` and Robot HTML report alongside her existing tests — *without leaving the RF toolchain or learning a Python eval framework*. The "aha" moment: a failure surfaces with the exact tool the agent called instead, the docstring under test, and the threshold violated — visible in the standard RF log, no external dashboard.
- **Agent Surface Author (ships skills, MCP servers, prompts INTO pre-built coding agents).** Devon writes a Claude Code skill and uses `Skill.Get Frontmatter` + `Skill.Get Activation Decision` + `Stat.Get Pass At K` to validate it triggers reliably. Mei runs `MCP.Get Tool Discoverability` against her MCP server across multiple models and reads the cohort table to fix her docstrings. The "aha" moment: *understands within 30 seconds which docstring to fix* via the per-model cohort + failed-task prompts + competing tool picks evidence block — without needing eval-methodology expertise. Uses Claude Code, Codex CLI, GitHub Copilot CLI, Pi, or any other pre-built coding agent as the runtime under test.
- **Agent Developer (builds multi-step agent orchestrations from scratch).** Raj runs `Run Scenario` against a YAML eval bundle with `Stat.Get Pass At K` thresholds and gets honest statistical verdicts rather than retry-until-green theatre. The "aha" moment: replaces a custom Python end-to-end test (the kind that exists today in [`rf-mcp`](https://github.com/manykarim/rf-mcp) and [`robotframework-agentskills`](https://github.com/manykarim/robotframework-agentskills)) with a `.robot` suite at parity — less custom code, same rigor. Works with Claude Agent SDK, OpenAI Agents SDK, or the Generic LiteLLM-backed runtime for full orchestration control.

A test that passes or fails for reasons the writer cannot read off the Robot log within 30 seconds is treated as a product bug, not a user error. This is the operational form of `AC-SIMPLICITY-01`.

### Business Success

For an Apache-2.0 OSS library with no commercial model, business success = **honest adoption signals** with decision implications, *not* installs-as-vanity. Bars are falsifiable; missing them triggers a documented response, not silent decay.

- **Month 6 (post-1.0.0):** ≥ 500 unique installers/month (PyPI), ≥ 3 inbound GitHub issues from non-author users (signal that installs are hitting reality), ≥ 1 RoboCon 2027 talk submitted, ≥ 1 community blog post or RF-forum thread citing the library. *Miss two of four → DX/positioning retrospective before further Phase 2 investment.*
- **Month 12:** ≥ 2,000 unique installers/month, ≥ 5 public GitHub dependents (production repos importing the library), ≥ 1 RoboCon 2027 talk accepted, ≥ 1 inbound community PR landed. *Miss majority → reframe positioning from "de facto RF agent-eval standard" to "niche-but-deep" before further scope expansion.*
- **Dogfood credibility (rolling):** `rf-mcp` and `robotframework-agentskills` both have their custom end-to-end tests replaced by `.robot` suites using this library by end of Phase 1 (`AC-DOGFOOD-01`). Both repos remain green in their own CI using only the library — *no maintained custom eval code path*. If a regression in this library breaks either dogfood project's CI, it blocks the next release.

### Technical Success

The library's *internal* quality bars — what makes downstream user success even possible. Carry through ADRs, not just CI configs.

- **`AC-SIMPLICITY-01`:** Every assertion keyword in the core library writes a self-contained evidence block (threshold, observed value, raw agent artifact) on both pass and fail, sufficient for a reviewer to determine correctness without re-running the test or consulting external dashboards. **CI-enforced:** library-level test suite asserts every `@keyword`-decorated assertion method emits the required evidence shape; a missing block fails build.
- **`AC-DISCOVER-01`:** `MCP.Tool Should Be Discoverable` emits a tool-name + pass@k vs threshold + per-model Wilson-CI cohort table + per-task verdict matrix + failed-task prompts + competing-tool-picks + docstring snippet + reproducibility footer. CI-enforced via fixture suite using a mock MCP server.
- **`AC-DISCOVER-02`:** `max_cost_usd` argument (default `5.00`) with pre-flight estimate + mid-run hard-stop at 1.1×. Applies to all Tier-3 keywords that fan out across models/trials. CI-enforced via cost-meter unit tests.
- **`AC-DOGFOOD-01`:** Both reference repos ship `.robot` suites using this library that subsume their existing custom end-to-end tests at parity (same metrics, same assertions, same non-determinism handling). Verified by running each repo's CI against the latest `robotframework-agenteval` release.
- **Test-tier reliability:** unit ≥99% pass rate, smoke 100%, live-nightly ≥95%. CI matrix Python 3.12 + 3.13 on Linux + macOS for unit + acceptance-smoke + acceptance-tier1; nightly cron for live + tier3.
- **Polling-ban enforcement:** `PollingDisallowedError` raised on Tier-2/Tier-3 keywords receiving `polling=` argument. Library-level test suite asserts the gate exists per keyword tier.
- **`AC-CONFORMANCE-01`:** Conformance suite (`tests/conformance/`) includes **fidelity oracles** — golden-trace fixtures recorded from deterministic mock agent runs. Each adapter under test must produce output matching the golden fixture's structure AND values, with documented allowable variations (e.g., `latency_ms > 0` rather than exact). Adapters emitting all-zero latency or hallucinated sequence_index fail the suite. Ships Phase 1 as contract publication (so community adapter authors have a runnable target from Day 1) — see ADR-008.
- **`AC-CONFORMANCE-02`:** `AgentRunResult.metadata.completeness: Literal["complete", "truncated", "partial"]` field is **required**. Conformance suite injects truncation (e.g., kills mock subprocess mid-stream) and asserts the adapter reports `truncated`. Silently-incomplete traces are a worse failure mode than loud truncation — see ADR-009.
- **`AC-MCP-OBSERVE-01`:** `AgentRunResult.metadata.mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` indicator required on every result from keywords using `mcp_servers=` (3-value enum per ratified ADR-016, was 4-value in PRD draft; ratified 2026-05-17 via Story 0.3). Metric keywords (`Get Tool Call Count`, `Get Tool Hit Rate`, etc.) raise `IncompleteTraceError` on `external_mixed` unless user opts in via `allow_external_mcp_blind=True`. Loud refusal beats silent half-truth — see ADR-007/ADR-016.
- **`AC-MCP-OBSERVE-02`:** MCP observer validates negotiated MCP spec version at session start. Raises `UnsupportedMCPVersionError` if outside tested range (`mcp>=1.0,<2.0`). Conformance suite injects a future-spec mock server to verify the gate fires. Same loud-refusal principle as MCP-OBSERVE-01 — see ADR-008 (Story 3.1 code-review Auditor HIGH 2026-05-19: amended from stale ADR-011 reference; ADR-011 is the Three-Persona Model — the MCP spec-version-validation authority is ADR-008 post-renumbering).
- **`AC-MCP-OBSERVE-03`:** MCP observer scopes traces per-RF-test by reading Listener v3 `test_id` from RF context. Each test gets a unique library-hosted MCP server instance by default; `mcp_per_test=False` opts out with documented cross-test pollution trade-off. Conformance suite verifies isolation under `pabot` parallel execution — see ADR-012.

### Measurable Outcomes (consolidated)

| Outcome | Bar | Measured how | Decision if missed |
|---|---|---|---|
| Time-to-first-test (defined cohort) | ≤ 5 min, README-only | Periodically re-timed; CI smoke runs the walkthrough end-to-end | Failure blocks next release; first-day troubleshooting guide gets updated |
| Test-tier reliability | unit ≥99%, smoke 100%, live-nightly ≥95% | GitHub Actions matrix results | Below bar = release-blocking |
| Dogfood replacement | Both reference repos: custom tests retired | Cross-repo CI integration | Below bar = scope-cut signal for next phase |
| Month-6 install signal | ≥500/mo unique installers | PyPI download stats | Triggers DX/positioning retro |
| Month-12 install signal | ≥2,000/mo unique installers + ≥5 dependents | PyPI + libraries.io | Reframes "de facto standard" claim |
| Tool Discoverability cost ceiling | Default `max_cost_usd=5.00` honored | CI cost-meter assertion | Bug, not config issue |

## Product Scope

Three scope tiers — MVP / Growth / Vision — calibrated to the **credible 0.x** framing. MVP is what earns the right to exist; Growth is what makes it the obvious choice; Vision is the long arc.

### MVP — Minimum Viable Product (Phase 1, target 6–8 weeks calendar at solo + AI-agent-assisted throughput)

**Stated throughput caveat:** AI-agent productivity assumed near-zero on RF / MCP / OTel-internal surfaces (these are training-data-rare). Higher productivity on docs, scenario YAML, test fixtures, recipe gallery. Re-baseline weekly without ceremony.

In scope:

- Top-level `AgentEval(DynamicCore)` library + bounded sub-libraries (`mcp/`, `skills/`, `hooks/`, `subagents/`, `scenarios/`, `metrics/`, `stats/`, `_assertions/`, `providers/`, `coding_agent/`, `telemetry/`, `config/`) — lazy-loaded, ≤8-char pronounceable namespace prefixes.
- **10-keyword core** (memorize-or-fail): `Connect Agent`, `Send Prompt`, `Run Scenario`, `Agent Response Should Contain`, `Agent Response Should Match Schema`, `Tool Call Should Have Occurred`, `Trajectory Should Match`, `Latency Should Be Below`, `Cost Should Be Below`, `Evaluate With Judge`.
- **MCP sub-library:** `Start MCP Server`, `Connect To MCP Server`, `Stop MCP Server`, `List MCP Tools`, `Call MCP Tool`, `Get MCP Capabilities`, `Validate MCP Tool Schema`, `MCP.Tool Should Be Discoverable` (Phase 1 capability).
- **Static-inspection sub-libraries** (Skill / Hook / Subagent / Scenario): ~6–8 keywords each.
- **Providers:** LiteLLM adapter (default) + Mock adapter (offline tests).
- **CodingAgent adapters (Phase 1):** Generic (LiteLLM-backed) + `coding_agent/claude_code_cli.py` (Claude Code CLI via `--output-format=stream-json`). Two adapters covering the agnostic baseline (Generic) AND the dogfood Skill/MCP runtime target (Claude Code CLI). Claude Agent SDK + OpenAI Agents SDK + Codex CLI + Copilot CLI deferred to Phase 2 (full Tier-1 set ships by end of Phase 2).
- **Conformance test suite (`tests/conformance/`)** — public Phase 1 deliverable with fidelity oracles (golden-trace fixtures from deterministic mock agent runs). Defines the executable contract for any adapter (1st-party or community). Per AC-CONFORMANCE-01.
- **Hosted-MCP universal trace observer (`telemetry/mcp_observer.py`)** — when the library spawns an MCP server the agent connects to, records every `tools/call` server-side regardless of agent. Per-test scope via Listener v3 `test_id` (AC-MCP-OBSERVE-03). Negotiated MCP spec version gate (AC-MCP-OBSERVE-02). `mcp_coverage` indicator on every `AgentRunResult.metadata` (AC-MCP-OBSERVE-01).
- **AssertionEngine kernel** with three-tier ACL gates + polling ban + `validate` operator disabled by default.
- **OpenTelemetry listener** + in-memory + JSONL trace backends.
- **Metrics keywords:** tool-call count/names/hit-rate/success-rate/trajectory/tokens/latency.
- **Statistical primitives in core:** `Run N Times`, `Pass At K` (HumanEval unbiased estimator). Wilson CI for binomial proportions (no SciPy dep for this).
- **Scenario YAML loader** + `Run Scenario File`.
- **Three example `.robot` suites**, `libdoc`-generated keyword reference, README.
- **Documentation deliverables (first-class, not "after MVP" polish):** "First agent eval in 5 minutes" walkthrough (timed + CI-regressed); recipe gallery ≥8 worked examples; CI integration cookbook (GitHub Actions, GitLab CI); "Coming from DeepEval / Promptfoo" migration mapping; first-day troubleshooting guide (Windows/corporate-env caveats, `uv` alternatives, PyPI proxy/cert, `.env` mistakes); ADRs in `docs/adr/` for every load-bearing decision (DynamicCore composition, AssertionEngine adoption, polling ban, `validate` operator default-off, namespace-prefix discoverability, evidence-block legibility).
- **Dogfood:** `rf-mcp` and `robotframework-agentskills` custom end-to-end tests replaced by `.robot` suites using this library (`AC-DOGFOOD-01`).
- **Tool Discoverability MVP strip:** ≤2 models (`claude-sonnet`, `gpt-4o-mini`), user-supplied `task_list` only (no auto-generation), Wilson CI (no SciPy), single comparator, `asyncio.gather` parallelism only, stdout + JSON artifact output (no HTML report).

Explicit MVP non-goals (do not propose in MVP planning):

- LLM-generated docstring auto-rewrites (eval vs authoring boundary — Sally's call).
- Hosted observability platform / regression-tracking SaaS / human-annotation UI (LangSmith/Braintrust/Phoenix territory).
- Native vendor SDKs as default providers (LiteLLM is the abstraction; native SDKs are reserved Protocol implementations).
- Operational NFRs: SLA, uptime guarantees, scale-out architecture — not applicable to a PyPI library.
- `migration_guide` — pre-1.0, no users to migrate. Replaced by an explicit 0.x→1.0 exit-criteria list.

### Growth Features — Phase 2 (target 4–6 weeks after MVP)

- `coding_agent/claude_agent_sdk.py` — Claude Agent SDK Python adapter (subprocess JSON-lines bridge + in-process MCP-tool support).
- `coding_agent/openai_agents.py` — OpenAI Agents SDK (`Runner.run_streamed` + stream-event capture).
- `coding_agent/codex_cli.py` — Codex CLI adapter (JSON event stream).
- **`coding_agent/copilot_cli.py` — GitHub Copilot CLI adapter** (live `-p --output-format=json` + post-hoc `~/.copilot/session-state/{uuid}/events.jsonl`; MCP support via `~/.copilot/mcp-config.json` + `--additional-mcp-config`). Empirically verified Tier-1-grade on the maintainer's system (v1.0.9, 2026-05-16); promoted from initial "deferred" assessment after WebFetch + local inspection.
- Completes the Tier-1 adapter set: Generic + Claude Code CLI (Phase 1) + Claude Agent SDK + OpenAI Agents SDK + Codex CLI + Copilot CLI (Phase 2) = 6 adapters, within the "≤2 per vendor + 1 universal" rule (3 vendors × 2 + 1 generic). See ADR-005.
- `judge/` sub-library: rubric loader (YAML/dict), `LLM Judge Score`, `LLM Judge Pairwise`, calibration cookbook.
- OTLP trace exporter wiring.
- Advanced statistics behind `agenteval-advanced` opt-in extra: Mann-Whitney U, Cliff's δ, bootstrap CI.
- Tool Discoverability extensions: auto-task generation from docstrings, multi-model statistical significance, docstring A/B side-by-side rendering, judge-model calibration for "did it actually use the tool correctly."
- 5+ additional example scenarios; judge calibration cookbook.
- 0.x→1.0 exit criteria checklist (3–5 bullets — to be authored at Phase 1 close; criteria include API stability across 2 minor releases, dogfood-repo CI green for 90 days, ≥1 external production dependent).

### Vision — Phase 3 (TBD, post-1.0)

- LangGraph / CrewAI / AutoGen bridge adapters as separate `[bridges-*]` extras.
- HumanEval / SWE-bench fixture loaders for benchmark suites.
- Sandboxing for Tier-3 agent-generated code execution (Docker or ephemeral worktree).
- BFCL trajectory match (one reviewed implementation reference: `agentguard`).
- Cross-provider eval harness: same scenario, multiple providers, statistical comparison via Mann-Whitney → "is Claude Opus 4.7 actually better than gpt-4o for our tool-set?" as a one-liner.
- Long-term portfolio anchor: agenteval is one of several independent libraries in Many's portfolio (`agentguard` for safety, future `agent*` libraries as the space matures) — each library solves a complementary problem on its own terms, no shared dependency or required alignment.

## User Journeys

Six narrative journeys covering the **three PRD personas** (QA Engineer + Agent Surface Author + Agent Developer-Multi-step-mode) plus a Contributor. Each ≤170 words, ends with one Lesson line stating the single concept the reader now holds. Rich step-by-step walkthroughs are deferred to the Phase 1 recipe gallery (see Appendix). Every journey includes a friction beat — heroic journeys are marketing copy, not journeys (Sally's editorial standard, captured as a frontmatter authoring principle). Persona-split rationale follows the test stated in `Success Criteria > User Success` (ADR-014).

### Journey 1 — Priya, QA Engineer: First test in five minutes

**Trigger.** Monday Slack: *"Validate the new `sales-agent-v3` MCP server before Thursday demo."* Priya owns the team's RF acceptance suite; she does not own the agent code.

**Path.** `uv add robotframework-agenteval`. Copy the README's 5-min example. Replace the echo MCP server with `sales-agent-v3`'s endpoint. Run — instant red. Her copy-paste left the echo-server fixture path in `Suite Setup`. **Two minutes wondering if the library is broken**, then she reads the error line — it names the fixture. Fix. Green in 8 seconds. Adds `MCP.Get Tool Description    refund_lookup    matches    .*30.day.*`. Red again — the agent team's docstring says "Returns refund records," no mention of 30 days. She Slacks the agent team; fix lands within the hour.

**Capabilities revealed:** README-driven 5-min path; `MCP.` namespace; `MCP.Get Tool Description` + AssertionEngine `matches` matcher; standard `output.xml` + HTML report integration.

**Lesson:** Agent-eval results land in the same Robot HTML report her director already reads — no new dashboard, no parallel toolchain.

### Journey 2 — Priya, QA Engineer: Polling ban + Pass@k recovery

**Trigger.** Three weeks in. A Tier-3 assertion — `Agent Response Should Contain    refund_amount` — passes locally; fails ~1 in 5 in CI.

**Path.** Reflex: she adds `polling=2s`. **The library refuses:**

```
PollingDisallowedError: Polling defeats deterministic evaluation. Use
Stat.Get Pass At K to express tolerance for flakiness instead.
Example:  ${runs}=  Stat.Run N Times  10  <your assertion>
          Stat.Get Pass At K  ${runs}  k=8  >=  0.8
See ADR-003: docs/adr/003-polling-ban.md
```

Annoyance, then the ADR — three-minute read. She rewrites with 10 runs, threshold `k=8 >= 0.8`. Result: 7/10 pass — fails honestly at 0.7. The evidence block shows three failures returned `refund_value`, not `refund_amount`. Real bug in her assertion, not flakiness. Fix → 9/10 → green honestly.

**Capabilities revealed:** `PollingDisallowedError` with actionable copy + ADR link (text revised per Paige); `Stat.Run N Times` (action), `Stat.Get Pass At K` + AssertionEngine matcher (paired getter per AC-SIMPLICITY-02); Tier-3 evidence-block legibility (AC-SIMPLICITY-01); ADR text doing user-facing product education.

**Lesson:** Non-deterministic doesn't mean unreliable — it means you express tolerance explicitly with Pass@k, not by retrying until lucky.

### Journey 3 — Mei, Agent Surface Author (MCP author mode): Vocabulary is the bug

**Trigger.** Internal users say Claude "doesn't find the right tool half the time" against Mei's MCP server. Her unit tests cover correctness, not findability.

**Path.**

```robot
MCP.Get Tool Discoverability    tool=search_database
...    by_models=anthropic/claude-sonnet,openai/gpt-4o-mini
...    with_tasks=${TASK_LIST}    k=8    max_cost_usd=2.00    >=    0.8
```

Pre-flight: $0.84. **Result: pass@k = 0.50, FAIL.** Mei spends 20 minutes assuming gpt-4o-mini is broken before reading the failed-task evidence — `claude-sonnet 8/10, gpt-4o-mini 2/10`. Missed tasks all used *query*, *pull*, *check*; competing tools picked were `run_sql`, `fetch_orders`. Her docstring says "Searches…" — real users don't say "search." Rewrites: *"Search, query, lookup, or filter database tables and rows…"* pass@k = 0.9 both models. Two months later, internal complaints about tool-finding drop to zero.

**Capabilities revealed:** `MCP.Get Tool Discoverability` (renamed from `Should Be Discoverable` per AC-SIMPLICITY-02; AC-DISCOVER-01 evidence block still applies); cost guardrail with pre-flight + mid-run meter (AC-DISCOVER-02); per-model cohort evidence; failed-task prompts + competing tool picks + docstring under test.

**Lesson:** Your docstrings are your agent-facing API; the cohort table shows you which words bridge or block.

### Journey 4 — Devon, Agent Surface Author (Skill author mode): Three-tier skill validation (Phase 1 + Phase 2)

**Trigger.** Devon's Claude Code skill (`incident-triage.md`) triggers inconsistently; unclear whether the issue is description, allowed-tools, or model variance.

**Phase 1 path (ships now — Tier 1 static + Tier 3 statistical).**

```robot
Skill.Get Frontmatter        .claude/skills/incident-triage.md    Should Be Valid Frontmatter
Skill.Get Allowed Tools      .claude/skills/incident-triage.md    contains    Read
${runs}=    Stat.Run N Times    10    Skill.Get Activation Decision
...    name=incident-triage    prompt=Triage the auth-service outage at 14:00 UTC
Stat.Get Pass At K    ${runs}    k=8    >=    0.8
```

**Friction.** First Tier-3 run: 5/10. Devon nearly assumes the library is wrong before reading the failed prompts — users say "analyze," his description says "triage." Description rewrite + re-run = 9/10.

**Phase 2 path (deferred).** Layer Tier-2 `Judge.Get Score` with a rubric to assert the skill *correctly used* the runbook script — not just that it triggered. Devon's full validation flow stacking all three tiers is a Phase 2 capability story; Phase 1 ships the Tier-1 + Tier-3 subset that already catches most regressions.

**Capabilities revealed:** `Skill.Get Frontmatter` + `Should Be Valid Frontmatter` matcher (renamed from `Validate Frontmatter` per AC-SIMPLICITY-02); `Skill.Get Activation Decision` + matcher (renamed from `Should Be Activated`); Tier-1 + Tier-3 composition (Phase 1); `Judge.Get Score` (Phase 2 — explicitly out of Phase 1).

**Lesson:** Skill regressions become catchable when all three tiers stack — but Phase 1 catches most with Tier-1 + Tier-3 alone, and that's enough to earn the install.

### Journey 5 — Raj, Agent Developer (multi-step orchestration mode): Dogfood replacement

**Trigger.** Raj maintains [`rf-mcp`](https://github.com/manykarim/rf-mcp) and [`robotframework-agentskills`](https://github.com/manykarim/robotframework-agentskills) — both with ~800 lines of custom Python end-to-end tests collecting agent metrics against non-deterministic runs. Two repos, two custom stacks, drift between them.

**Path.** Ports the first scenario to YAML + library keywords. **Friction:** custom tests collected a cost-per-step metric the library didn't surface. Files an issue, writes a small `Metric.Get Cost Total` extension locally while the upstream PR lands. Once merged, the rest of the porting is mechanical. Three weeks of weekend work: both repos use only `.robot` + `robotframework-agenteval`. Custom Python: deleted. AC-DOGFOOD-01 satisfied. Library's release CI now runs both downstream repos as integration gates.

**Capabilities revealed:** `Run Scenario` + YAML scenario format; `Metric.` namespace getters (`Get Tool Call Count`, `Get Tool Success Rate`, `Get Latency P95`, **`Get Cost Total`** — new, added this round); `Trajectory Should Match` (core, paired with `Get Trajectory`); cross-repo CI integration as release gate (AC-DOGFOOD-01).

**Lesson:** A library that subsumes existing custom test code at parity is a library proven against real workload shape — not toy demos. *(Framing per Paige: this is dogfood-validation evidence, not a "rip out your tests" pitch.)*

### Journey 6 — Inês, Contributor: Custom Protocol adapter

**Trigger.** Inês's team runs self-hosted vLLM with custom routing logic LiteLLM doesn't natively support. She wants to use the library without forking.

**Path.** Finds `LLMProviderAdapter` Protocol in docs (~40 LoC to implement). **Friction:** her vLLM streams tokens in a format the default `chat()` response shape doesn't expect. She nearly forks. Then notices the Protocol's `stream` arg + the Mock adapter's stream test as a template. Adapts her parser in 20 minutes. Registers via `[project.entry-points."agenteval.providers"]` so all her team's RF projects auto-discover it. First test green. No library patches needed.

**Capabilities revealed:** `LLMProviderAdapter` + `CodingAgentAdapter` Protocols; entry-points discovery for org-wide custom adapters; Mock adapter as contributor fixture/template; no-fork extension path.

**Lesson:** Protocol surfaces survive the user's specific oddities; the Mock adapter is the contract specification users actually read.

### Journey Requirements Summary

Capability surface revealed by the six journeys, grouped by area. Reflects `AC-SIMPLICITY-02` (sub-library getter+matcher rule + core ergonomic carve-out + paired-getter requirement).

**Core keyword surface (ergonomic everyday-user form; paired getters required per `AC-SIMPLICITY-02b`; core is intentionally NOT capped at 10):**

| Ergonomic core keyword | Paired getter (`AC-SIMPLICITY-02b`) | Phase |
|---|---|---|
| `Connect Agent` | (action; returns agent handle) | 1 |
| `Send Prompt` | (action; returns response handle) | 1 |
| `Run Scenario` | (action; returns run result handle) | 1 |
| `Agent Response Should Contain` | `Get Agent Response` (returns str) | 1 |
| `Agent Response Should Match Schema` | `Get Agent Response` + `Should Match Schema` matcher | 1 |
| `Tool Call Should Have Occurred` | `Get Tool Calls` (returns list) + `Should Contain` matcher | 1 |
| `Trajectory Should Match` | `Get Trajectory` (returns ordered list) | 1 |
| `Latency Should Be Below` | `Get Latency` (returns ms float) | 1 |
| `Cost Should Be Below` | `Get Cost Total` (returns USD float) — **added per Journey 5** | 1 |
| `Evaluate With Judge` | `Get Judge Score` (returns float 0..5) | **2** |

**Sub-libraries (lazy-loaded, ≤8-char namespace prefixes; getter + AssertionEngine matcher only per `AC-SIMPLICITY-02a`):**

- `MCP.` — server start/connect/stop, tool list/call, capability introspection, `MCP.Get Tool Description`, **`MCP.Get Tool Discoverability`** (renamed from `Tool Should Be Discoverable`; AC-DISCOVER-01 evidence block still applies).
- `Skill.` — **`Get Frontmatter`** + `Should Be Valid Frontmatter` matcher (renamed from `Validate Frontmatter`); `Get Allowed Tools`; `Get Description`; **`Get Activation Decision`** + matcher (renamed from `Should Be Activated`). Phase 1: frontmatter + allowed-tools + activation. Phase 2: `Run With Prompt` returning richer multi-turn response.
- `Hook.` and `Subagent.` — static-inspection keywords parallel to `Skill.` (frontmatter, configuration). Phase 1.
- `Metric.` — `Get Tool Call Count`, `Get Tool Call Names`, `Get Tool Hit Rate`, `Get Tool Success Rate`, `Get Trajectory`, `Get Token Usage`, `Get Latency`, `Get Latency P95`, **`Get Cost Total`** (new).
- `Stat.` — `Run N Times` (action), **`Get Pass At K`** + AssertionEngine matcher (renamed from `Pass At K`). Mann-Whitney U, Cliff's δ, bootstrap CI: Phase 2, behind `agenteval-advanced` extra.
- `Judge.` — `Get Score` with rubric. **Phase 2 only.**

**Cross-cutting infrastructure:**

- AssertionEngine getter+matcher idiom across every sub-library getter.
- `PollingDisallowedError` with actionable error message + ADR link (text per `userProvidedContext` PollingDisallowedError revised wording; see Journey 2).
- In-memory OTel trace store as metric backplane.
- Evidence-block legibility on every assertion on pass and fail (`AC-SIMPLICITY-01`).
- Cost guardrail with pre-flight + mid-run meter (`AC-DISCOVER-02`). Applies to any Tier-3 keyword that fans out across models/trials.
- `LLMProviderAdapter` + `CodingAgentAdapter` Protocols + entry-points discovery (`[project.entry-points."agenteval.providers"]`, `"agenteval.coding_agents"`).
- Mock adapter for offline tests *and* as contributor template.
- Bundled echo MCP server fixture for the 5-min walkthrough.
- `robot.listener` entry point for trace lifecycle (per-test span hierarchy).

**Documentation surface revealed by journeys (Phase 1, first-class):**

- README with the 5-min walkthrough (Journey 1).
- ADRs that do real product education — particularly ADR-003 polling ban, referenced inline in the runtime error message (Journey 2). ADRs are user-facing footnotes, not architecture archaeology.
- Recipe gallery (see Appendix below) with stubs for recipes 1–8 in Phase 1.
- Cross-repo integration cookbook (Journey 5) — how to wire downstream repos as release gates.

**Capabilities intentionally NOT revealed by journeys (scope check):**

- No admin console, no support-staff workflow, no separate API-consumer journey (the library *is* the API; contributors are the analog and Journey 6 covers them).
- No hosted dashboard — out of scope by design.
- `Judge.Get Score` keyword: Phase 2 only. Devon's full skill validation flow (Tier 1 + 2 + 3 stacked) is a Phase 2 capability story; Phase 1 ships the Tier-1 + Tier-3 subset.

## Domain-Specific Constraints

The CSV-mapped `general` domain framing doesn't fit this product — there's no FDA pathway, no HIPAA boundary, no PCI-DSS scope, no FedRAMP attestation. Compliance positioning is atmospheric (per Executive Summary). But the `high` complexity bump from Step 2 was justified by *real* constraint surfaces — non-determinism handling, external-spec instability, maintainership reality, eval-domain trust/safety, and the determinism contract — that the canonical compliance template misses. This section consolidates them as the source of truth for the architecture step downstream.

### 1. Non-determinism handling (Tier-aware constraints)

LLM agents are non-deterministic; CI gates over them must report honest uncertainty rather than hide it. Constraints the library enforces:

- **Three-tier keyword model with ACL gates.** Tier-1 (static) keywords are fully deterministic and need no API key. Tier-2 (LLM-deterministic) keywords use `temperature=0` defaults and optional `seed` pass-through but are *not* truly deterministic across model versions/providers/snapshot dates — see §5 (Determinism Contract) for what the library does and does not promise. Tier-3 (agent-non-deterministic) keywords are non-deterministic by design.
- **Polling ban on Tier-2 and Tier-3.** The library raises `PollingDisallowedError` if a user passes `polling=` to a Tier-2 or Tier-3 keyword. The error text directs users to `Stat.Get Pass At K` and links ADR-003. Polling defeats statistical interpretation by re-sampling the LLM until "lucky" — survivorship bias destroys CI gate credibility.
- **Statistical primitives in core, not opt-in.** `Stat.Run N Times` + `Stat.Get Pass At K` (HumanEval unbiased estimator) ship in core, not behind an extras flag. The library refuses to make honest statistical assertions optional.
- **Cost guardrails on multi-trial Tier-3 keywords.** `MCP.Get Tool Discoverability` and any future fan-out keyword ship with `max_cost_usd` argument (default `5.00` per invocation), pre-flight estimate, and mid-run hard-stop at 1.1× (`AC-DISCOVER-02`). Without cost ceilings, CI runs that fan out across models × tasks × trials silently burn budget.

### 2. External-specification instability + pinning posture

The library depends on several specs and SDKs that are themselves under active churn. The PRD treats this as a first-class constraint, not a risk-register footnote:

- **MCP spec churn** — Streamable HTTP supersedes deprecated SSE; the Tasks primitive is in flight for the 2026 roadmap; governance is maturing. **Posture:** library pins `mcp>=1.0,<2.0`; MCP-protocol handling is isolated to the `mcp/` sub-library so a spec major-version bump is a single-surface migration. Capability negotiation at session start is the source of truth; hardcoded primitive assumptions are forbidden.
- **OpenTelemetry GenAI semantic conventions** — experimental until expected stabilization through mid-2026. **Posture:** library emits spans through a thin internal facade (`telemetry/semconv.py`), so attribute-name changes are a single-file update. Datadog (≥v1.37) and Grafana are the first-party export targets validated against semconv.
- **LiteLLM** — rapid minor releases, occasionally breaking. **Posture:** pin to a minor floor; `LLMProviderAdapter` Protocol isolates the dependency; Mock adapter ensures unit tests don't break on LiteLLM upgrades. A future vendor-native adapter is a reserved Protocol implementation, not a default.
- **Robot Framework 8.x (future)** — pinned `>=7.4,<9.0`. Library depends only on stable APIs (`@keyword`, Listener v3, DynamicCore via `pythonlibcore`). Pre-release testing on 8.x.beta builds is a Phase 2 deliverable.
- **Coding-agent SDKs (Claude / OpenAI Agents)** — both pre-1.0, plan/pricing/credit changes in flight (Claude Agent SDK billing model changing 2026-06-15). **Posture:** both adapters live behind optional extras (`[claude]`, `[openai-agents]`); the Generic adapter via LiteLLM remains the agnostic default. Adapter churn cannot break the core library.
- **Coding-agent CLIs (Claude Code, Copilot, Codex)** — output-format schemas are CLI-tool-internal and could evolve without notice. **Posture:** each CLI adapter pins a tested binary version range (`[claude-code]` adapter pins `claude` CLI; `[copilot]` adapter pins `copilot` CLI `>=1.0.9,<2.0` per ADR-013; `[codex]` adapter pins `codex` CLI). Integration tests run against the pinned versions; conformance suite (AC-CONFORMANCE-01) catches schema drift via golden-trace fixture mismatches. Adapter wrappers ship; binaries assumed on `$PATH` (library never bundles vendor binaries).

### 3. Maintainership constraints (solo + AI-agent-assisted)

The library is built and maintained solo + AI-agent-assisted. The PRD names this honestly as a load-bearing constraint:

- **AI-agent productivity is assumed near-zero on training-data-rare surfaces** — Robot Framework + MCP Python SDK + OpenTelemetry GenAI semconv + RF Listener v3 + AssertionEngine + agent-eval-framework internal patterns generally. AI agents will be slowest exactly where this library lives. Timeline math (Phase 1 = 6–8 weeks calendar) is honest only because AI productivity is *high* on docs / scenario YAML / test fixtures / recipe gallery and offsets the deficit elsewhere. Re-baseline weekly without ceremony.
- **Bus-factor stated openly.** Orgs requiring vendor SLAs / indemnification / formal support contracts are out of scope for adoption *as unsupported OSS*. Recommended pattern for such orgs: pair the library with a paid-support arrangement or fork. The PRD does not pretend otherwise.
- **Contributor onboarding as a first-class Phase 1 deliverable.** `CONTRIBUTING.md`, "good first issue" labels, the agent* portfolio shared-pattern docs, and the Mock adapter as contributor template (Journey 6) all ship with v1.0. Bus-factor mitigation is treated as product scope, not aspirational.
- **Architectural patterns are reviewed across multiple references including `robotframework-agentguard`.** agentguard is one inspiration / pattern source among others (no dependency, free to diverge). Architecture-discovery risk is reduced by having reviewed prior art; agenteval evolves independently and may pick different abstractions, tools, or approaches whenever they serve agenteval better.

### 4. Trust and safety in the eval domain

Eval frameworks are special — they sit upstream of trust decisions, so their own correctness is load-bearing:

- **LLM-as-judge bias is a known limitation.** The brief does not pretend judge scores are ground truth. Phase 1 ships no `Judge.` keywords (Phase 2 only). Phase 2 ships single-judge `Judge.Get Score` with a rubric + a calibration cookbook. Multi-judge majority voting and ensemble methods are Phase 2+. The library will *not* ship judges as "audit-grade" until calibration evidence supports the claim.
- **`eval()` exposure (AssertionEngine `validate` operator) is gated.** Disabled by default; opt-in only via library `__init__(allow_validate_operator=True)`. Documented as a known footgun (pattern informed by agentguard ADR-013, evaluated on merit for agenteval).
- **Credential redaction is mandatory pre-trace-write.** All adapters route their trace serialization through `config.redact_env()`. CI test asserts no API-key strings appear in committed fixtures. Trace JSONL output is safe to share with auditors / colleagues.
- **Eval ≠ authoring boundary** (Sally's call, captured in frontmatter as an explicit non-goal). The library evaluates docstrings, skills, prompts, tool schemas — it does NOT *rewrite* them. LLM-generated docstring auto-suggestion would cross from evaluation into authoring; that's a different product with a different trust model. Library outputs raw evidence (failed tasks, competing tool picks, missed phrasings) so users can rewrite themselves.
- **Tool Discoverability vocabulary asymmetry** (elicitation finding). For domain-specific jargon (medical, legal, industrial, internal terminology), a failed `MCP.Get Tool Discoverability` result may reflect *agent training-data gaps*, not docstring quality. Library docs surface this asymmetry as a known limitation in the recipe; failure evidence hints when missed-task vocabulary is itself rare.

### 5. Determinism contract

The library's most distinctive product-DNA section. What `robotframework-agenteval` *promises* and *does not promise* about test reproducibility — load-bearing for the "credible 0.x" framing.

**The library promises:**

- **Tier-1 reruns are bit-identical.** Static-inspection keywords (`Skill.Get Frontmatter`, `MCP.Validate Schema`, `Hook.Get Script Path`, etc.) read files + protocol introspection only; same input → same output, every time, forever. CI flakiness on Tier-1 is a product bug, not eval reality.
- **Tier-2/Tier-3 reruns are *statistically interpretable* via `Stat.Run N Times` + `Stat.Get Pass At K`.** Independent samples (fresh agent instance per run; no state leakage). The Pass@k estimator uses HumanEval's unbiased formula (`1 - C(n-c, k) / C(n, k)`). Users who write `Stat.Get Pass At K    ${runs}    k=8    >=    0.8` get an honest verdict; the library does not retry-until-green.
- **Reproducibility footers on every Tier-3 evidence block.** Model name + version, seed, MCP server commit/SHA, task-list hash, library version. Sufficient to reproduce a run (or to identify *why* a rerun differs).
- **Snapshot diffing for Tier-1 outputs.** Tier-1 keywords produce stable JSONL traces suitable for snapshot-based regression detection across releases. Snapshot tests on Tier-1 are first-class Phase 1 test infrastructure.
- **`PollingDisallowedError` on Tier-2 and Tier-3.** Hard refusal; not a warning. Prevents survivorship bias structurally.

**The library does NOT promise:**

- **Cross-model-version reproducibility.** `anthropic/claude-sonnet` evaluated on 2026-05-16 may produce different statistics than the same model identifier evaluated on 2026-08-01. Provider snapshot updates are out of library control. Users who need reproducibility across time MUST pin model snapshots explicitly (e.g., `anthropic/claude-sonnet-4-5-20250929`).
- **Cross-provider reproducibility for "equivalent" models.** `openai/gpt-4o-mini` and `anthropic/claude-haiku-4-5` are NOT interchangeable; the library does not normalize for capability differences.
- **Bit-identical Tier-2/Tier-3 traces across reruns.** `temperature=0` reduces variance dramatically but does not eliminate it; provider-side caches, distributed inference routing, and snapshot updates can produce divergent outputs. The library reports the variance honestly via statistical primitives; it does not pretend determinism is achievable where it isn't.
- **Automatic flake budgets / retry-until-green.** No exponential backoff disguising flakiness, no "skip if flaky" tags, no implicit retry counts. Users explicitly set `k` and threshold; tests pass or fail at those thresholds.
- **Snapshot-equality regression detection on Tier-2/Tier-3 outputs.** Statistical comparison (Mann-Whitney U, Cliff's δ — Phase 2) is the appropriate primitive; bit-equality is the wrong tool. The library's `agenteval-advanced` extras package the statistical comparators; users who try to diff Tier-3 JSONL outputs directly will get noise.

**Determinism contract — single-paragraph summary for the PRD's downstream consumers (architecture, requirements, stories):**

> The library promises bit-identical reproducibility for Tier-1, statistical interpretability for Tier-2/Tier-3 via Pass@k + reproducibility footers, no automatic retry/flake hiding, and explicit refusal (`PollingDisallowedError`) of polling on non-deterministic keywords. The library does not promise cross-version or cross-provider reproducibility, bit-equality on Tier-2/3, or magical flake elimination. Honest statistical reporting beats false-confidence determinism in every keyword decision.

## Developer Tool — Specific Requirements

### Language & Platform Compatibility Matrix

| Dimension | Supported | Pinned floor / ceiling | Rationale |
|---|---|---|---|
| **Python** | 3.12, 3.13 | `>=3.12` (no upper cap) | Modern baseline standard for modern Python+RF libraries; PEP 695 syntax used; older Python not worth the test-matrix cost |
| **Robot Framework** | 7.4–8.x | `>=7.4,<9.0` | Listener v3 (default ≥7.0) and `@keyword` decorator are stable; 8.x is a future concern, pin upper-bounded conservatively |
| **OS — first-class** | Linux, macOS | CI matrix tier-1 | Both run in CI on every PR for unit + acceptance-smoke + acceptance-tier1 |
| **OS — second-class** | Windows | Best-effort, no CI gate | Tier-1 static keywords work; Tier-3 may surface `uv` / proxy / cert issues — first-day troubleshooting guide covers these |
| **MCP SDK** | `mcp>=1.0,<2.0` | Pinned major | Spec churn (Tasks primitive incoming, SSE deprecated) requires single-surface migration if 2.0 lands |
| **LiteLLM** | `litellm>=1.83` | Pinned minor floor | Adapter Protocol isolates; Mock fallback for unit tests |
| **OpenTelemetry** | `opentelemetry-api>=1.27` + `opentelemetry-sdk>=1.27` | Pinned minor floor | GenAI semconv experimental; internal facade isolates attribute-name churn |
| **AssertionEngine** | `robotframework-assertion-engine>=4.0` | Pinned major floor | Provides `AssertionOperator` enum used by every getter+matcher keyword |
| **PythonLibCore** | `robotframework-pythonlibcore>=4.5` | Pinned minor floor | `DynamicCore` composition; lazy sub-library loading |

CI matrix: **Python 3.12 + 3.13** × **Linux + macOS** for unit + acceptance-smoke + acceptance-tier1. Nightly cron for `@live` + tier-3. Windows is documented + best-effort, not gated.

### Installation Methods + Extras Matrix

**Primary install path (the README example):**
```bash
uv add robotframework-agenteval
```

**Fallback (for orgs without `uv`):**
```bash
pip install robotframework-agenteval
```

**Optional extras — each unlocks a bounded capability surface that's lazy-loaded so a missing extra degrades gracefully with a clear `ImportError`:**

| Extras flag | Unlocks | Phase | When to install |
|---|---|---|---|
| (default) | Core keyword surface + MCP + LiteLLM provider + Mock provider + OTel listener (memory/JSONL) + `Stat.Get Pass At K` + Wilson CI | 1 | Every install |
| `[claude-code]` | `coding_agent/claude_code_cli.py` — Claude Code CLI adapter (`--output-format=stream-json`) | **1** | When evaluating against Claude Code CLI (Skill / MCP runtime target; dogfood path) |
| `[claude]` | `coding_agent/claude_agent_sdk.py` — Claude Agent SDK adapter (subprocess JSON-lines bridge) | 2 | When evaluating against Claude Agent SDK Python runtime specifically |
| `[openai-agents]` | `coding_agent/openai_agents.py` — OpenAI Agents SDK adapter | 2 | When evaluating against OpenAI Agents SDK runtime specifically |
| `[codex]` | `coding_agent/codex_cli.py` — Codex CLI adapter (JSON event stream) | 2 | When evaluating against Codex CLI runtime specifically |
| `[copilot]` | `coding_agent/copilot_cli.py` — GitHub Copilot CLI adapter (`-p --output-format=json` live + `~/.copilot/session-state/{uuid}/events.jsonl` post-hoc) | 2 | When evaluating against GitHub Copilot CLI (Skill / MCP runtime target — empirically verified Tier-1-grade) |
| `[otlp]` | `opentelemetry-exporter-otlp` for OTLP trace export to Datadog / Grafana / Tempo | 2 | When wiring traces into a hosted observability backend |
| `[judge]` | `Judge.` sub-library (`Get Score`, rubric loader, calibration cookbook) | 2 | When using LLM-as-judge keywords |
| `[agenteval-advanced]` | `Stat.` advanced primitives — Mann-Whitney U, Cliff's δ, bootstrap CI (adds `scipy` dep) | 2 | When doing cross-model statistical comparison or research-grade analysis |
| `[lint]` | `shellcheck-py` for hook-script linting | 2 | When using `Hook.` static-inspection keywords with shell-script checks |
| `[bench]` | `datasets` for HumanEval / SWE-bench fixture loaders | 3 | When using benchmark suites |
| `[dev]` | `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `robotframework-tidy` | All | Contributors only |

**Install size discipline:** the default install is intentionally minimal. Heavy / niche dependencies are extras. No extras are auto-installed by transitive dependency on the default install.

### IDE Integration & Tooling

- **`libdoc`-generated keyword reference** — `uv run python -m robot.libdoc AgentEval docs/keywords/AgentEval.html` produces one HTML reference per top-level library + per sub-library. Linked from README. Auto-regenerated in CI on every release.
- **`robotframework-lsp` (Language Server Protocol)** — keyword completion, goto-definition, and parameter-info work out-of-the-box once `libdoc` reference is generated. Tested in VS Code (Robot Framework Language Server extension) and IntelliJ (Intellibot). No special LSP work in the library — relies on `@keyword` decorator metadata being clean.
- **`robotframework-tidy`** — listed under `[dev]` extras; pre-commit hook recommended for contributors. Library's own `.robot` examples conform.
- **RIDE compatibility** — RIDE (Robot Framework IDE) still parses the keyword surface via libdoc; documented as "works, not actively tested in CI."
- **VS Code workflow** — README's 5-min walkthrough is timed against a VS Code + RF extension dev environment. Not tested against Windows VS Code; that's first-day troubleshooting territory.

### Keyword Catalog (`api_surface`)

Renamed per editorial decision: for a Robot Framework library, the user-facing "API" *is* the keyword catalog, not Python classes.

**Full keyword catalog — already documented in `User Journeys > Journey Requirements Summary` above.** Reference that section rather than duplicating here. Summary in one line:

- **Core (no namespace prefix; ergonomic everyday-user surface; AC-SIMPLICITY-02b paired-getter rule applies):** 10 ergonomic keywords + their paired getters (Phase 1 except `Evaluate With Judge` → Phase 2).
- **Sub-libraries (lazy-loaded, ≤8-char pronounceable prefixes; AC-SIMPLICITY-02a getter+matcher rule applies):** `MCP.`, `Skill.`, `Hook.`, `Subagent.`, `Metric.`, `Stat.` (all Phase 1); `Judge.` (Phase 2).

The Python-class surface (`AgentEval(DynamicCore)`, `LLMProviderAdapter` Protocol, `CodingAgentAdapter` Protocol, `ChatResponse` dataclass, `AgentRunResult` dataclass) is the *contributor-facing* API — secondary to keywords. Documented in `docs/adr/` and the contributor onboarding section.

### Code Examples

Worked `.robot` examples already shown inline across all six User Journeys above + cross-referenced in `Appendix: Recipe Gallery` (8 Phase 1 recipes + 5 Phase 2 stubs). Reference rather than duplicate.

### 0.x → 1.0 Exit Criteria (stub)

`migration_guide` was cut as premature (per John's elicitation prescription — pre-1.0, no users to migrate). Replaced with explicit exit criteria for when the library stops being 0.x. Full criteria authored at Phase 1 close (when reality reveals what "stable" looks like); preliminary stub:

- **API stability across 2 minor releases.** No breaking keyword renames, signature changes, or removed keywords between two consecutive minor versions on the path to 1.0. Stability Surface metadata in each release notes which surfaces are `stable` / `provisional` / `experimental`.
- **Dogfood repos green on this library for 90 consecutive days.** `rf-mcp` and `robotframework-agentskills` CI green on the latest published release of `robotframework-agenteval` for 90 days, with no library-side fixes required.
- **≥1 external production dependent.** At least one non-author GitHub repo with the library in `pyproject.toml` and active commits.
- **`AC-SIMPLICITY-01` and `AC-SIMPLICITY-02` CI-enforced and clean.** Library-level test suite asserts every assertion keyword emits the required evidence shape AND no sub-library boolean `Should Be X` keyword exists. Build fails if either is violated.
- **Phase 2 capabilities shipped** (Claude / OpenAI Agents SDK adapters, `Judge.` sub-library, OTLP exporter, `agenteval-advanced` extras). 1.0 means Phase 1 + Phase 2 both stable.

These are *preliminary* exit criteria; the canonical list will be authored at Phase 1 close and committed as an ADR. The PRD captures the bar shape so downstream consumers know what 1.0 means.

## Phasing Strategy, Adapter Matrix & Risk Mitigation

Phasing decision: locked at the brief level (Phase 1 / Phase 2 / Phase 3 in `## Product Scope`). This section *consolidates* the phasing rationale + MVP philosophy + risk mitigation + the Coding Agent Adapter Matrix without re-listing features already covered upstream. No silent de-scoping; everything in user-provided input remains in scope.

### MVP Strategy & Philosophy

**MVP type:** **Validated-learning + dogfood-credibility MVP** (not a "feature-complete v1" MVP).

The product earns the right to exist when:
1. The bundled `.robot` examples + recipe gallery convince a QA engineer to install on a Monday and run their first eval before lunch (Journey 1; outcome bar: time-to-first-test ≤ 5 min on the published happy path).
2. The two reference repos (`rf-mcp`, `robotframework-agentskills`) replace their existing custom Python end-to-end tests at parity using only `.robot` + this library (`AC-DOGFOOD-01`).
3. Static-inspection keywords (Tier 1) work zero-API-key, zero-network, in milliseconds — establishing the "this thing rewards installation immediately" property that pulls users into Tier 2/3.

**MVP is NOT:** judge calibration, multi-judge ensembles, OTLP exporter to hosted backends, native Claude Agent SDK / OpenAI Agents SDK adapters, Codex CLI adapter, **Copilot CLI adapter** (Tier-1 Phase 2 per ADR-013), Mann-Whitney U / Cliff's δ comparison, BFCL trajectory match. All deferred to Phase 2/3 (per existing scope) — not because they aren't valuable, but because the MVP must answer "does this library find users who stick" before scaling capability surface.

**Resource requirements** (already locked, restated for this section):
- **Maintainership:** solo + AI-agent-assisted (see `Domain-Specific Constraints > 3. Maintainership constraints`).
- **Phase 1 timeline:** 6–8 weeks calendar; AI productivity assumed near-zero on RF / MCP / OTel-internal surfaces, ~normal on docs / scenario YAML / test fixtures / recipe gallery (which offsets); re-baseline weekly.
- **No team scaling required** to ship MVP; contributor onboarding (Journey 6, `CONTRIBUTING.md`) is itself a Phase 1 deliverable for bus-factor mitigation rather than a precondition.

### Phasing Rationale (why phased, not single-release)

- **Architecture risk is reduced** by drawing on reviewed pattern references (including `robotframework-agentguard`, evaluated on merit), but **timeline risk is real** (solo + AI-productivity-near-zero on RF/MCP/OTel surfaces — see Domain Constraints §3). Phasing limits the scope blast radius if Phase 1 slips.
- **Competitive risk is moderate** (a competitor could ship an RF binding in a weekend — per Sally's red-team finding). Shipping a Phase 1 with credible editorial discipline (`AC-SIMPLICITY-01`, `AC-SIMPLICITY-02`, evidence-block legibility, Tool Discoverability primitive, conformance suite as public Phase 1 deliverable) faster than waiting for a "complete" 1.0 captures the niche before competitors notice.
- **Dogfood loop closure (`AC-DOGFOOD-01`)** is the falsifiable Phase 1 outcome bar — phasing aligns scope with the falsifiable thing.
- **Phase 2 features** (judge calibration, native agent SDK adapters, advanced statistics, additional Tier-1 adapters) depend on Phase 1 learning that doesn't exist yet. Building them in Phase 1 risks building the wrong shape.

### Feature Set References (no duplication)

- **Phase 1 (MVP) feature list:** see `Product Scope > MVP — Minimum Viable Product` above.
- **Phase 2 (Growth) feature list:** see `Product Scope > Growth Features — Phase 2`.
- **Phase 3 (Vision) feature list:** see `Product Scope > Vision — Phase 3`.
- **Phase 1 capability coverage by user journey:** see `User Journeys > Journey Requirements Summary`.
- **Phase 1 documentation deliverables:** see `Product Scope > MVP` doc bullets + `Appendix: Recipe Gallery`.
- **Compatibility + extras matrix:** see `Developer Tool — Specific Requirements > Installation Methods + Extras Matrix`.

### Coding Agent Adapter Matrix

The `CodingAgentAdapter` Protocol underpins all dynamic eval work (Tier 2 + Tier 3 keywords). This subsection defines the adapter tiering, the conformance contract, and the universal MCP observation fallback.

**Architecture rule — adapter cap as principle, not number (ADR-005):**

> The Protocol is the contract; the tier is the promise. 1st-party adapter ceiling is **"≤2 adapters per vendor + 1 generic escape hatch"** — not an absolute number. Current Tier-1 set instantiates the rule at 6 (Anthropic: Claude Code CLI + Claude Agent SDK; OpenAI: OpenAI Agents SDK + Codex CLI; GitHub/Microsoft: Copilot CLI; Universal: Generic-via-LiteLLM). New vendors entering the agent space (e.g., Mistral, xAI) can add up to 2 adapters each before scope tightening is required.

**Protocol shape (unchanged at the boundary; split internally per ADR-006):**

- `CodingAgentAdapter` Protocol — single method `run(prompt, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult`. Public contract.
- Internal base classes (contributor-facing API, Phase 1 deliverable):
  - `InProcessAdapter` — SDK-driven (full-fidelity traces, `usage` always populated, `messages` complete).
  - `SubprocessAdapter` (ABC) — CLI-driven. Hooks: `_spawn`, `_parse_event`, `_finalize`. Same return type; some fields opportunistic (`usage` often `None`, `tool_calls` best-effort, `messages` may collapse to `[final_response]` + parsed transcript).

**`AgentRunResult` shape — required honesty fields (ADR-009 + ADR-010):**

```python
@dataclass(frozen=True)
class AgentRunResult:
    messages: list[Message]
    tool_calls: list[ToolCallTrace]
    usage: Optional[Usage]
    final_response: str
    metadata: AgentRunMetadata

@dataclass(frozen=True)
class AgentRunMetadata:
    adapter_name: str
    adapter_version: str
    agent_version: str          # underlying agent CLI / SDK version
    model: str
    seed: Optional[int]
    completeness: Literal["complete", "truncated", "partial"]   # REQUIRED — AC-CONFORMANCE-02
    mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]  # REQUIRED — AC-MCP-OBSERVE-01; 3-value enum per ratified ADR-016 (was 4-value in PRD draft; ratified 2026-05-17)
    library_version: str
```

`completeness` is **required** — if the agent exits non-zero mid-stream, the adapter MUST emit `completeness="truncated"` even if the structural shape is otherwise valid. Conformance suite verifies via injected truncation tests.

**`ToolCallTrace` Protocol-level contract:**

```python
@dataclass(frozen=True)
class ToolCallTrace:
    name: str
    args: dict[str, Any]
    result: Any                  # serialized result; None if errored
    error: Optional[str]
    latency_ms: float
    sequence_index: int
    source: Literal["adapter", "hosted_mcp"]
```

Conformance suite asserts `latency_ms > 0` for non-errored calls, `sequence_index` is monotonic per agent run, and `source` honesty is verified via fixture inspection (golden traces — AC-CONFORMANCE-01).

**Tier breakdown:**

| Tier | Adapter | Trace mechanism | MCP support | Phase |
|---|---|---|---|---|
| **Tier 1 (1st-party)** | `coding_agent/generic.py` (LiteLLM) | Direct API; full fidelity | via `mcp_servers=` arg | **Phase 1** |
| | `coding_agent/claude_code_cli.py` | `--output-format=stream-json` (live) + post-hoc CC conversation history | Yes (native CC MCP registry) | **Phase 1** |
| | `coding_agent/claude_agent_sdk.py` | OTel + SDK callbacks | Yes (in-process) | Phase 2 |
| | `coding_agent/openai_agents.py` | `StreamEvent` | via SDK config | Phase 2 |
| | `coding_agent/codex_cli.py` | JSON event stream | per Codex CLI capabilities | Phase 2 |
| | **`coding_agent/copilot_cli.py`** ⬅ promoted from "deferred" per empirical validation 2026-05-16 | `-p --output-format=json` (live) + `~/.copilot/session-state/{uuid}/events.jsonl` (post-hoc) — see ADR-013 | **Yes — `~/.copilot/mcp-config.json` + `--additional-mcp-config`** | **Phase 2** |
| **Tier 2 (community, entry-points, conformance-gated)** | `goose` (Block, Rust) | OTel exporter via library-hosted collector | Yes | Community |
| | `opencode` (sst, TS/TUI) | Hosted-MCP observation only; log-scrape fallback | Yes | Community |
| | `pi` (earendil-works, Node.js) | JSON-RPC output mode | **No MCP by design — hosted-MCP fallback does NOT apply** | Community |
| **Tier 3 (experimental, `contrib/`)** | Anything else | None; pattern reuse only | — | Out of scope |

**Tier-1 count:** 6 adapters (3 vendors × 2 + 1 universal) — within "≤2 per vendor + 1 universal" rule. Phase 1 ships 2 (Generic + Claude Code CLI); Phase 2 ships 4 (Claude Agent SDK, OpenAI Agents SDK, Codex CLI, **Copilot CLI**).

**Conformance test suite (`tests/conformance/`) — Phase 1 deliverable as CONTRACT PUBLICATION:**

The suite ships in Phase 1 not for consistency enforcement (Phase 1 has only 2 adapters — overkill for that) but as **contract publication** so community adapter authors have a runnable target from Day 1. The suite is the executable Protocol.

**Suite asserts STRUCTURE AND FIDELITY (AC-CONFORMANCE-01 + AC-CONFORMANCE-02):**

- **Structural assertions:** `AgentRunResult` shape, `ToolCallTrace` shape, `AgentRunMetadata` fields populated, `completeness` and `mcp_coverage` present.
- **Fidelity oracles:** golden-trace fixtures — JSON files recorded from deterministic mock agent runs against a fixed scenario. Each adapter under test must produce output matching the golden fixture's structure AND values, with documented allowable variations (e.g., `latency_ms > 0` rather than exact). Adapter that emits all-zero `latency_ms` or hallucinated `sequence_index` fails the suite. Adapter that lies about `source="hosted_mcp"` fails when fixture's source attribution is verified.
- **Honesty oracles for `completeness`:** suite injects truncation (kills mock subprocess mid-stream) and asserts adapter emits `completeness="truncated"`. Adapter that always claims `complete` is silently broken — oracle catches this.
- **Credential redaction:** fixture contains custom env names beyond `OPENAI_API_KEY` (e.g., `MY_CUSTOM_SECRET_*`) to verify `config.redact_env()` handles unknown shapes.

**Hosted-MCP universal trace observation (ADR-007):**

When the library spawns the MCP server the agent connects to, it records every `tools/call` server-side regardless of agent. Operates per-RF-test (Listener v3 `test_id` scoping per ADR-012). This rescues agents the library has no adapter for — as long as their tool calls flow through the library-hosted MCP server.

**Required honesty mechanisms on hosted-MCP observation:**

- **`mcp_coverage` indicator (AC-MCP-OBSERVE-01):** every `AgentRunResult` from a keyword using `mcp_servers=` populates `metadata.mcp_coverage`:
  - `complete` — agent ONLY used library-hosted MCP servers; trace truth guaranteed.
  - `library_only` — same as complete, but explicit (adapter verified no external MCP registration).
  - `external_mixed` — agent connected to BOTH library-hosted AND external MCP servers (e.g., user's `.mcp.json`-registered servers Claude Code reads, or `~/.copilot/mcp-config.json`). Library captures library-hosted half; external half is invisible. **Library refuses to claim trace truth** when `external_mixed`; metric keywords raise `IncompleteTraceError` unless user explicitly opts in via `allow_external_mcp_blind=True`.
  - `no_mcp` — agent does not use MCP (e.g., Pi); hosted-MCP fallback does not apply.
- **MCP spec version gate (AC-MCP-OBSERVE-02):** MCP observer validates the negotiated MCP spec version at session start. If outside `mcp>=1.0,<2.0`, observer raises `UnsupportedMCPVersionError`. Conformance suite injects a future-spec mock server to verify this gate fires.
- **Per-test trace scope (AC-MCP-OBSERVE-03):** MCP observer scopes traces per-RF-test by reading the Listener v3 `test_id` from RF context. Each test gets a unique library-hosted MCP server instance by default; `mcp_per_test=False` opts out with documented cross-test pollution trade-off. Listener fixture in `tests/conformance/` verifies isolation under parallel execution.

**"Agent-agnostic" claim reframe (locked):**

> **Agent-agnostic by Protocol + conformance suite + hosted-MCP observation fallback** — the library defines a single `CodingAgentAdapter` Protocol with a conformance test suite that any adapter (1st-party or community) must pass; hosted-MCP server-side observation captures tool-call truth even for agents the library has no adapter for, as long as they use library-hosted MCP servers. Adapter ceiling follows the "≤2 per vendor + 1 universal" rule (ADR-005); community adapters extend without library CI cost. Three vendors covered by end of Phase 2 (Anthropic, OpenAI, GitHub/Microsoft).

**ADR Backlog (Phase 1 deliverable to be ratified at Phase 1 close):**

10 architectural decisions surfaced during PRD authoring (ADR-005 adapter cap rule, ADR-006 Protocol class split, ADR-007 hosted-MCP universal observation, ADR-008 conformance suite fidelity oracles, ADR-009 `completeness` field requirement, ADR-010 `mcp_coverage` + `IncompleteTraceError`, ADR-011 MCP spec version gate, ADR-012 per-test MCP scope, ADR-013 Copilot CLI trace strategy, ADR-014 three-persona model + split test) are seeded in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` — to be ratified at Phase 1 close and committed to `docs/adr/`. ADR-001..004 are informed by patterns reviewed in `robotframework-agentguard` among other references (DynamicCore composition, AssertionEngine adoption, polling ban, `validate` operator disabled by default), evaluated on merit for agenteval.

### Risk Mitigation Strategy

Consolidated from scattered prior sections (Domain-Specific Constraints, elicitation findings, brief risk register). The architecture step downstream will refine into ADRs.

**Technical risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| MCP spec churn (Tasks primitive, SSE deprecation) | High | Medium | Pin `mcp>=1.0,<2.0`; isolate protocol handling to `mcp/` sub-library; capability negotiation as source of truth; MCP observer raises `UnsupportedMCPVersionError` on out-of-range (AC-MCP-OBSERVE-02 / ADR-008) |
| OTel GenAI semconv changes (experimental until ~mid-2026) | Medium | Low | Thin internal facade (`telemetry/semconv.py`); attribute-name changes = single-file update |
| LiteLLM breaking minor releases | Medium | Medium | Pin minor floor; `LLMProviderAdapter` Protocol isolates; Mock fallback keeps unit tests stable |
| Robot Framework 8.x breaking changes | Low | Medium | Pin `>=7.4,<9.0`; depend only on stable APIs (`@keyword`, Listener v3, DynamicCore) |
| Claude Agent SDK plan/billing change (2026-06-15) | Low | Low | Optional `[claude]` extra; Generic adapter remains agnostic default |
| Coding-agent CLI output-format schema drift (Claude Code, Codex, Copilot) | Medium | Medium | Pinned CLI version ranges per adapter; conformance suite golden-trace fixtures (AC-CONFORMANCE-01) catch schema drift; adapter wrappers ship, binaries assumed on `$PATH` |
| Test flakiness from agent non-determinism | High | Medium | `temperature=0` default; `Stat.Run N Times` + `Stat.Get Pass At K`; polling ban (`PollingDisallowedError`) prevents survivorship bias |
| Credential leakage in trace artifacts | Medium | High | Mandatory `config.redact_env()` pre-trace-write; CI test asserts no API-key strings in committed fixtures; conformance suite uses custom env names to verify unknown-shape redaction |
| Async-to-sync bridge edge cases (nested loops in IDE runners) | Medium | Low | Worker-thread fallback; documented; opt-in `nest_asyncio` for IDE-only |
| AI-agent productivity near-zero on training-data-rare surfaces (RF/MCP/OTel) | High | High | Explicitly named in `Domain Constraints §3` and `Product Scope > MVP throughput caveat`; re-baseline weekly; AI productivity high on docs/YAML/fixtures offsets |
| **Adapter sprawl / 1st-party ceiling breach** | Medium | High | Tier-1 capped via "≤2 per vendor + 1 universal" rule (ADR-005); new adapters require explicit Tier-1 promotion via ADR; conformance suite gates every release; community Tier-2 is the default home for new agents |
| **Hosted-MCP observation incomplete due to external MCP servers** | Medium | Medium | `mcp_coverage` indicator + `IncompleteTraceError` on `external_mixed` (AC-MCP-OBSERVE-01 / ADR-010); detection-failure default is `external_mixed` (safer than `library_only`) |
| **Per-test MCP server startup latency under heavy Pass@k re-runs** | Medium | Low | Per-test scope default (AC-MCP-OBSERVE-03); `mcp_per_test=False` opt-out for users who explicitly accept pollution trade-off; documented in cookbook |

**Market risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Competitor ships RF binding (DeepEval, Promptfoo, Inspect AI) | Medium | Medium | Editorial discipline is the moat (Sally's call); ADRs + docs + conformance suite ship as Phase 1 first-class deliverables, not "after MVP" polish |
| QA-engineer audience routes AI testing to ML/platform engineers instead | Medium | High | Dogfood loop (`AC-DOGFOOD-01`) proves real-world fit; Agent Surface Author persona (Devon, Mei) covers the org pattern where Skill/MCP authors *are* the testers |
| RF community size insufficient for "de facto standard" claim | Medium | Medium | Honest framing — Vision adopts the "de facto for RF community" wording with explicit Month-12 reframe trigger to "niche-but-deep" if installer bars miss (see `Success Criteria > Business Success`) |
| EU AI Act adoption doesn't drive tool selection | Confirmed | N/A | Already treated as atmospheric, not load-bearing (per elicitation; locked) |
| Tool Discoverability vocabulary asymmetry teaches wrong lesson for jargon-heavy domains | Medium | Low | Documented as known limitation in recipe; failure evidence hints when missed-task vocabulary is itself rare |

**Resource risks:**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Solo maintainer bus factor | High | High | Contributor onboarding (`CONTRIBUTING.md`, "good first issue", agent* portfolio docs, Mock adapter as template, `SubprocessAdapter` ABC as contributor-facing API per ADR-006, conformance suite published per ADR-008) ships as Phase 1 deliverable; bus-factor stated openly in maintenance docs; orgs needing SLA paired with fork or paid support |
| Phase 1 slip beyond +50% buffer | Medium | High | Re-baseline weekly without ceremony; cut Phase 1.5 hardening sprint by deferring `Stat.` advanced primitives, second trace backend (JSONL), recipe count to ≥4 (vs ≥8) if needed |
| Dogfood repo regression blocks library release | Medium | Medium | This is by design (`AC-DOGFOOD-01`) — feature, not bug. The dogfood gate forces real-world correctness. Mitigation: keep dogfood repo CI suites tight and well-isolated so regressions are diagnosable in ≤ 1 day |
| Judge calibration in Phase 2 turns out to be a research problem, not a sub-library | Medium | Medium | Phase 2 ships single-judge `Judge.Get Score` with explicit calibration cookbook; multi-judge ensembles and advanced calibration deferred to Phase 2+ / Phase 3 |

## Functional Requirements

Each FR states the testable, observable capability the library must provide. Format: `FR# Actor can <capability>` + (where load-bearing) the specific keyword call, error type, or output shape that proves the FR is satisfied. Tier and Phase annotations are inline. No "per AC-X" pointer-style FRs (testability rule — Amelia's call, applied globally) — ACs define pass/fail criteria; FRs define the observable behavior. The conformance suite (FR45) is the executable enforcement of the FR↔AC contract.

### 1. Static Agent-Surface Inspection (Tier 1, Phase 1)

- **FR1:** Agent Surface Author can call `Skill.Get Frontmatter <path.md>` and receive a dict containing the parsed YAML frontmatter; missing or malformed frontmatter raises `InvalidSkillFrontmatterError` with the file path, line number, and field name at fault.
- **FR2:** Agent Surface Author can call `Skill.Get Frontmatter <path.md>` with the AssertionEngine matcher `Should Be Valid Frontmatter` (validates `name`, `description`, `allowed-tools`, `disable-model-invocation` per Claude Code skill schema) or with `contains` / `matches` operators against any field via `Skill.Get Description`, `Skill.Get Allowed Tools`, `Skill.Get Disable Model Invocation`.
- **FR3:** Agent Surface Author can call `Subagent.Get Frontmatter <path.md>` against `.claude/agents/*.md` files and receive the parsed sub-agent definition (validates `name`, `description` per the Claude Code sub-agent schema as required fields; `tools`, `model` optional with type-checks; ratified Story 2.2 code-review 2026-05-19 to match FR2's explicit-schema shape); same matcher surface as `Skill.Get Frontmatter`. Missing or malformed frontmatter raises `InvalidSubagentDefinitionError`.
- **FR4:** Agent Surface Author can call `Hook.Get Config <settings.json path>` and receive a dict mapping `hooks.<event>` → list of hook entries (`command`, `args`, `timeout`, `matcher`); supports `PreToolUse`, `PostToolUse`, `Stop` events and inline-skill-frontmatter hooks.
- **FR5:** Agent Surface Author can call `MCP.Get Server Config <.mcp.json path>` and receive a dict of declared MCP servers: keys are server names; each entry contains `command` (required), plus optional `args`, `env`, `transport` (per FR7's `stdio | streamable_http | in_memory` enum), and optional `tools` (Phase-1 declarative tool-schemas per FR6 carve-out). The returned dict starts no server processes. (Ratified Story 2.3 code-review 2026-05-19 to disambiguate "(`name`, `command`, ...)" — `name` is the outer dict KEY mapping `server_name → entry`, NOT a field in each entry.)
- **FR6:** Agent Surface Author can call `MCP.Get Tool Schema <tool_name>` against a running or configured MCP server and receive the JSON Schema for tool input; `MCP.Validate Tool Schema <tool_name>` raises `InvalidMCPToolSchemaError` with the JSON Pointer and validation error message if the schema is malformed.

### 2. MCP Server Dynamic Evaluation (Phase 1)

- **FR7:** Agent Surface Author can call `MCP.Start Server <command> <args>... transport=<stdio|streamable_http|in_memory>` and receive a server handle; library spawns the server subprocess (or in-process instance for `in_memory`) with per-test scope by default (see FR40).
- **FR8:** Agent Surface Author can call `MCP.Connect To Server <handle|url>` and receive a client connection; library negotiates MCP spec version and raises `UnsupportedMCPVersionError("MCP server version <X> outside library tested range mcp>=1.0,<2.0")` on out-of-range. (Story 3.1 code-review Auditor HIGH 2026-05-19: amended to include leading `MCP ` prefix — semantically clearer for end users than the pre-edit "server version <X>" wording, and matches the shipped Story 3.1 implementation byte-for-byte.)
- **FR9a:** Agent Surface Author can call `MCP.List Tools <handle>` and receive an ordered list of `MCPTool` records (`name`, `description`, `input_schema`, `output_schema`). The field-projection convenience keywords `Get Tool Names` / `Get Tool Descriptions` are deferred to Phase-1.5 (Story 3.2 code-review Auditor HIGH 2026-05-19: PRD originally named both projection keywords inline with FR9a; Story 3.2 implements only `MCP.List Tools` because AssertionEngine + native Python list-comprehension + `${tools[*].name}` index access cover the documented use case without a dedicated keyword. Phase-1.5 may re-introduce as convenience keywords if .robot-test ergonomics warrant — tracked in `deferred-work.md`).
- **FR9b:** Agent Surface Author can call `MCP.Call Tool <handle> <tool_name> <args_dict>` and receive an `MCPToolResult` (`content` list of MCP content blocks per spec, `is_error` mirroring the SDK's `CallToolResult.isError`, `error_message` extracted from the first text-content block when `is_error=True`, `latency_ms` wall-clock for the SDK round-trip, `correlation_id` per-call uuid4 hex Phase-1 placeholder for Epic 5 trace-id wiring); same call supports AssertionEngine matchers (`Should Contain`, `matches`, `Should Match Schema`) against `content`. (Story 3.2 code-review Auditor HIGH 2026-05-19: amended from pre-edit `(result, error, latency_ms)` shape to match the 5-field implementation that ships in `src/AgentEval/mcp/lifecycle.py:MCPToolResult` — same pattern as Story 3.1's FR8 prefix amendment. Pre-edit shape was too narrow: `content` is a LIST of typed blocks per MCP spec, not a scalar `result`; tool-level error responses surface as `is_error=True` first-class data per FR9b semantic intent, distinct from infrastructure failure which raises `MCPConnectionLostError`; per-call `correlation_id` ships now so Epic 5 trace wiring doesn't require a breaking API change.)
- **FR10a:** Agent Surface Author can call `MCP.Get Tool Discoverability tool=<name> by_models=<list> with_tasks=<list> k=<n>` against a single coding-agent runtime and receive a `ToolDiscoverabilityResult` containing per-model selection rate (Wilson CI), per-task verdict matrix, failed-task prompts, competing tools picked, and docstring snippet under test (Tier 3, Phase 1; single-runtime version).
- **FR10b:** Agent Surface Author can compare `ToolDiscoverabilityResult` across ≥2 coding-agent runtimes via `MCP.Compare Tool Discoverability runtime_a=<adapter> runtime_b=<adapter>` and receive a cross-runtime delta with statistical significance (Mann-Whitney U) — **Phase 2** (depends on ≥2 fully-shipped Tier-1 runtimes; Phase 1 has only Generic + CC CLI where Generic is a thin LiteLLM stub).
- **FR11:** Library raises `CostExceededError("projected $X.XX > max_cost_usd=$5.00; raise limit or reduce task_list")` pre-flight if the projected cost for a fanned-out keyword exceeds `max_cost_usd` (default 5.00 USD); during execution, the cumulative cost meter hard-stops with `CostExceededError("$X.XX exceeded $Y.YY=1.1× max_cost_usd")` at 1.1× the limit. Verifiable via `Stat.Run N Times 10 max_cost_usd=0.01 ...` against a deterministic mock provider.
- **FR11b (time guardrail — sibling to FR11):** Library exposes `max_runtime_seconds` keyword argument (default `None` — no time cap; opt-in) on Tier-3 fan-out keywords (`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`). When set, library performs a pre-flight wall-clock estimate (`mcp_startup_estimate × n_servers × n_trials + agent_runtime_estimate × n_trials`) and raises `RuntimeBudgetExceededError("projected XXs > max_runtime_seconds=YY; reduce trials, use mcp_per_test=suite, or raise limit")` pre-flight; mid-run wall-clock meter hard-stops at 1.1× declared limit. Orthogonal to FR11: cost guard catches token spend; time guard catches latency under heavy MCP servers (e.g., `rf-mcp` / `robotmcp` take several seconds to start; multiplied across trials this can silently blow runtime budgets). Verifiable via `Stat.Run N Times 20 max_runtime_seconds=5 ...` against a deterministic slow-mock provider.

### 3. Agent Run Orchestration & Adapter Ecosystem

- **FR12 (Protocol):** Library exposes a `CodingAgentAdapter` Protocol with single method `run(prompt, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult`; internal base classes `InProcessAdapter` and `SubprocessAdapter(ABC)` are part of the public contributor-facing API (importable from `agenteval.coding_agent`).
- **FR13a:** Agent Developer can use `coding_agent/generic.py` (LiteLLM-backed) in Phase 1, with `LLMProviderAdapter` Protocol composition for any of 140+ LiteLLM-supported providers including local Ollama / vLLM.
- **FR13b:** Agent Developer can use `coding_agent/claude_code_cli.py` in Phase 1; adapter validates `claude` binary on `$PATH` and raises `UnsupportedBinaryVersionError` if outside the pinned range; parses `--output-format=stream-json` live + falls back to post-hoc CC conversation history.
- **FR13c:** Agent Developer can use `coding_agent/claude_agent_sdk.py` in Phase 2 (subprocess JSON-lines bridge + in-process MCP-tool support).
- **FR13d:** Agent Developer can use `coding_agent/openai_agents.py` in Phase 2 (`Runner.run_streamed` + stream-event capture).
- **FR13e:** Agent Developer can use `coding_agent/codex_cli.py` in Phase 2 (JSON event stream from Codex CLI; pinned binary version).
- **FR13f:** Agent Developer can use `coding_agent/copilot_cli.py` in Phase 2; adapter uses live `-p --output-format=json` + post-hoc `~/.copilot/session-state/{uuid}/events.jsonl`; MCP support via library-augmented `~/.copilot/mcp-config.json` (`--additional-mcp-config`); pinned `copilot` CLI `>=1.0.9,<2.0` per ADR-013.
- **FR14:** Agent Developer can call `Send Prompt <agent> <prompt>` against a connected coding agent and receive an `AgentRunResult` with all required fields populated per FR36a/FR36b.
- **FR15:** Agent Developer can call `Run Scenario <yaml_path>` to execute a declarative evaluation scenario; scenario YAML specifies `model`, `provider`, `agent`, `mcp_servers`, `evals[]` with `prompt`, `repeat`, `expect:` block (per-keyword thresholds), optional `judge:` block (Phase 2).
- **FR16:** Agent Developer can configure MCP servers per agent run via `mcp_servers=` keyword argument; library hosts them with per-test scope (FR40) and observes their `tools/call` traffic server-side (FR35).
- **FR17a (entry-points):** Contributor can register a custom `CodingAgentAdapter` implementation via `[project.entry-points."agenteval.coding_agents"]` in `pyproject.toml`; library auto-discovers and exposes it via `coding_agent=<name>` keyword arg.
- **FR17b (composition):** Contributor can pass a custom `CodingAgentAdapter` instance directly via `__init__(coding_agent=MyAdapter())` for one-off / org-internal use without packaging.
- **FR17c (Provider Protocol):** Contributor can register a custom `LLMProviderAdapter` via `[project.entry-points."agenteval.providers"]` OR pass directly via `__init__(provider=MyProvider())`.
- **FR18 (scaffolding):** Contributor can run `agenteval new-adapter <name> --base <InProcessAdapter|SubprocessAdapter>` and receive a generated adapter skeleton with conformance-suite stubs pre-wired (Phase 1 — lowers the bar for community Tier-2 adapter contributions).

### 4. Tool-Call Metrics & Trajectory Analysis (Phase 1)

- **FR19:** Agent Developer can call `Metric.Get Tool Call Count <run>` returning `int`; `Metric.Get Tool Call Names <run>` returning `list[str]` (preserving order); both accept AssertionEngine matchers.
- **FR20:** Agent Developer can call `Metric.Get Tool Hit Rate <run> <expected_tools>` returning `float` (fraction of expected tools that appeared in the trajectory) and `Metric.Get Tool Success Rate <run>` returning `float` (fraction of non-errored tool calls).
- **FR21:** Agent Developer can call `Metric.Get Unnecessary Call Rate <run> <expected_tools>` returning `float` (fraction of tool calls outside the expected set).
- **FR22:** Agent Developer can call `Metric.Get Token Usage <run>` returning `Usage(input, output, total)`; `Metric.Get Latency <run>` returning mean turn-level latency in ms; `Metric.Get Latency P95 <run>` returning P95 latency; `Metric.Get Cost Total <run>` returning USD cost.
- **FR23a:** Agent Developer can call `Trajectory Should Match <run> <expected_sequence>` (core keyword, paired with `Get Trajectory`) supporting three documented match modes (defaults to `mode=exact`): `mode=exact` (ordered, no extras), `mode=subsequence` (ordered, extras allowed), `mode=set` (unordered, no extras).
- **FR23b:** Agent Developer can pass `mode=regex` to `Trajectory Should Match` to match each step against a regex pattern over the tool-call name + serialized args.
- **FR24:** QA Engineer can call `Tool Call Should Have Occurred <run> tool=<name> [args=<dict>]` to assert a specific tool call appeared during an agent run, optionally with specified arguments.
- **FR25:** QA Engineer can call `Agent Response Should Contain <run> <substring>`, `Agent Response Should Match Regex <run> <pattern>`, or `Agent Response Should Match Schema <run> <jsonschema>`.

### 5. Statistical Evaluation & Three-Tier Determinism Model (Phase 1; advanced Phase 2)

- **FR26:** Agent Developer can call `Stat.Run N Times <n> <keyword> <args>...` and receive `list[KeywordRun]`; library guarantees independent samples (fresh agent instance per run; no state leakage).
- **FR27:** Agent Developer can call `Stat.Get Pass At K <runs> k=<int>` and receive `float ∈ [0, 1]` computed via the HumanEval unbiased estimator (`1 - C(n-c, k) / C(n, k)`); accepts AssertionEngine matchers (`>=`, `<=`, etc.).
- **FR28:** Library raises `PollingDisallowedError` (verbatim text per frontmatter PollingDisallowedError revised wording entry) whenever a Tier-2 or Tier-3 keyword receives `polling=` argument. Verifiable via `Run Keyword And Expect Error PollingDisallowedError* Skill.Get Activation Decision polling=1s` in `tests/conformance/`.
- **FR29a (Phase 2 — `agenteval-advanced` extras):** Agent Developer can call `Stat.Mann Whitney U <runs_a> <runs_b>` returning `MannWhitneyResult(u_statistic, p_value, effect_size_r)`; FR is observable Phase 2 only — the extras package's import surface is the test target.
- **FR29b (Phase 2):** Agent Developer can call `Stat.Cliff Delta <runs_a> <runs_b>` returning `float ∈ [-1, 1]`.
- **FR29c (Phase 2):** Agent Developer can call `Stat.Bootstrap Confidence Interval <samples> statistic=<callable> alpha=0.05` returning `(lo, hi)` tuple.
- **FR30a (tier model):** Library categorizes every `@keyword`-decorated method into Tier 1 / 2 / 3 via metadata; `Get Keyword Tier <keyword_name>` returns the tier; libdoc renders the tier badge in keyword reference. Verifiable via reflection on the keyword registry.
- **FR30b (ACL gates):** Library raises `TierViolationError` if a Tier-1 keyword attempts to invoke an LLM provider or `validate` operator without explicit opt-in; verifiable via reflection on the keyword dispatcher.
- **FR31a (determinism — Tier 1):** Library guarantees bit-identical output across runs of any Tier-1 keyword given identical inputs; verifiable via `Assert Run Determinism <keyword> <args> expect=byte_identical` in conformance suite.
- **FR31b (determinism — Tier 2/3):** Library guarantees statistical interpretability for Tier-2/Tier-3 reruns via `Stat.Run N Times` + `Stat.Get Pass At K`; library does NOT promise bit-identical traces, cross-model-version reproducibility, or cross-provider equivalence — verifiable via the Determinism Contract document (FR63) published with each release.

### 6. Trace Recording & Observability

- **FR32:** Library emits OpenTelemetry GenAI-conformant spans for every agent run (`invoke_agent → chat → execute_tool`); span hierarchy + `gen_ai.*` attribute coverage verifiable via `Get Run Spans <run>` returning a `list[Span]` and conformance-suite span-shape assertions.
- **FR33a (Listener):** Library registers `agenteval.telemetry.otel_listener:OTelListener` via `[project.entry-points."robot.listener"]`; opt-in via `__init__(telemetry=True)` (default on).
- **FR33b (backends):** Library emits trace artifacts to `memory` backend by default + `jsonl` backend (Phase 1) + `otlp` backend (Phase 2 via `[otlp]` extra); verifiable via `Get Trace Backend Names` returning configured backends.
- **FR34a (evidence-block format):** Every assertion keyword writes a self-contained evidence block to the Robot Framework log on both pass and fail in the format documented in `docs/contracts/evidence-block-format.md` — header line, threshold-vs-observed table, raw-artifact section (response / trajectory / tool-call trace); verifiable via `Get Last Evidence Block <keyword>` returning parsed sections (`AC-SIMPLICITY-01`).
- **FR34b (visual contract):** The evidence-block visual contract specifies: monospace fenced section with header `┌─ EVIDENCE ─┐ <keyword> <PASS|FAIL> ─┐`, three sub-sections (`Compared:`, `Observed:`, `Raw:`), and uniform truncation (`...` after 1000 chars per field with link to full artifact). Verifiable via the conformance suite's evidence-block-format snapshot fixtures.
- **FR35:** Library performs server-side observation of `tools/call` invocations on every MCP server it spawns (regardless of which agent invoked them), populating each `ToolCallTrace.source` field with `"hosted_mcp"`; adapter-side trace extractions populate `source="adapter"`. Verifiable via `Get Tool Call Sources <run>` returning the `set[str]` of sources present.
- **FR36a (`completeness` field):** Every `AgentRunResult.metadata.completeness` field is REQUIRED and adapter MUST emit `"truncated"` when the agent exits non-zero mid-stream or its event parser fails to reach a terminal event. Verifiable via `Run Keyword With Mock Agent killed_at=mid_stream Send Prompt ...` + assertion that the resulting `AgentRunResult.metadata.completeness == "truncated"`.
- **FR36b (`mcp_coverage` field):** Every `AgentRunResult.metadata.mcp_coverage` field from a keyword using `mcp_servers=` is REQUIRED and is one of `"hosted_in_process"`, `"subprocess_with_observer"`, `"external_mixed"` (3-value enum per ratified ADR-016 D1 trust-floor + D4 adapter contract, 2026-05-17; PRD draft used 4-value enum — superseded). Verifiable via `Run Keyword With External MCP Server Send Prompt ...` + assertion that the resulting `mcp_coverage == "external_mixed"`.
- **FR37:** Library raises `IncompleteTraceError("metric keyword <name> called on AgentRunResult with mcp_coverage=external_mixed; opt in via allow_external_mcp_blind=True or ensure all MCP traffic flows through library-hosted servers")` when metric keywords are called against an `AgentRunResult.metadata.mcp_coverage == "external_mixed"` without `allow_external_mcp_blind=True`. Verifiable via the same fixture as FR36b + `Run Keyword And Expect Error IncompleteTraceError*`.
- **FR38a (trace-side redaction):** Library redacts known credentials (LiteLLM-standard env names + custom patterns registered via `config.add_redaction_pattern(<regex>)`) from all trace artifacts before serialization to any backend (memory snapshot, JSONL file, OTLP export). Verifiable via the conformance suite's redaction fixture (env names beyond `OPENAI_API_KEY` to verify unknown-shape redaction).
- **FR38b (config-source redaction):** Same `config.redact_env()` mechanism applies to env-var snapshots in `Get Effective Config` output (FR41) so env-dump operations never leak secrets.
- **FR39 (Run Manifest):** Library emits a `RunManifest` JSON artifact alongside every evaluation report; manifest contains seeds, adapter name + version, MCP server names + versions/SHAs, prompt hashes, library version, redaction-policy hash, RF Listener test_id, ISO 8601 timestamp. Path: `${OUTPUT_DIR}/agenteval/manifest__<suite>__<test>.json`. Verifiable via `Get Run Manifest <run>` returning the parsed dict + conformance suite asserting all required fields are populated.
- **FR40 (per-test MCP scope):** MCP observer scopes traces per-RF-test by reading Listener v3 `test_id` from RF context; each test gets a unique library-hosted MCP server instance by default; `__init__(mcp_per_test=False)` opts out with documented pollution trade-off. Verifiable via `pabot --processes 2` parallel-test fixture in conformance suite asserting no cross-test trace pollution.

### 7. Configuration & Provider/Agent Extensibility (Phase 1)

- **FR41:** Library resolves configuration via the precedence chain (highest wins): library `__init__` args → environment variables → `.env` file at project root → defaults. User can call `Get Effective Config` and receive `dict[str, ConfigValue]` where each `ConfigValue` has `value` + `source: Literal["init_arg", "env", "dotenv", "default"]`. Verifiable via test that sets a value at each source level + asserts `Get Effective Config[key].source == expected`.
- **FR42:** Defaults: `provider="litellm"`, `telemetry=True`, `trace_backend="memory"`, `allow_validate_operator=False`, `default_temperature=0.0`, `mcp_per_test=True`, `allow_external_mcp_blind=False`, `max_cost_usd=5.00`. Verifiable via `Get Effective Config` on a freshly-initialized library with no overrides.
- **FR43:** Library exposes `__init__(allow_validate_operator=True)` to enable the AssertionEngine `validate` operator (which uses `eval()`); default `False`. Verifiable via `Run Keyword And Expect Error ValidateOperatorDisallowed* <getter> validate <expr>` when `allow_validate_operator=False`. (Class name ratified `ValidateOperatorDisallowed` per ADR-014 2026-05-17; PRD draft used `ValidateOperatorDisabledError` — superseded.)
- **FR44:** Library exposes `__init__(telemetry=False)` to disable the OTel listener; when disabled, `Get Trace Backend Names` returns `[]` and no network egress occurs to OTLP endpoints (Phase 2). Verifiable via `Assert No Egress To` fixture in conformance suite when `telemetry=False`.

### 8. Conformance & Compatibility Contracts (Phase 1)

- **FR45:** Library publishes a runnable conformance test suite at `tests/conformance/` as a public deliverable. Users can run it via `python -m agenteval.conformance` (returns exit 0 on green); adapter authors can run it against their custom adapters via `python -m agenteval.conformance --adapter my_adapter` (exits non-zero on failure with structured report). The suite asserts: (a) `AgentRunResult` shape per FR14/FR36; (b) `ToolCallTrace` shape per FR35; (c) `latency_ms > 0` for non-errored calls; (d) `sequence_index` monotonic per agent run; (e) `source` field honesty via fixture inspection; (f) `completeness="truncated"` injection (FR36a); (g) `mcp_coverage` detection (FR36b); (h) credential redaction on custom env name patterns (FR38a).
- **FR46:** MCP observer raises `UnsupportedMCPVersionError` per FR8 on negotiated MCP spec versions outside `mcp>=1.0,<2.0`; verifiable via conformance fixture using a mock MCP server negotiating spec version `2.5.0`.
- **FR47:** Each CLI adapter (Claude Code CLI, Codex CLI, Copilot CLI) raises `UnsupportedBinaryVersionError("<binary> version <X> outside tested range <range>")` at adapter instantiation if the vendor binary on `$PATH` is outside the pinned tested range; library never downloads, installs, or auto-updates vendor binaries.
- **FR48:** Contributor can load custom plugin classes via `__init__(plugins=[MyMetricsClass(), MyAssertionsClass()])`; library auto-discovers `@keyword`-decorated methods and registers them under a configurable namespace prefix. Verifiable via `Get Library Instance` returning the plugin's keywords in the keyword registry.

### 9. Reporting, CI Integration & First-Run Experience

- **FR49 (JUnit XML):** Library emits JUnit-compatible XML report alongside `output.xml` via `--listener agenteval.reporting.junit_listener:JUnitListener` (opt-in) for CI systems consuming JUnit XML. Schema conforms to the de facto JUnit XML spec; one `<testsuite>` per RF suite; one `<testcase>` per RF test.
- **FR50 (non-zero exit codes):** RF execution exits with sysexits.h-style per-leaf codes (ratified 2026-05-18 per Story 1a.4 code-review HIGH-6; PRD draft used family codes 1/2/3 — superseded). Phase-1 pinned: `1` = generic assertion failure; `65` = `PollingDisallowedError`; `66` = `CostExceededError`; `67` = `IncompleteTraceError`; `68` = `UnsupportedMCPVersionError`. Remaining `AgentEvalError` leaves get sysexits.h-aligned codes assigned by Epic 8a Story 8a.1 (canonical table at `docs/contracts/error-class-hierarchy.md`). Verifiable via subprocess invocation + exit-code assertion in conformance suite.
- **FR51 (trace ID in report):** Every test's RF report line includes a `trace_id=<uuid>` attribute linking to the trace artifact at `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl`. Verifiable via parsing `output.xml` and asserting every `<test>` element has a `trace_id` attribute.
- **FR52 (`agenteval init`):** User can run `agenteval init [--template basic|skill|mcp|scenario]` in an empty directory and receive a working `.robot` test, an `agenteval.yaml` scenario file, a `.env.example` template, and a one-line `README.md` pointing to the recipe gallery. Default template (`basic`) targets a bundled echo MCP server and runs without API keys.
- **FR53 (`agenteval new-adapter`):** Covered by FR18 above; cross-referenced here as part of the first-run / scaffolding experience.
- **FR54 (terminal run summary):** After every `robot` invocation, library writes a human-readable run summary to stderr (configurable to stdout via `__init__(summary_stream="stdout")`) containing pass/fail counts, total cost in USD, time-to-first-test, and a "next step" hint when failures occur. Verifiable via subprocess invocation + stderr regex assertion in conformance suite.
- **FR55 (cohort heatmap format):** `Metric.Get Cohort Heatmap <ToolDiscoverabilityResult>` (and equivalent for any multi-cohort metric) returns a `CohortHeatmap` object with `as_ascii() -> str` (default terminal output: ✓/✗/• with model rows × task-cluster columns), `as_html() -> str` (Phase 2), `as_dict() -> dict` (machine-readable). Verifiable via fixture matching the documented ASCII format.
- **FR56 (polling-error testability checklist):** The `PollingDisallowedError` text MUST contain (a) the keyword name that was called with `polling=`, (b) the offending RF test file path + line number from the call stack, (c) the exact remediation snippet (verbatim `${runs}=  Stat.Run N Times ...` example), and (d) the ADR link. Verifiable via conformance suite asserting all 4 elements present in the raised error message.
- **FR57 (conformance-report shape):** `python -m agenteval.conformance --adapter <name>` emits a structured JSON report on stdout (machine-readable) and a human-readable summary on stderr (pass/fail count + first 5 failure summaries + link to full report). Verifiable via subprocess invocation in CI-flavored conformance test.
- **FR58 (visual contract for OTel trace):** Library publishes a sample OTel trace visualization (Jaeger / Grafana Tempo screenshot + documented field mapping) at `docs/contracts/otel-trace-visual.md`. The contract specifies which `gen_ai.*` attributes appear in the trace UI and which appear only in JSONL/OTLP exports. Documentation deliverable; verifiable via doc-build CI asserting the file exists with required sections.
- **FR59 (Tier-1 setup-failure diagnostics):** All Tier-1 keyword setup failures (file not found, parse errors, schema errors, missing MCP server config) raise structured errors with (a) the input path + filename, (b) the offending line number when applicable, (c) a one-sentence remediation hint. Verifiable via conformance fixtures injecting each error class + asserting all 3 elements present.

### 10. Honest Failure Reporting (cross-cutting)

- **FR60:** Library MUST surface adapter version drift detected at runtime via a one-time warning logged through the RF Listener: `AdapterVersionDriftWarning("<adapter> binary version <X> matches pinned range but is <Y> versions behind tested; conformance fidelity may degrade")`. Phase 2 — reachable when ≥2 Tier-1 CLI adapters ship.
- **FR61:** Library MUST emit a `DegradedTraceWarning` if hosted-MCP observation detects partial-stream interruption mid-run (e.g., agent-side connection drop) WITHOUT raising — `mcp_coverage` is set to `partial` and metric keywords get the warning but don't refuse. Distinguishes recoverable partial from external-mixed.
- **FR62:** `Get Last Warnings <run>` returns the list of warnings emitted during the run with source + message + remediation. Verifiable via fixture intentionally triggering each warning class.

### 11. Determinism Contract & Stability Surface (documentation deliverables)

- **FR63:** Library publishes a Determinism Contract document at `docs/contracts/determinism-contract.md` covering the promises and non-promises enumerated in `## Domain-Specific Constraints > 5. Determinism Contract`. Verifiable via doc-build CI asserting the file's required sections exist and the single-paragraph summary is byte-identical to the PRD source.
- **FR64:** Library publishes a Stability Surface document at `docs/contracts/stability-surface.md` labeling each public surface (keyword, Protocol, error class, scenario YAML schema, adapter file path) as `stable` / `provisional` / `experimental`. Updated per release. Verifiable via doc-build CI asserting every public-API element has exactly one stability label.
- **FR65:** Library publishes an evolving 0.x → 1.0 Exit Criteria document at `docs/contracts/exit-criteria-0x-to-1x.md` (preliminary stub in PRD `## Developer Tool — Specific Requirements > 0.x → 1.0 Exit Criteria (stub)`). Final criteria authored at Phase 1 close.

## Non-Functional Requirements

Specific, measurable quality attributes the library must achieve. Some consolidate bars already named in upstream sections (Success Criteria > Technical Success, Domain Constraints, Risk Mitigation) — the NFR section is the single source of truth for the bars themselves. FRs say *what* the library does; NFRs say *how well*.

### Performance

- **NFR-PERF-01:** Time-to-first-test ≤ 5 minutes on the published happy-path cohort (Linux or macOS dev machine, Python ≥3.12, `uv` pre-installed, Tier-1 keywords only, no API keys, bundled echo MCP server). Measured by a CI smoke job that executes the README walkthrough end-to-end and asserts elapsed time. **Release-blocking** if bar missed on the gated CI matrix.
- **NFR-PERF-02:** Tier-1 (static-inspection) keyword execution: median ≤ 50 ms per keyword call on typical file sizes (5 KB skill `.md`; 10-tool MCP server config; sub-agent `.md`; hook entry in `settings.json`). Measured by library-internal `tests/benchmarks/` suite; regression of >2× threshold blocks release.
- **NFR-PERF-03a (bundled echo MCP server):** Library-controlled bundled echo MCP server startup ≤ 200 ms median on Linux/macOS. This is library-internal — must stay lightweight by design to support the 5-min time-to-first-test bar (NFR-PERF-01). Measured by CI smoke job.
- **NFR-PERF-03b (user-provided MCP servers under test):** Library does NOT impose a startup-latency cap on user-provided MCP servers. Real-world first-party servers (`rf-mcp`, `robotmcp`, `robotframework-agentskills`-shipped servers, etc.) take **several seconds** to start because they bootstrap Robot Framework + library state + MCP protocol handshake. This is acknowledged and accepted, NOT a defect.
- **NFR-PERF-03c (MCP protocol handshake after server startup):** Once the server process is up, the MCP `initialize` + capability negotiation handshake completes within ≤ 500 ms median. This is library/SDK-controlled and is bar-able. Measured via fixture timing the time between server-handle ready and first usable connection.
- **NFR-PERF-03d (per-test scope cost trade-off documented):** Under the default `mcp_per_test=True` (FR40 / AC-MCP-OBSERVE-03), every RF test pays the server startup cost. For heavy servers this is several seconds per test → minutes of overhead for a 30-test suite. Three-mode trade-off matrix published in the cookbook + Recipe Gallery #5 (dogfood replacement):
  - `mcp_per_test=True` (default) — full per-test isolation; expensive for heavy servers.
  - `mcp_per_test="suite"` (NEW value) — one server per RF suite, reused across tests in that suite. Tests in the same suite see interleaved trace events; `mcp_coverage` set to `library_only` if no external MCP detected, but `Get Tool Calls` calls require the user to filter by `test_id` themselves. Documented trade-off: 10× cost reduction at the cost of per-test trace cleanliness.
  - `mcp_per_test=False` — single global server reused across the whole RF execution; per-test pollution explicit; safest for explicit-opt-in only.
- **NFR-PERF-04:** Cost guardrail accuracy: pre-flight cost estimate within ±20% of actual realized cost on Tier-3 fan-out keywords (`MCP.Get Tool Discoverability` and future multi-model keywords); mid-run hard-stop fires within 10% of the declared `max_cost_usd` limit. Measured by cost-meter unit tests against deterministic mock provider.
- **NFR-PERF-05:** Concurrent execution under `pabot --processes N` produces no cross-test trace pollution; per-test MCP server isolation verified up to N=8 in conformance suite **when using the bundled echo server**. For heavy MCP servers (multi-second startup), users are documented to consider `mcp_per_test="suite"` or `mcp_per_test=False` opt-outs with the trade-off matrix from NFR-PERF-03d. Conformance suite includes a "heavy server simulation" fixture (intentionally `time.sleep(3)` on startup) that asserts the opt-out paths function correctly and that pre-flight cost / runtime estimates account for startup latency.
- **NFR-PERF-06 (time guardrail):** Library exposes `max_runtime_seconds` keyword argument (default `None` — no time cap; opt-in) on Tier-3 fan-out keywords (`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`). When set, library performs a pre-flight estimate (`mcp_startup_estimate × n_servers × n_trials + agent_runtime_estimate × n_trials`) and raises `RuntimeBudgetExceededError("projected XXs > max_runtime_seconds=YY; reduce trials, use mcp_per_test=suite, or raise limit")` pre-flight; mid-run wall-clock check fires at 1.1× declared limit. Parallels the `max_cost_usd` guardrail (FR11 / NFR-PERF-04) for time-budget defense. Captured as `FR11b` in Functional Requirements.

### Reliability

- **NFR-REL-01:** `tests/unit/` pass rate ≥ 99% across the gated CI matrix (Python 3.12 + 3.13 on Linux + macOS) on every PR. **Release-blocking** if violated. Tracked via GitHub Actions matrix results.
- **NFR-REL-02:** `tests/acceptance/` smoke-tag pass rate = 100% on every release-tag CI run. **Release-blocking** if any smoke test fails.
- **NFR-REL-03:** `tests/integration/` (live `@pytest.mark.live`) pass rate ≥ 95% in nightly cron CI. Below-bar nightly results trigger triage within 1 business day; sustained below-bar (3+ consecutive nights) blocks next release until root cause is identified.
- **NFR-REL-04:** External dependency pinning posture documented per release in CHANGELOG: every external dep has a pinned floor and ceiling (or unconstrained ceiling with rationale); deprecation-watch posture for MCP spec, OpenTelemetry GenAI semconv, LiteLLM minor releases, and each coding-agent SDK/CLI documented and reviewed at each release.
- **NFR-REL-05:** Dogfood loop integrity (`AC-DOGFOOD-01`): `rf-mcp` and `robotframework-agentskills` CI runs against every released version of the library within 24h of publication; regression in either dogfood repo blocks the next release until library-side fix or scope cut is committed.

### Security

- **NFR-SEC-01:** Library never persists user-provided credentials (API keys, OAuth tokens) to disk or trace artifacts in their original form. All credentials routed through `config.redact_env()` (and user-extensible patterns via `config.add_redaction_pattern()`) before any serialization. CI test asserts no known API-key strings or custom patterns appear in any committed fixture; conformance suite verifies unknown-shape redaction (FR38a).
- **NFR-SEC-02:** Library never executes `eval()` on user-provided strings except via the explicitly-opted-in AssertionEngine `validate` operator (`__init__(allow_validate_operator=True)`, default `False`, FR43). All other AssertionEngine matchers use safe comparison operators. CI test asserts no `eval()` calls exist on user input paths in default-configured library.
- **NFR-SEC-03:** All LLM provider traffic uses TLS in transit (delegated to LiteLLM / provider SDKs); library does NOT relax certificate validation or expose any HTTP-without-TLS opt-out. MCP transports use TLS for Streamable HTTP; `stdio` and in-memory transports are local-process-only by design.
- **NFR-SEC-04:** Vendor CLI binaries (`claude`, `codex`, `copilot`, `goose`, `pi`, `opencode`) are never auto-downloaded, installed, or auto-updated by the library; user explicitly installs binaries (FR47). Supply-chain trust boundary documented in `SECURITY.md`: library trusts the binary on `$PATH` to the same level the user does.
- **NFR-SEC-05:** Library does NOT phone home. Only LLM provider endpoints (per user-configured providers) and OTLP endpoints (Phase 2, opt-in via `[otlp]` extra + explicit endpoint config) generate network egress. `__init__(telemetry=False)` eliminates all OTel listener egress. Conformance suite verifies via `Assert No Egress To` fixture in default-configured + `telemetry=False` configurations.

### Integration & Compatibility

- **NFR-COMPAT-01:** Python compatibility: 3.12 and 3.13 are Tier-1 (gated CI matrix on Linux + macOS); future 3.14+ tested in CI but not gated until upstream stable release. Python <3.12 explicitly unsupported; `pyproject.toml` `requires-python = ">=3.12"` enforces at install time.
- **NFR-COMPAT-02:** Robot Framework compatibility: `>=7.4,<9.0`. Library depends only on stable RF APIs (`@keyword` decorator, Listener v3, DynamicCore via `robotframework-pythonlibcore`). RF 8.x.beta pre-release testing in CI is a Phase 2 deliverable. RF <7.4 explicitly unsupported.
- **NFR-COMPAT-03:** Operating-system support: Linux and macOS are first-class (Tier-1 gated CI matrix); Windows is best-effort with documented troubleshooting in the first-day guide (no CI gate; community-tested). FreeBSD and other Unixes are community-effort unsupported. WSL2 on Windows behaves as Linux.
- **NFR-COMPAT-04:** MCP spec compatibility: `mcp>=1.0,<2.0`. MCP observer raises `UnsupportedMCPVersionError` outside range (FR8, FR46). MCP transports: `stdio` (local default), Streamable HTTP (remote default; supersedes deprecated SSE), in-memory (test default). SSE supported as legacy client only with deprecation warning.
- **NFR-COMPAT-05:** LiteLLM compatibility: `litellm>=1.83` (pinned minor floor; no ceiling). `LLMProviderAdapter` Protocol isolates the dependency surface; Mock adapter keeps unit tests stable across LiteLLM upgrades. LiteLLM provider-coverage drift (e.g., a provider that LiteLLM stops supporting mid-release) surfaces as a provider-specific test failure, not a library bug.
- **NFR-COMPAT-06:** OpenTelemetry compatibility: `opentelemetry-api>=1.27` + `opentelemetry-sdk>=1.27` (pinned minor floors). GenAI semantic convention attribute names routed through internal facade (`telemetry/semconv.py`) so attribute-name churn is a single-file update. Datadog v1.37+ and Grafana Tempo are first-party validated export targets in Phase 2.

### Maintainability

- **NFR-MAINT-01:** Solo + AI-agent-assisted maintainership posture stated openly in `MAINTAINERS.md`. Bus-factor mitigation deliverables ship in Phase 1: `CONTRIBUTING.md`, "good first issue" labels, agent* portfolio shared-pattern docs, Mock adapter as contributor template, conformance suite as contract publication (FR45), `SubprocessAdapter` ABC as contributor-facing API (FR12).
- **NFR-MAINT-02:** Issue-triage SLA: best-effort 5 business days for triage of new issues; security issues (per `SECURITY.md` reporting process) prioritized. SLA + posture published in `SUPPORT.md`. Orgs requiring contracted SLA / indemnification are recommended to pair with a paid-support arrangement or fork.
- **NFR-MAINT-03:** Semantic versioning discipline: pre-1.0 (`0.x.y`) during Phase 1 — breaking changes minor-bump (`0.x` → `0.x+1`); patch releases (`0.x.y` → `0.x.y+1`) are non-breaking. 0.x → 1.0 exit criteria (FR65) ratified at Phase 1 close; 1.0+ follows strict semver with breaking changes major-bump.
- **NFR-MAINT-04:** Documentation deliverables are first-class Phase 1 deliverables, not "after MVP" polish (per the editorial-moat principle and the moat-defensibility finding in Step 2 frontmatter). Doc-build CI asserts required documents exist with required sections: README, recipe gallery (≥8 Phase 1 recipes per `Appendix: Recipe Gallery`), ADRs in `docs/adr/`, contracts docs (`docs/contracts/evidence-block-format.md`, `docs/contracts/determinism-contract.md`, `docs/contracts/stability-surface.md`, `docs/contracts/exit-criteria-0x-to-1x.md`, `docs/contracts/otel-trace-visual.md`).
- **NFR-MAINT-05:** Stability Surface metadata (FR64) is updated per release; every public-API element (keyword, Protocol, error class, scenario YAML schema field, adapter file path) carries exactly one stability label (`stable` / `provisional` / `experimental`). Release notes link to the Stability Surface document. Doc-build CI asserts no public element is unlabeled.

## Appendix: Recipe Gallery (stub for Phase 1 docs deliverable)

The journey walkthroughs in `## User Journeys` are tight per the PRD's information-density bar. Rich step-by-step recipes are a Phase 1 first-class docs deliverable; the gallery seed below names the recipes that derive from each journey + a few high-leverage additions identified during PRD discovery. Each recipe is targeted at ≤1 page of runnable code, an evidence-block screenshot, and a "next step" link.

### Phase 1 recipe seed

| # | Recipe title | Derived from | Files referenced |
|---|---|---|---|
| 1 | First agent eval in five minutes | Journey 1 | README example; bundled echo MCP server fixture |
| 2 | When tests get flaky: Pass@k over polling | Journey 2 | `docs/adr/003-polling-ban.md`; `Stat.` namespace |
| 3 | Tool Discoverability: debugging vocabulary | Journey 3 | `MCP.Get Tool Discoverability`; `TASK_LIST` YAML template; cohort-table reference |
| 4 | Static skill validation (Phase 1 subset) | Journey 4 (Phase 1 portion only) | `Skill.` keyword catalog |
| 5 | Replacing custom Python e2e tests with `.robot` | Journey 5 | `rf-mcp` before/after diff; `Metric.Get Cost Total` example; `mcp_per_test="suite"` trade-off (NFR-PERF-03d) |
| 6 | Custom provider adapter via Protocol | Journey 6 | `LLMProviderAdapter` Protocol; Mock adapter template |
| 7 | First MCP server test (Tier-1 only, no API key) | New | bundled echo MCP server; `MCP.` static keywords |
| 8 | CI integration: GitHub Actions for nightly tier-3 | New | sample `workflow.yaml`; tier-tag filtering; JUnit XML emission (FR49); exit-code conventions (FR50) |

### Phase 2 recipe seed

| # | Recipe title |
|---|---|
| 1 | Three-tier skill validation with `Judge.Get Score` (full Devon flow) |
| 2 | Cross-provider eval: Mann-Whitney U + Cliff's δ via `agenteval-advanced` |
| 3 | `Judge.` calibration cookbook |
| 4 | `MCP.Get Tool Discoverability` with auto-task generation from docstrings |
| 5 | OTLP trace export to Grafana / Datadog |

Recipes 1–6 mirror the journey numbering for cross-reference. Recipes 7–8 cover capabilities surfaced during journey-requirement analysis that didn't fit a single persona narrative.



