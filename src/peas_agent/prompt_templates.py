"""Load and render agent system prompt templates under templates/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_PACKAGE_ROOT = Path(__file__).resolve().parent
_TEMPLATES_ROOT = _PACKAGE_ROOT / "templates"


@lru_cache
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_ROOT)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(name: str, *, strip: bool = False, **kwargs: Any) -> str:
    """Render a template under templates/ (e.g. agent/identity.md)."""
    text = _environment().get_template(name).render(**kwargs)
    return text.rstrip() if strip else text


def load_bundled_template(template_name: str) -> str | None:
    """Read a bundled template file; return None if missing."""
    path = _TEMPLATES_ROOT / template_name
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def sync_workspace_templates(workspace: Path, *, silent: bool = False) -> list[str]:
    """Copy bundled templates into workspace when missing; never overwrite existing files."""
    added: list[str] = []

    def _write(src: Path | None, dest: Path) -> None:
        if dest.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = src.read_text(encoding="utf-8") if src and src.is_file() else ""
        dest.write_text(content, encoding="utf-8")
        try:
            added.append(str(dest.relative_to(workspace)))
        except ValueError:
            added.append(str(dest))

    for name in ("AGENTS.md", "SOUL.md", "USER.md"):
        _write(_TEMPLATES_ROOT / name, workspace / name)

    _write(_TEMPLATES_ROOT / "memory" / "MEMORY.md", workspace / "memory" / "MEMORY.md")
    (workspace / "skills").mkdir(exist_ok=True)
    (workspace / "tools").mkdir(exist_ok=True)
    _write(
        _TEMPLATES_ROOT / "tools" / "example_calc" / "tool.py",
        workspace / "tools" / "example_calc" / "tool.py",
    )

    if added and not silent:
        for name in added:
            print(f"  Created {name}")

    return added
