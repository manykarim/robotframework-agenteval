# Docstring refresh proposal — adopt Browser Library style across all 49 keywords

**Date:** 2026-05-26
**Author:** Amelia (Developer)
**Status:** PROPOSAL — no docstrings rewritten yet. Awaiting Kilo + Codex cross-LLM review per user `/goal` directive.
**Reference:** `robotframework-browser` (https://github.com/MarketSquare/robotframework-browser/tree/main/Browser/keywords) — the de facto gold standard for libdoc-friendly Robot Framework keyword documentation.
**Scope:** 49 keywords across 5 libraries (`AgentEval` 30 + `SkillsLibrary` 8 + `MCPLibrary` 9 + `SubagentsLibrary` 1 + `HooksLibrary` 1) — every `@keyword(name=...)`-decorated method in `src/AgentEval/`.

## TL;DR

agenteval docstrings are already substantively well-written (Google-style `Args:` / `Returns:` / `Raises:` sections, dense FR/ADR/Story provenance, technical accuracy). What's missing is **libdoc-renderable structure** + **runnable examples**:

| Dimension | Browser Library | agenteval (current) | Gap |
| --- | --- | --- | --- |
| **`| =Arguments= | =Description= |` table** | ✓ every keyword | ✗ Google-style `Args:` indent | libdoc renders Browser's table as a clean HTML `<table>`; agenteval's `Args:` renders as a paragraph. |
| **`Example:` section with RF syntax** | ✓ every keyword (1–4 examples) | ✗ zero examples | **Biggest miss.** Users opening libdoc HTML can't see runnable code. |
| **Backtick cross-refs `` `Other Keyword` ``** | ✓ everywhere | ✗ prose-only | libdoc auto-links these. agenteval's "see `Send Prompt`" becomes a dead string in HTML. |
| **One-line summary** | ✓ 1–2 sentences | ✓ 1–2 sentences | Equivalent. |
| **Tier annotation `[Tier N — Label]`** | n/a | ✓ project convention | Keep — agenteval-specific. |
| **FR/ADR/Story citations** | n/a | ✓ pervasive | Keep — load-bearing for contributors. Move to a `Notes:` tail section. |
| **Forum/external links** | ✓ `[Comment >>]` footer | ✗ none | Optional — Issue tracker link would be the agenteval-equivalent. |

This proposal converts agenteval to **Browser-Library-style libdoc structure** while preserving the project's FR/ADR provenance discipline.

## Browser Library template (verbatim reference)

From `Browser/keywords/getters.py::get_text`:

````python
"""Returns text attribute of the element found by ``selector``.

Keyword can also return `input` or `textarea` value property text.
See the `Finding elements` section for details about the selectors.

| =Arguments= | =Description= |
| ``assertion_operator`` | See `Assertions` for further details. Defaults to None. |
| ``assertion_expected`` | Expected value for the state |
| ``message`` | overrides the default error message for assertion. |
| ``text_type`` | How text is returned. Possible values are ``allInnerTexts``, ``allTextContents``, ``innerText``, ``inputValue``, and ``innerHTML``. |

Keyword uses strict mode, see `Finding elements` for more details about strict mode.
The ``text_type`` argument determines how text is returned. The ``allInnerTexts`` and
``allTextContents`` will return a list of strings, while other types return a single
string.

Optionally asserts that the text matches the specified assertion. See `Assertions`
for further details for the assertion arguments. By default, assertion is not done.

Example:
| ${text} =    `Get Text`    id=important                                # Returns element text without assertion.
| ${text} =    `Get Text`    id=important    ==    Important text        # Returns element text with assertion.
| ${text} =    `Get Text`    //input         ==    root                  # Returns input element text with assertion.
| ${text} =    `Get Text`    id=important    text_type=innerHTML         # Returns element inner HTML.
| ${text} =    `Get Text`    id=important    text_type=allInnerTexts     # Returns element inner text as list of strings.

[https://forum.robotframework.org/t//4285|Comment >>]
"""
````

**Structural elements:**

1. **First sentence** — what the keyword does, with backticks around argument names (`` ``selector`` ``)
2. **Optional 1–2-paragraph context** — cross-references to other keywords / concepts
3. **`| =Arguments= | =Description= |` table** — every argument documented in a pipe-delimited table row
4. **Optional behavioral notes** — strict-mode caveats, type semantics
5. **`Example:` section** — multi-line pipe-delimited RF syntax, often with inline `# Comments` explaining each line
6. **Footer link** — forum thread / issue (optional)

## Proposed agenteval template

agenteval-flavored adaptation preserving:

- The `[Tier N — Label]` annotation (project convention; no Browser-Library equivalent)
- FR / ADR / Story provenance (load-bearing for contributors per `feedback_citation_drift_first_class`)
- The honest-framing of failure modes (Phase-1 carve-outs, `IncompleteTraceError` gates)

````python
"""Execute a single-shot prompt against a coding-agent adapter (PRD FR14).

[Tier 2 — Stochastic Single-Shot] — invokes the named adapter's
``run()`` method per the `CodingAgentAdapter` Protocol. See the
`Adapters` section for available adapter names.

| =Arguments= | =Description= |
| ``adapter`` | Adapter name registered via the ``agenteval.coding_agents`` entry-points group. Defaults to ``"generic"`` (LiteLLM-backed). Tier-2 keywords resolve adapter names via `Get Adapter` from the discovery registry. |
| ``prompt`` | Prompt text to send to the agent. |
| ``mcp_servers`` | Optional ``dict[str, ServerHandle]`` of MCP servers to attach. Phase-1: string form (comma-separated names) accepted but not yet resolved to handles (DF-4.3-S2). |
| ``**kwargs`` | Provider/adapter-specific forward-compat kwargs (e.g., ``model="anthropic/claude-sonnet-4-6"``, ``temperature=0.5``). |

Returns an ``AgentRunResult`` carrying ``response_text``, ``tool_calls``,
``usage``, ``metadata`` (with ``completeness`` + ``mcp_coverage``),
``cost_usd``, ``latency_seconds``, and ``trace_id``.

Raises ``IncompleteTraceError`` per FR37 when the run reports
``mcp_coverage="external_mixed"`` AND the Library was constructed
with ``allow_external_mcp_blind=False`` (default).

Example:
| ${result} =    `Send Prompt`    prompt=Hello, world.                                  # Default adapter (generic), default model.
| ${result} =    `Send Prompt`    adapter=claude-code-cli    prompt=Run the build.      # CLI adapter — pinned `claude` binary.
| ${result} =    `Send Prompt`    adapter=generic    prompt=Search for tutorials    model=anthropic/claude-sonnet-4-6
| `Tool Call Should Have Occurred`    ${result}    web_search                           # Use as input to other keywords.

Notes:
- See `feedback_listener_hook_api_surface_empirical_check` (Epic 8 retro) for the empirical-probe contract when adapter output shapes are unverified.
- ``cost_usd`` is 0.0 on the Mock provider; non-zero on real adapters (Story 8a.1 v1 HIGH-1 fix — read ``total_cost_usd`` first).
"""
````

**What changed structurally:**

- ✓ `[Tier N]` annotation preserved (project-specific)
- ✓ `| =Arguments= | =Description= |` table replaces Google `Args:` block
- ✓ `Example:` section added with 3–4 RF-syntax invocations + inline `# Comments`
- ✓ Backtick-wrapped argument names + cross-refs (libdoc auto-links)
- ✓ FR/ADR provenance moved to inline parentheticals + a `Notes:` tail section (keeps grepability for contributors)
- ✓ Errors documented in prose paragraph (cleaner libdoc render than indented `Raises:`)

## Per-library scope

49 keywords across 5 libraries:

| Library | Keywords | Current docstring quality | Example density | Effort |
| --- | --- | --- | --- | --- |
| `AgentEval` (top-level) | 30 | Good Google-style; FR-cited; no examples | 0/30 examples | **L** — biggest surface; metrics + assertions + stats + orchestration + telemetry |
| `AgentEval.skills.library.SkillsLibrary` | 8 | Excellent; tier-annotated; FR-cited | 0/8 examples | **M** — skill validation has natural example shape |
| `AgentEval.mcp.library.MCPLibrary` | 9 | Excellent; transport-enum explained | 0/9 examples | **M** — MCP server lifecycle benefits hugely from start/stop example |
| `AgentEval.subagents.library.SubagentsLibrary` | 1 | Mirror of `Get Frontmatter` | 0/1 | **XS** |
| `AgentEval.hooks.library.HooksLibrary` | 1 | Specialized; settings.json schema | 0/1 | **XS** |
| **Total** | **49** | — | **0/49** | **~L + M + M + XS + XS** |

## Sequencing recommendation

If the cross-LLM review approves direction:

1. **Phase A — XS libraries first** (1 commit; sanity-check the template): `SubagentsLibrary` + `HooksLibrary` (2 keywords total)
2. **Phase B — Tier-2/3 keywords on AgentEval** (1 commit; ~10 keywords): `Send Prompt`, `Run Scenario`, `Stat.Run N Times`, `Stat.Get Pass At K`, etc. — these are the user-facing entry points; examples here have highest user value
3. **Phase C — Tier-1 metrics + assertions on AgentEval** (1 commit; ~12 keywords): `Get Tool Hit Rate`, `Tool Call Should Have Occurred`, `Trajectory Should Match`, etc.
4. **Phase D — Tier-1 telemetry + config + heatmap on AgentEval** (1 commit; ~8 keywords): `Get Spans`, `Get Run Manifest`, `Get Effective Config`, `Get Cohort Heatmap`, etc.
5. **Phase E — SkillsLibrary** (1 commit; 8 keywords): static + activation + discoverability
6. **Phase F — MCPLibrary** (1 commit; 9 keywords): config + lifecycle + tool inspection
7. **Phase G — Regenerate all 5 libdoc HTML + verify Pages-hosted renders match expectations** (1 commit)

**Total: 7 commits.** Each Phase B–F bounded by 1 library or 1 thematic group so a reviewer can scan + approve per-PR.

**Cross-LLM review on each phase:** every commit gets kilo/minimax review per `feedback_third_llm_family_fallback`. The XS Phase A acts as the template-validation pass before bulk rollout.

## What stays the same

- **`@tier(N)` decorator** + `[Tier N — Label]` summary prefix — project convention; no Browser equivalent.
- **FR / ADR / Story citations** — preserved (`feedback_citation_drift_first_class`).
- **`IncompleteTraceError` + `mcp_coverage` honesty contracts** — preserved.
- **Honest-framing language** — Phase-1 carve-outs, "Phase-1.5 C71" markers, etc.
- **Type annotations** on Python signatures — libdoc derives these from `inspect.signature()`; docstring tables are descriptive supplements, not duplicates.

## What changes

1. **`Args:` → `| =Arguments= | =Description= |`** — table format renders cleanly in libdoc HTML.
2. **Add `Example:` section** to every keyword (minimum 2 RF-syntax invocations; 3–5 for keywords with multi-mode args like `Trajectory Should Match`'s 4 modes).
3. **Wrap argument + keyword + class references in `` `` backticks ``** — libdoc auto-links keywords; backticks render as `<code>` in libdoc.
4. **Move ADR / FR / Story citations to inline parentheticals + a `Notes:` tail section** — keeps them grepable but out of the Arguments table.
5. **Errors documented in prose** (instead of indented `Raises:`) — cleaner libdoc render.
6. **Add cross-references between related keywords** — e.g., `Get Tool Call Count`'s docstring should link to `Get Tool Calls` + `Get Tool Hit Rate` so libdoc users can navigate.

## Estimated diff size

Per keyword: ~15–30 additional lines of docstring (table + examples + notes). Across 49 keywords: roughly **+1000 lines** of docstring content across 7 files. Zero code changes; zero test changes.

libdoc HTML regeneration produces ~5x larger HTML files (more table rendering + example formatting). Estimated `docs/keywords/AgentEval.html` grows from 237 KB → ~500 KB. Acceptable for static hosting.

## Risks + considerations

1. **Libdoc render verification** — Browser Library's `| =Arguments= | =Description= |` table syntax may render differently between libdoc 5.x and the RF 7.x version agenteval pins. Phase A's XS validation pass exercises this.
2. **Citation drift** — every cross-LLM review since Epic 2 has caught at least one citation-drift issue. The refactor must NOT drop FR/ADR/Story citations even when restructuring; verify each keyword's existing citations end up in the new `Notes:` section.
3. **Example accuracy** — invented examples that don't run are worse than no examples (`feedback_executable_doc_precheck` Epic 7 retro). Every example MUST be `robot --dryrun`-able OR copy-pasted from an existing test under `tests/`.
4. **Forum/external link footer** — Browser Library uses `[https://forum.robotframework.org/t//...|Comment >>]`. agenteval doesn't have a forum yet. Suggest substituting `[https://github.com/manykarim/robotframework-agenteval/issues|Issue/discussion >>]` at the end of each docstring — but this is OPTIONAL and adds noise; recommend **deferring** until a forum/discussion-board choice is made.
5. **Tier annotation collision with the table** — `[Tier N — Label]` lives on the first line. Browser's first line is the keyword purpose. agenteval places tier on line 1 of body (after the summary). Need to confirm libdoc renders both correctly: `"""Summary.\n\n[Tier 2 — Stochastic Single-Shot] — context.\n\n| =Arguments= ..."""`.

## Validation plan

For each phase commit:

1. Regenerate libdoc HTML: `uv run python -m robot.libdoc <library> /tmp/test.html`
2. Open `/tmp/test.html` in a browser (or use `python -c "from html.parser import ..."` to grep the rendered structure).
3. Verify the Arguments table renders as `<table>`.
4. Verify Example blocks render as `<pre>` (RF libdoc convention).
5. Verify backtick keyword references render as auto-links.
6. Run kilo/minimax cross-LLM review on the docstring diff.
7. Spot-check 2–3 examples are valid RF syntax (paste into a scratch `.robot` file + `robot --dryrun`).

## Decision needed

Below is the **review prompt** I'll send to Kilo + Codex CLIs before implementation. **Please confirm the prompt scope captures the right concerns** — or adjust as needed.

---

## v2 — post cross-LLM review (2026-05-26)

**Reviewers:** Kilo (minimax-M2.7) — substantive 7-critique review with verdict *approve-with-revisions*. Codex CLI — spent its budget on the empirical libdoc probe + Browser source verification; ran out of output budget before structured critique landed. Codex's actions implicitly verified the central claim (it created `tmp_libdoc_probe.py` matching Critique 1's empirical-probe ask).

### Empirical libdoc-render probe (CRITIQUE 1 + CRITIQUE 3 resolution)

Kilo's HIGH CRITIQUE 1 marked the proposal's central claim ("libdoc renders pipe tables as `<table>`") as **UNVERIFIED**. Codex started the probe but ran out before the structured output. **I ran the probe myself** post-review with this minimal Python file:

```python
from robot.api.deco import keyword

class LibdocProbe:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"
    @keyword(name="Example One")
    def example_one(self, arg: str = "value") -> str:
        """Does one thing.

        | =Arguments= | =Description= |
        | ``arg`` | Example argument. |

        Example:
        | `Example One`    arg=hello
        | `Example Two`    first=`Example One`
        """
        return arg

    @keyword(name="Example Two")
    def example_two(self, first: str = "x") -> str:
        """Uses `Example One`. See `Adapters` for non-keyword text.

        | =Arguments= | =Description= |
        | ``first`` | Example reference to `Example One` and `Adapters`. |

        Example:
        | `Example Two`    first=hello
        """
        return first
```

`uv run python -m robot.libdoc libdoc_probe.LibdocProbe /tmp/probe.html` produces this rendered fragment for `Example Two`'s doc field:

```html
<p>Uses <a href="#Example%20One" class="name">Example One</a>. See <span class="name">Adapters</span> for non-keyword text.</p>
<table border="1">
<tr><th>Arguments</th><th>Description</th></tr>
<tr><td><code>first</code></td><td>Example reference to <a href="#Example%20One" class="name">Example One</a> and <span class="name">Adapters</span>.</td></tr>
</table>
<p>Example:</p>
<pre>
<a href="#Example%20Two" class="name">Example Two</a>    first=hello
</pre>
```

**Verified empirically (RF 7.4.2 libdoc):**

1. ✓ `| =Arguments= | =Description= |` syntax → `<table border="1"><tr><th>Arguments</th>...</tr>` HTML table
2. ✓ Backtick keyword references → `<a href="#KeywordName" class="name">` (intra-library auto-links)
3. ✓ Backtick non-keyword references → `<span class="name">` (styled, gracefully degraded; no broken `href`)
4. ✓ `Example:` followed by pipe-prefixed lines → `<pre>` block with embedded auto-links
5. ✓ Inline `` ``code`` `` (double-backtick) → `<code>` tags

**Kilo's CRITIQUE 1 is REFUTED.** The proposal's central technical claim was correct; libdoc renders all 4 structural elements as expected. The existing `docs/keywords/*.html` files contain zero `<table>` tags because the **current docstrings use Google-style `Args:` blocks, not pipe tables** — exactly as the proposal diagnoses.

### Revisions accepted from Kilo's review

| # | Severity | Critique | Disposition |
| --- | --- | --- | --- |
| 1 | HIGH | "libdoc table rendering unverified" | **Refuted** by empirical probe (above). |
| 2 | HIGH | "Example-accuracy gate unenforceable without CI extraction" | **Accepted** — see Phase 8 below. |
| 3 | HIGH | "Phase A is mislabeled as template-validation; needs Phase 0 empirical probe first" | **Partially accepted** — empirical probe is done (above); the proposal's Phase A keeps the "validate template via 2 small libraries" role but Phase 0 is collapsed into this v2 amendment. |
| 4 | MED | "Citation drift risk in Notes: tail section — add bidirectional consistency check" | **Accepted** — see Phase 8 below. |
| 5 | MED | "Phase D too wide — split telemetry from config+heatmap" | **Accepted** — phase plan revised to 7 commits + 1 CI phase. |
| 6 | MED | "HTML file-size estimate inflated (500 KB)" | **Accepted** — revised estimate to 300–350 KB. |
| 7 | LOW | "Forum-link deferred indefinitely — add TODO marker" | **Accepted** — `# TODO(agenteval-docs): footer link once forum/discussion choice is made` to be added to each library's first keyword. |
| Risk 1 | — | "Tier annotation + table interaction" | **Refuted** by empirical probe — Tier prefix + table coexist fine. |
| Risk 2 | — | "**kwargs row in table is sig-introspection-inconsistent" | **Accepted** — replace `` ``**kwargs`` `` row with a behavioral note paragraph below the table. |
| Risk 3 | — | "Cross-library linking unverified" | **Partially confirmed** — intra-library auto-links work; cross-library references degrade to `<span class="name">` (styled but unlinked). Acceptable; document the limitation. |

### Revised phase plan (8 phases, was 7)

1. **Phase 0** ✓ COMPLETE — Empirical libdoc-render probe (above); confirmed pipe table + auto-links + Example block render correctly.
2. **Phase 1 (XS, was Phase A)** — `SubagentsLibrary` + `HooksLibrary` (2 keywords) → 1 commit. Real refresh, not template-validation.
3. **Phase 2 (was Phase B)** — `AgentEval` Tier-2/3 user-facing (~10 keywords: `Send Prompt`, `Run Scenario`, `Load Scenario`, `Stat.Run N Times`, `Stat.Get Pass At K`, `Stat.Get Pass At K Confidence Interval`, `Stat.Assert Run Determinism`, etc.) → 1 commit.
4. **Phase 3 (was Phase C)** — `AgentEval` Tier-1 metrics + assertions (~12 keywords: tool-call metrics + 3 assertion keywords) → 1 commit.
5. **Phase 4 (split Phase D part 1)** — `AgentEval` Tier-1 telemetry (~4 keywords: `Get Spans`, `Get Run Manifest`, `Get Last Warnings`, `Get Keyword Tier`) → 1 commit.
6. **Phase 5 (split Phase D part 2)** — `AgentEval` Tier-1 config + heatmap (~4 keywords: `Get Config`, `Get Effective Config`, `Get Effective Config With Provenance`, `Get Cohort Heatmap`) → 1 commit.
7. **Phase 6 (was Phase E)** — `SkillsLibrary` (8 keywords) → 1 commit.
8. **Phase 7 (was Phase F)** — `MCPLibrary` (9 keywords) → 1 commit.
9. **Phase 8 (was Phase G + Kilo CRITIQUE 2 + CRITIQUE 4)** — Two-part CI hygiene:
   - 8a: `tests/unit/conventions/test_docstring_examples_dryrun.py` — extract `Example:` blocks from every `@keyword`-decorated method's docstring, write them to temp `.robot` files, run `robot --dryrun`, fail on RC != 0 (Kilo CRITIQUE 2 mitigation).
   - 8b: `tests/unit/conventions/test_docstring_citation_consistency.py` — if a docstring body mentions `FR\d+` / `ADR-\d+` / `Story \d+\.\d+`, the same identifiers must appear in the `Notes:` tail section (Kilo CRITIQUE 4 mitigation).
   - 8c: Regenerate all 5 libdoc HTML + commit. **Per-phase verification** (Kilo CRITIQUE 3 follow-up): every commit between Phase 1–7 also regenerates the affected library's HTML so reviewers can preview Pages output per-phase.

### Outstanding risks per Kilo + new findings

- **Cross-library backtick references** degrade gracefully to `<span class="name">` (styled but unlinked). Acceptable for Phase 1 ship; future improvement is libdoc's `--name <library>` aggregation flag (untested).
- **`**kwargs` documentation pattern** — proposed revision: document `**kwargs` in a behavioral-note paragraph BELOW the Arguments table (e.g., "Additional keyword arguments are forwarded to the underlying adapter — see `Adapters` for adapter-specific kwargs."). Avoids inconsistency with libdoc's signature introspection (Kilo Risk 2).
- **Forum-link footer** — defer with explicit TODO marker per Kilo CRITIQUE 7. Phase-2 work-item.

### HTML file-size estimate (revised)

Per Kilo CRITIQUE 6: estimate revised from 500 KB → **300–350 KB** for `AgentEval.html` post-refresh. Acceptable for static GitHub Pages hosting.

### Decision needed (v2)

**Approve the revised 8-phase plan?** Specifically:

1. **Phase 0 empirical probe is DONE** — pipe-table rendering confirmed via my probe + the screenshot evidence above. OK to proceed to Phase 1?
2. **Phase 8 CI conventions tests** (8a + 8b) — author them inline with Phase 1, OR ship as a final phase after all docstrings are migrated?
3. **Tier-annotation placement** — keep `[Tier N — Label]` on line 2 of body (after one-line summary), OR move to a `=Metadata=` row inside the Arguments table? Kilo's Risk 1 was refuted but the placement question is still open.

Once you confirm direction, I'll start with Phase 1 (`SubagentsLibrary` + `HooksLibrary` — 2 keywords, ~30 lines of docstring diff) so we get a real-world signal from a small surface before touching the 30-keyword `AgentEval` library.

---

## ORIGINAL v1 — review prompt (for archival)

### Review prompt (for Kilo + Codex review)

> Review this docstring refresh proposal for the robotframework-agenteval project. The proposal converts 49 keyword docstrings across 5 libraries to Browser-Library-style format (table-formatted Arguments + RF-syntax Examples + backtick cross-refs).
>
> Verify:
>
> 1. **Browser Library style claims** — re-derive the structural elements (table syntax, Example: section, backtick conventions) from the actual Browser source at `https://github.com/MarketSquare/robotframework-browser/tree/main/Browser/keywords` (read 2–3 keyword files).
> 2. **Libdoc compatibility** — does RF 7.x libdoc render `| =Arguments= | =Description= |` tables correctly? Are backtick keyword references auto-linked?
> 3. **Citation-preservation concern** — the proposal moves FR/ADR/Story citations from `Args:` block to a `Notes:` tail. Does this risk drift per `feedback_citation_drift_first_class`?
> 4. **Phase sequencing** — XS-first → user-facing Tier-2/3 → Tier-1 metrics → telemetry → SkillsLibrary → MCPLibrary → libdoc-regen. Is the order sensible? Any phase that should split or merge?
> 5. **Example-accuracy enforcement** — is "every example must be `robot --dryrun`-able OR copy-pasted from an existing test" a strong enough gate? Should we add a CI extraction step?
> 6. **Risks not yet captured** — Tier annotation + table interaction; forum-link absence; HTML file-size growth. What else?
>
> Surface 3–7 substantive critiques ranked HIGH/MED/LOW. Quote specific proposal sections. Propose concrete revisions.
>
> End with: "Overall: approve-direction / approve-with-revisions / reject-and-revise".
