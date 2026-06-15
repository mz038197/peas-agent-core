"""Background Dream runner."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from peas_agent.dream_runner import get_dream_runner, poll_dream_message, submit_background_dream
from peas_agent.memory_store import configure_memory_store


def test_submit_returns_immediately_and_poll_notifies(tmp_path: Path) -> None:
    configure_memory_store(tmp_path)
    store = configure_memory_store(tmp_path)
    config = {"dream": {"cross_session_archive": False}}
    dream_llm = MagicMock()

    with patch("peas_agent.dream_runner.Dream") as mock_dream_cls:
        mock_dream_cls.return_value.run.return_value = True
        ok = submit_background_dream(
            tmp_path,
            config,
            store,
            dream_llm,
            session_path=None,
        )
        assert ok is True

        deadline = time.time() + 3.0
        message = None
        while time.time() < deadline:
            message = poll_dream_message(tmp_path)
            if message:
                break
            time.sleep(0.05)

    assert message == "（Dream 背景完成。）"
    get_dream_runner(tmp_path).poll_message()
