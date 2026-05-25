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

"""Scaffold writer for `agenteval new-adapter` (Story 8b.2)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

__all__ = ["scaffold_new_adapter"]

_TEMPLATES_DIR = Path(__file__).parent / "templates"

AdapterType = Literal["subprocess", "inprocess"]


def _normalize_name(name: str) -> tuple[str, str]:
    """Normalize ``name`` to (package_name, module_name).

    Examples:
        ``"my-adapter"`` → ``("my-adapter", "my_adapter")``
        ``"my_adapter"`` → ``("my_adapter", "my_adapter")``
        ``"MyAdapter"`` → ``("MyAdapter", "myadapter")`` (lowercased)
    """
    package_name = name
    module_name = name.replace("-", "_").lower()
    return package_name, module_name


def scaffold_new_adapter(
    *,
    name: str,
    adapter_type: AdapterType = "subprocess",
    output_dir: Path,
    force: bool = False,
) -> int:
    """Scaffold a new agenteval adapter package.

    Creates:
        - ``<output_dir>/<name>/pyproject.toml`` — declares the
          ``agenteval.coding_agents`` entry-points group per FR17a.
        - ``<output_dir>/<name>/<module_name>/__init__.py``
        - ``<output_dir>/<name>/<module_name>/adapter.py`` —
          ``SubprocessAdapter`` (or ``InProcessAdapter``) subclass stub.
        - ``<output_dir>/<name>/tests/test_<module_name>.py`` — Mock
          conformance test.

    Args:
        name: package name (``my-adapter`` or ``my_adapter``).
        adapter_type: ``"subprocess"`` (CLI-driven) or ``"inprocess"``
            (SDK-driven).
        output_dir: target directory (parent of the new package).
        force: if True, overwrite existing files.

    Returns:
        0 on success; non-zero only on fatal errors (currently none).
    """
    package_name, module_name = _normalize_name(name)
    package_dir = output_dir / package_name
    package_dir.mkdir(parents=True, exist_ok=True)

    # Template selection. argparse limits `adapter_type` to subprocess|inprocess.
    adapter_template = "adapter_subprocess.py.tmpl" if adapter_type == "subprocess" else "adapter_inprocess.py.tmpl"

    files: dict[Path, str] = {
        package_dir / "pyproject.toml": _render(
            "pyproject.toml.tmpl", package_name=package_name, module_name=module_name
        ),
        package_dir / module_name / "__init__.py": _render(
            "__init__.py.tmpl", package_name=package_name, module_name=module_name
        ),
        package_dir / module_name / "adapter.py": _render(
            adapter_template, package_name=package_name, module_name=module_name
        ),
        package_dir / "tests" / f"test_{module_name}.py": _render(
            "test_adapter.py.tmpl",
            package_name=package_name,
            module_name=module_name,
        ),
    }

    written = 0
    skipped = 0
    overwritten = 0
    for target, content in files.items():
        if target.exists() and not force:
            sys.stderr.write(
                f"agenteval new-adapter: {target.relative_to(output_dir)} already exists; use --force to overwrite\n"
            )
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        was_existing = target.exists()
        target.write_text(content, encoding="utf-8")
        if was_existing:
            overwritten += 1
            sys.stderr.write(f"agenteval new-adapter: overwrote {target.relative_to(output_dir)}\n")
        else:
            written += 1

    sys.stdout.write(
        f"agenteval new-adapter: scaffolded {written + overwritten} files "
        f"({written} new, {overwritten} overwritten, {skipped} skipped) "
        f"at {package_dir}.\n"
    )
    sys.stdout.write(f"\nNext steps:\n  cd {package_dir}\n  uv add --dev pytest\n  uv run pytest tests/\n")
    return 0


def _render(template_name: str, *, package_name: str, module_name: str) -> str:
    """Render a template by substituting ``{{name}}`` / ``{{module}}`` tokens."""
    path = _TEMPLATES_DIR / template_name
    text = path.read_text(encoding="utf-8")
    return text.replace("{{name}}", package_name).replace("{{module}}", module_name)
