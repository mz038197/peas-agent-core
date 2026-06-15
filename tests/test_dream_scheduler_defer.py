"""Dream scheduler defers when chat is active."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from peas_agent.chat_activity import chat_activity
from peas_agent.dream_scheduler import DreamScheduler


def test_scheduler_tick_defers_during_chat(tmp_path: Path) -> None:
    config = {
        "llm": {"api_key": "test-key", "model": "gpt-test"},
        "dream": {"enabled": True, "cron": "0 */2 * * *"},
    }
    scheduler = DreamScheduler(tmp_path, config)

    with chat_activity():
        with patch("peas_agent.dream_scheduler.Dream") as mock_dream_cls:
            scheduler._tick()
            mock_dream_cls.assert_not_called()
