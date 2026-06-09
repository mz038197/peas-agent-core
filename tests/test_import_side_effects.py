"""Regression tests: import must not create skills/tools in cwd."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from peas_agent.core import PACKAGE_DIR, SkillsLoader
from peas_agent.tools_loader import ToolsLoader


def test_skills_loader_init_does_not_mkdir(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    loader = SkillsLoader(workspace, builtin_dir=PACKAGE_DIR / "builtin_skills")
    assert loader.workspace_skills == workspace / "skills"
    assert not loader.workspace_skills.exists()


def test_tools_loader_init_does_not_mkdir(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    loader = ToolsLoader(workspace)
    assert loader.tools_dir == workspace / "tools"
    assert not loader.tools_dir.exists()


def test_import_does_not_create_skills_tools_in_cwd(tmp_path: Path) -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run(
        [sys.executable, "-c", "from peas_agent import Agent"],
        cwd=tmp_path,
        env={
            **dict(__import__("os").environ),
            "PYTHONPATH": str(src),
        },
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert not (tmp_path / "skills").exists()
    assert not (tmp_path / "tools").exists()
