"""Tests for bootstrap templates, sync, and build_system_prompt assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from peas_agent.core import (
    BOOTSTRAP_FILES,
    PACKAGE_DIR,
    SkillsLoader,
    WORKSPACE,
    build_system_prompt,
)
from peas_agent.tools_loader import ToolsLoader
from peas_agent.prompt_templates import load_bundled_template, sync_workspace_templates


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path.resolve()
    monkeypatch.chdir(root)
    monkeypatch.setattr("peas_agent.core.WORKSPACE", root)
    monkeypatch.setattr("peas_agent.core.MEMORY_DIR", root / "memory")
    monkeypatch.setattr("peas_agent.core.MEMORY_PATH", root / "memory" / "MEMORY.md")
    monkeypatch.setattr("peas_agent.core.HISTORY_PATH", root / "memory" / "HISTORY.md")
    monkeypatch.setattr(
        "peas_agent.core.SKILLS_LOADER",
        SkillsLoader(root, builtin_dir=PACKAGE_DIR / "builtin_skills"),
    )
    monkeypatch.setattr("peas_agent.core.TOOLS_LOADER", ToolsLoader(root))
    monkeypatch.setattr("peas_agent.core._ACTIVE_CONFIG", {"token_budget": 100000})
    return root


def test_sync_workspace_templates_creates_missing_only(workspace: Path) -> None:
    added = sync_workspace_templates(workspace, silent=True)
    assert "AGENTS.md" in added
    assert "SOUL.md" in added
    assert "USER.md" in added
    assert any(p.replace("\\", "/") == "memory/MEMORY.md" for p in added)
    assert (workspace / "skills").is_dir()

    (workspace / "SOUL.md").write_text("custom soul", encoding="utf-8")
    added_again = sync_workspace_templates(workspace, silent=True)
    assert added_again == []
    assert (workspace / "SOUL.md").read_text(encoding="utf-8") == "custom soul"


def test_bootstrap_injected_when_files_exist(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    prompt = build_system_prompt()
    for filename in BOOTSTRAP_FILES:
        assert f"## {filename}" in prompt


def test_tool_contract_always_injected(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    prompt = build_system_prompt()
    assert "# Tool Usage Notes" in prompt
    assert "web_fetch" in prompt


def test_build_system_prompt_order(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    prompt = build_system_prompt()
    identity_idx = prompt.find("## Workspace")
    bootstrap_idx = prompt.find("## AGENTS.md")
    tool_idx = prompt.find("# Tool Usage Notes")
    memory_idx = prompt.find("## Long-term Memory")
    assert identity_idx >= 0
    assert bootstrap_idx > identity_idx
    assert tool_idx > bootstrap_idx
    if memory_idx >= 0:
        assert memory_idx > tool_idx


def test_default_memory_template_skipped(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    prompt = build_system_prompt()
    assert "## Long-term Memory" not in prompt

    custom = "# Long-term Memory\n\n- User prefers concise replies.\n"
    (workspace / "memory" / "MEMORY.md").write_text(custom, encoding="utf-8")
    prompt2 = build_system_prompt()
    assert "User prefers concise replies" in prompt2


def test_load_bundled_template_reads_templates() -> None:
    content = load_bundled_template("SOUL.md")
    assert content is not None
    assert "法鬥超人" in content
