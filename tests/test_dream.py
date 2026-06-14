"""Tests for Dream.run noop and light_apply."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from peas_agent.dream import Dream
from peas_agent.memory_store import configure_memory_store, get_memory_store


@pytest.fixture
def dream_env(tmp_path: Path) -> tuple[Path, MagicMock]:
    (tmp_path / "memory").mkdir()
    (tmp_path / "SOUL.md").write_text("# soul\n", encoding="utf-8")
    (tmp_path / "USER.md").write_text("# user\n", encoding="utf-8")
    (tmp_path / "memory" / "MEMORY.md").write_text("# mem\n", encoding="utf-8")
    configure_memory_store(tmp_path)
    llm = MagicMock()
    config = {
        "dream": {
            "enabled": True,
            "light_apply": True,
            "cross_session_archive": False,
            "max_batch_size": 20,
        }
    }
    return tmp_path, llm


def test_dream_noop_when_no_history(dream_env: tuple[Path, MagicMock]) -> None:
    workspace, llm = dream_env
    dream = Dream(workspace, {"dream": {}}, llm)
    assert dream.run() is False
    llm.invoke.assert_not_called()


def test_dream_skip_advances_cursor(dream_env: tuple[Path, MagicMock]) -> None:
    workspace, llm = dream_env
    store = get_memory_store()
    store.append_history("test entry")
    llm.invoke.return_value = MagicMock(content="[SKIP]")

    dream = Dream(
        workspace,
        {"dream": {"cross_session_archive": False, "light_apply": True}},
        llm,
    )
    assert dream.run() is True
    assert store.get_last_dream_cursor() == 1


def test_dream_light_apply(dream_env: tuple[Path, MagicMock]) -> None:
    workspace, llm = dream_env
    store = get_memory_store()
    store.append_history("discussion")
    llm.invoke.return_value = MagicMock(
        content="[FILE] USER: 偏好繁中回覆"
    )

    dream = Dream(
        workspace,
        {"dream": {"cross_session_archive": False, "light_apply": True}},
        llm,
    )
    assert dream.run() is True
    assert "繁中" in store.read_user()
    assert store.get_last_dream_cursor() == 1
