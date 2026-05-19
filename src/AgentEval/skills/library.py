# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Skill sub-library — static-inspection keywords for skill `.md` files.

Story 2.1 ships 5 Tier-1 keywords (per architecture L620 Decision-1 +
PRD FR1 + epics.md Epic 2 Story 2.1):

- `Get Frontmatter` — parse a skill `.md`'s YAML frontmatter into a dict.
- `Get Description` — return the `description` field.
- `Get Allowed Tools` — return the `allowed-tools` list.
- `Get Disable Model Invocation` — return the `disable-model-invocation` bool.
- `Should Be Valid Frontmatter` — structural validator (Phase-1 plain
  `@keyword`; full AssertionEngine matcher deferred to Phase-2 per
  ADR-022 catalog row).

Every method is `@tier(1)`-annotated (deterministic, ≤50 ms per call on
typical 5 KB inputs per NFR-PERF-02). Tier-1 keywords do NOT touch the
provider, the trace store, or external services; they read the local
`.md` file + parse YAML only.

Usage from a `.robot` file:

    *** Settings ***
    Library    AgentEval.skills.library    WITH NAME    Skill

    *** Test Cases ***
    Skill File Has Correct Description
        ${desc}=    Skill.Get Description    skills/example.md
        Should Be Equal    ${desc}    Example skill for testing.

Usage when composed under the top-level `AgentEval` library: the 5
keywords are flattened into the parent's keyword namespace via
`DynamicCore` so users who imported `Library AgentEval` can call them
directly (no `Skill.` prefix).

Phase-1 limitations explicitly documented:
- `Should Be Valid Frontmatter` is a plain `@keyword`-decorated function,
  NOT a `robotframework-assertion-engine` matcher. The Phase-1 manual-
  validation contract is load-bearing; Phase-2 (ADR-022 adoption) re-
  wires it with the full operator-chain idiom.
- The verb allowlist (`tests/unit/conventions/test_keyword_name_idiom.py`
  `_VERB_ALLOWLIST`) is extended with `"should"` per Story 1b.6 Dev
  Notes growth policy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.tier import tier
from AgentEval.skills._parser import parse_frontmatter, validate_frontmatter_structure

__all__ = ["SkillsLibrary"]


class SkillsLibrary:
    """Static-inspection keywords for skill `.md` files [Tier 1 — Deterministic].

    All 5 public methods are `@keyword`-decorated + `@tier(1)`-annotated
    per Story 1b.6 conventions. The class holds no mutable state; each
    call re-parses the target file so the keywords are stateless +
    parallel-safe under `pabot --processes N`.
    """

    @keyword(name="Get Frontmatter")
    @tier(1)
    def get_frontmatter(self, path: str | Path) -> dict[str, Any]:
        """Parse the YAML frontmatter at the head of a skill `.md` file.

        [Tier 1 — Deterministic] — pure file-read + YAML parse; no
        provider, no trace store. Median ≤ 50 ms per call on the 5 KB
        reference fixture per NFR-PERF-02.

        Args:
            path: Filesystem path to the skill `.md` file.

        Returns:
            The parsed YAML frontmatter as a dict.

        Raises:
            InvalidSkillFrontmatterError: On YAML / file-level structural
                failure (missing file, broken YAML, missing `---`
                delimiters, frontmatter not a mapping). This keyword
                does NOT enforce the required-fields contract — callers
                that need that should use `Get Description` / `Get
                Allowed Tools` / etc. (which validate) OR call `Should
                Be Valid Frontmatter` on the returned dict. Error
                format per `docs/contracts/error-class-hierarchy.md`
                L96-104.
        """
        return parse_frontmatter(path)

    @keyword(name="Get Description")
    @tier(1)
    def get_description(self, path: str | Path) -> str:
        """Return the `description` field from a skill `.md` file's frontmatter.

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a `description`-field type check. Raises if the field is
        missing or empty.

        Args:
            path: Filesystem path to the skill `.md` file.

        Returns:
            The `description` field value as a non-empty string.

        Raises:
            InvalidSkillFrontmatterError: If the frontmatter is invalid
                OR the `description` field is missing/non-string/empty.
        """
        return str(self._read_and_validate(path)["description"])

    @keyword(name="Get Allowed Tools")
    @tier(1)
    def get_allowed_tools(self, path: str | Path) -> list[str]:
        """Return the `allowed-tools` list from a skill `.md` file's frontmatter.

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a `list[str]` type check.

        Args:
            path: Filesystem path to the skill `.md` file.

        Returns:
            The `allowed-tools` field value as a `list[str]`. The list
            may be empty (a skill with no tool allowlist is valid).

        Raises:
            InvalidSkillFrontmatterError: If the frontmatter is invalid
                OR `allowed-tools` is not a list of strings.
        """
        return list(self._read_and_validate(path)["allowed-tools"])

    @keyword(name="Get Disable Model Invocation")
    @tier(1)
    def get_disable_model_invocation(self, path: str | Path) -> bool:
        """Return the `disable-model-invocation` bool from a skill `.md` file.

        [Tier 1 — Deterministic] — pure projection of `Get Frontmatter`
        with a strict bool type check.

        YAML coercion notes:
            - `true`/`false`/`yes`/`no`/`on`/`off` parse to Python bool
              (PyYAML 1.1 semantics) and are accepted.
            - `1`/`0` integers parse to Python int and are REJECTED
              (`isinstance(value, bool)` is False for ints).
            - String forms like `"true"` are REJECTED — must be unquoted.

        Args:
            path: Filesystem path to the skill `.md` file.

        Returns:
            The `disable-model-invocation` field value as a bool.

        Raises:
            InvalidSkillFrontmatterError: If the frontmatter is invalid
                OR `disable-model-invocation` is not a bool.
        """
        return bool(self._read_and_validate(path)["disable-model-invocation"])

    def _read_and_validate(self, path: str | Path) -> dict[str, Any]:
        """Parse + structurally-validate a skill `.md` file once per call.

        Internal helper that consolidates the parse + validate steps
        shared by `Get Description` / `Get Allowed Tools` / `Get
        Disable Model Invocation`. Story 2.1 code-review B2 fix: the
        earlier per-keyword `parse_frontmatter` + `validate_frontmatter_structure`
        call pair iterated `REQUIRED_FIELDS` once per call; this
        helper makes the cost one read + one parse + one validation
        sweep per public-keyword invocation, matching the NFR-PERF-02
        budget framing.

        Tier-1 callers that need ALL fields should call `Get Frontmatter`
        once + `Should Be Valid Frontmatter` on the result; chained
        per-field getters each incur ONE I/O + parse cycle (cache-free
        by design — `SkillsLibrary` is stateless under `pabot --processes N`).
        """
        frontmatter = parse_frontmatter(path)
        validate_frontmatter_structure(frontmatter, file_path=str(path))
        return frontmatter

    @keyword(name="Should Be Valid Frontmatter")
    @tier(1)
    def should_be_valid_frontmatter(self, frontmatter: dict[str, Any]) -> None:
        """Assert a parsed frontmatter dict has the 4 required fields + correct types.

        [Tier 1 — Deterministic] — structural validator. Phase-1 plain
        `@keyword` per ADR-022 catalog row (full AssertionEngine matcher
        deferred to Phase-2 when ADR-022 adoption completes).

        Args:
            frontmatter: The dict returned by `Get Frontmatter`. The
                4 required fields are `name`, `description`,
                `allowed-tools`, `disable-model-invocation`.

        Returns:
            None on success.

        Raises:
            InvalidSkillFrontmatterError: If any required field is
                missing OR any field has the wrong type. The error
                message lists the offending field(s) so the test author
                can remediate.

        Phase-1 limitation:
            This keyword is a plain `@keyword`-decorated function (NOT
            a `robotframework-assertion-engine` matcher) pending
            Phase-2 ADR-022 adoption.
        """
        validate_frontmatter_structure(frontmatter)
