"""Tests for bootstrap templates, sync, and build_system_prompt assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from peas_agent.core import (
    BOOTSTRAP_FILES,
    PACKAGE_DIR,
    SkillsLoader,
    build_system_prompt,
    set_host_context,
)
from peas_agent.memory_store import configure_memory_store
from peas_agent.tools_loader import ToolsLoader
from peas_agent.prompt_templates import load_bundled_template, sync_workspace_templates


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path.resolve()
    monkeypatch.chdir(root)
    monkeypatch.setattr("peas_agent.core.WORKSPACE", root)
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", root)
    monkeypatch.setattr("peas_agent.core.MEMORY_DIR", root / "memory")
    monkeypatch.setattr("peas_agent.core.MEMORY_PATH", root / "memory" / "MEMORY.md")
    monkeypatch.setattr("peas_agent.core.HISTORY_PATH", root / "memory" / "HISTORY.md")
    monkeypatch.setattr(
        "peas_agent.core.SKILLS_LOADER",
        SkillsLoader(root, builtin_dir=PACKAGE_DIR / "builtin_skills"),
    )
    monkeypatch.setattr("peas_agent.core.TOOLS_LOADER", ToolsLoader(root))
    monkeypatch.setattr("peas_agent.core._ACTIVE_CONFIG", {"token_budget": 100000, "dream": {"recent_history_max": 0}})
    configure_memory_store(root)
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
    assert "web_search" in prompt


def test_build_system_prompt_order(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    prompt = build_system_prompt()
    identity_idx = prompt.find("## Roots")
    bootstrap_idx = prompt.find("## AGENTS.md")
    tool_idx = prompt.find("# Tool Usage Notes")
    memory_idx = prompt.find("## Long-term Memory")
    assert identity_idx >= 0
    assert bootstrap_idx > identity_idx
    assert tool_idx > bootstrap_idx
    if memory_idx >= 0:
        assert memory_idx > tool_idx


def test_host_context_empty_omits_host_environment(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    set_host_context(None)
    prompt = build_system_prompt()
    assert "# Host Environment" not in prompt


def test_host_context_inserted_after_bootstrap_before_tools(workspace: Path) -> None:
    sync_workspace_templates(workspace, silent=True)
    set_host_context("Streamlit shell paths")
    prompt = build_system_prompt()
    bootstrap_idx = prompt.find("## AGENTS.md")
    host_idx = prompt.find("# Host Environment")
    tool_idx = prompt.find("# Tool Usage Notes")
    assert host_idx > bootstrap_idx
    assert tool_idx > host_idx
    assert "Streamlit shell paths" in prompt


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


def test_identity_includes_workspace_and_project_root(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr("peas_agent.core.WORKSPACE", workspace.resolve())
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project.resolve())
    prompt = build_system_prompt()

    assert f"Agent workspace: {workspace.resolve()}" in prompt
    assert f"Project root: {project.resolve()}" in prompt
    assert "Relative file paths resolve against the project root." in prompt


def test_project_agents_md_is_injected_separately(
    workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("project-specific rule", encoding="utf-8")
    monkeypatch.setattr("peas_agent.core.WORKSPACE", workspace.resolve())
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project.resolve())

    prompt = build_system_prompt()

    assert "## Project AGENTS.md" in prompt
    assert "project-specific rule" in prompt
