"""Tests for Recent History in build_system_prompt."""

from __future__ import annotations

from pathlib import Path

import pytest

from peas_agent.core import (
    PACKAGE_DIR,
    SkillsLoader,
    build_system_prompt,
)
from peas_agent.memory_store import configure_memory_store, get_memory_store
from peas_agent.tools_loader import ToolsLoader


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
    monkeypatch.setattr(
        "peas_agent.core._ACTIVE_CONFIG",
        {"token_budget": 100000, "dream": {"recent_history_max": 50}},
    )
    configure_memory_store(root)
    return root


def test_recent_history_appears_before_dream(workspace: Path) -> None:
    store = get_memory_store()
    store.append_history("使用者偏好安靜晚餐")
    prompt = build_system_prompt()
    assert "# Recent History" in prompt
    assert "安靜晚餐" in prompt


def test_recent_history_hidden_after_dream_cursor(workspace: Path) -> None:
    store = get_memory_store()
    cursor = store.append_history("已處理事實")
    store.set_last_dream_cursor(cursor)
    prompt = build_system_prompt()
    assert "# Recent History" not in prompt
