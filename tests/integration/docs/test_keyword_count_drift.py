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

"""Keyword-count drift check: README + docs/index.md must match libdoc.

Mirrors `scripts/check_doc_keyword_count.py` (the docs-build CI gate) so the
same assertion runs under `uv run pytest`. Fails when a new keyword ships
without the documented counts being updated.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "_check_doc_keyword_count",
        REPO_ROOT / "scripts" / "check_doc_keyword_count.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_libdoc_derives_expected_count() -> None:
    checker = _load_checker()
    # Composed `AgentEval` surface: 55 keywords after `remove-dead-machinery`
    # deleted the `Get Effective Config With Provenance` keyword (was 56).
    assert checker.derive_keyword_count() == 55


def test_readme_and_index_counts_match_libdoc() -> None:
    checker = _load_checker()
    failures = checker.check()
    assert not failures, "Doc keyword-count drift:\n" + "\n".join(failures)
