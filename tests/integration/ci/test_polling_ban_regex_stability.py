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

"""FR56 polling-ban error-message regex stability test (Story 8a.2 AC-8a.2.9).

Asserts the primary regex + 3 mandatory FR56 sub-regexes match the actual
`build_polling_disallowed_message` output across 4 representative
keyword-name contexts (matching the fixture at
`tests/conformance/fixtures/fix-polling-ban-error-format.json` contexts 1-4;
context 5 is a Phase-2 placeholder per AC-8a.2.4).
"""

from __future__ import annotations

import re

import pytest

from AgentEval._kernel.tier_acl import build_polling_disallowed_message

PRIMARY_REGEX = re.compile(r"^PollingDisallowedError: keyword '[^']+' received a `polling=` argument")
ELEMENT_A_KEYWORD_NAME = re.compile(r"keyword '[^']+'")
ELEMENT_C_STAT_RUN_N_TIMES = re.compile(r"\$\{runs\}=\s+Stat\.Run N Times")
ELEMENT_D_ADR_LINK = re.compile(r"See ADR-019")


@pytest.mark.parametrize(
    ("keyword_name", "keyword_args"),
    [
        ("Skill.Get Activation Decision", {"polling": 5.0}),
        ("Skill.Get Discoverability", {"polling": 10.0}),
        ("Stat.Run N Times", {"polling": 2.0}),
        ("validate", {"operator": "validate"}),  # AssertionEngine ADR-019 context.
    ],
)
def test_primary_regex_matches(keyword_name: str, keyword_args: dict[str, object]) -> None:
    """AC-8a.2.9: primary regex matches across 4 representative contexts."""
    msg = build_polling_disallowed_message(keyword_name, keyword_args)
    assert PRIMARY_REGEX.search(msg), f"primary regex did not match for {keyword_name!r}: {msg!r}"


@pytest.mark.parametrize(
    "keyword_name",
    [
        "Skill.Get Activation Decision",
        "Skill.Get Discoverability",
        "Stat.Run N Times",
        "validate",
    ],
)
def test_mandatory_fr56_elements_present(keyword_name: str) -> None:
    """AC-8a.2.9: the 3 mandatory FR56 sub-regexes (a, c, d) match."""
    msg = build_polling_disallowed_message(keyword_name, {"polling": 1.0})
    assert ELEMENT_A_KEYWORD_NAME.search(msg), f"element (a) keyword-name pattern missing for {keyword_name!r}"
    assert ELEMENT_C_STAT_RUN_N_TIMES.search(msg), f"element (c) Stat.Run N Times snippet missing for {keyword_name!r}"
    assert ELEMENT_D_ADR_LINK.search(msg), f"element (d) ADR-019 link missing for {keyword_name!r}"
