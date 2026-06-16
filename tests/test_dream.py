"""Tests for Dream.run noop and phase2 routing."""

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
        {"dream": {"cross_session_archive": False}},
        llm,
    )
    assert dream.run() is True
    assert store.get_last_dream_cursor() == 1


def test_dream_runs_phase2_for_file_updates(dream_env: tuple[Path, MagicMock]) -> None:
    workspace, llm = dream_env
    store = get_memory_store()
    store.append_history("discussion")
    llm.invoke.return_value = MagicMock(
        content="[FILE] USER: 偏好繁中回覆"
    )

    dream = Dream(
        workspace,
        {"dream": {"cross_session_archive": False}},
        llm,
    )
    with patch.object(Dream, "_run_phase2", return_value=True) as mock_phase2:
        assert dream.run() is True
        mock_phase2.assert_called_once()
    assert store.get_last_dream_cursor() == 1


def test_dream_filters_ephemeral_counting_preferences(
    dream_env: tuple[Path, MagicMock],
) -> None:
    workspace, llm = dream_env
    store = get_memory_store()
    store.append_history("請慢慢數到 10，每秒數一次")
    llm.invoke.return_value = MagicMock(
        content="\n".join(
            [
                "[FILE] USER: 曾要求慢慢數到 10",
                "[FILE] USER: 想要「每秒數一次」的效果",
                "[FILE] USER: 偏好繁中簡潔回覆",
            ]
        )
    )

    dream = Dream(
        workspace,
        {"dream": {"cross_session_archive": False}},
        llm,
    )
    with patch.object(Dream, "_run_phase2", return_value=True) as mock_phase2:
        assert dream.run() is True
        mock_phase2.assert_called_once()
        filtered_analysis = mock_phase2.call_args.args[0]

    assert "慢慢數到 10" not in filtered_analysis
    assert "每秒數一次" not in filtered_analysis
    assert "[FILE] USER: 偏好繁中簡潔回覆" in filtered_analysis
