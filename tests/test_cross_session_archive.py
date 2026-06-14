"""Tests for cross-session archive cursor sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from peas_agent.core import (
    _message_plaintext,
    load_session_jsonl,
    save_session_jsonl,
)
from peas_agent.memory_archive import (
    CONSOLIDATION_MAX_RETRIES,
    archive_session_chunk,
    cross_session_archive,
    pick_archive_end,
)
from peas_agent.memory_store import configure_memory_store, get_memory_store


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "sessions").mkdir()
    (tmp_path / "memory").mkdir()
    configure_memory_store(tmp_path)
    return tmp_path


def test_cross_session_advances_last_consolidated(workspace: Path) -> None:
    store = get_memory_store()
    session_b = workspace / "sessions" / "b.jsonl"
    history = [
        HumanMessage(content="我偏好安靜晚餐"),
        AIMessage(content="了解"),
    ]
    save_session_jsonl(str(session_b), history, None, 0)

    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="- 偏好安靜晚餐")

    count = cross_session_archive(
        workspace,
        str(workspace / "sessions" / "a.jsonl"),
        llm,
        store,
        load_session_jsonl=load_session_jsonl,
        save_session_jsonl=save_session_jsonl,
        message_plaintext=_message_plaintext,
    )
    assert count >= 1

    loaded, meta = load_session_jsonl(str(session_b))
    assert meta is not None
    assert meta["last_consolidated"] == len(history)

    entries = store.read_unprocessed_history(since_cursor=0)
    assert any("安靜" in e.get("content", "") for e in entries)


def test_pick_archive_end_splits_at_human_within_window() -> None:
    """end is exclusive; boundary search must not inspect messages[end]."""
    messages = [
        AIMessage(content="a"),
        AIMessage(content="b"),
        HumanMessage(content="c"),
        HumanMessage(content="d"),
    ]
    # Window [0:3) — human at index 2 is in-range; human at index 3 is not.
    assert pick_archive_end(messages, 0, max_messages=3) == 2


def test_pick_archive_end_returns_full_window_when_no_human_boundary() -> None:
    messages = [
        AIMessage(content="a"),
        AIMessage(content="b"),
        AIMessage(content="c"),
        HumanMessage(content="d"),
    ]
    assert pick_archive_end(messages, 0, max_messages=3) == 3


def test_pick_archive_end_splits_when_human_at_start() -> None:
    """HumanMessage at start must be found; return start+1 to avoid an empty chunk."""
    messages = [
        AIMessage(content="a"),
        HumanMessage(content="b"),
        AIMessage(content="c"),
        AIMessage(content="d"),
    ]
    assert pick_archive_end(messages, 1, max_messages=2) == 2


def test_pick_archive_end_human_at_start_does_not_skip_on_next_iteration() -> None:
    messages = [
        AIMessage(content="a"),
        HumanMessage(content="b"),
        AIMessage(content="c"),
        AIMessage(content="d"),
    ]
    first_end = pick_archive_end(messages, 0, max_messages=1)
    assert first_end == 1
    second_end = pick_archive_end(messages, first_end, max_messages=2)
    assert second_end == 2
    assert messages[first_end:second_end] == [messages[1]]


def test_archive_session_chunk_retries_after_llm_exception(workspace: Path) -> None:
    store = get_memory_store()
    llm = MagicMock()
    llm.invoke.side_effect = [
        RuntimeError("network error"),
        RuntimeError("api error"),
        MagicMock(content="- recovered summary"),
    ]
    chunk = [HumanMessage(content="retry me")]

    assert archive_session_chunk(
        llm,
        store,
        chunk,
        "session.jsonl",
        message_plaintext=_message_plaintext,
    )
    assert llm.invoke.call_count == 3

    entries = store.read_unprocessed_history(since_cursor=0)
    assert any("recovered summary" in e.get("content", "") for e in entries)


def test_archive_session_chunk_appends_failure_marker_after_exhausted_retries(
    workspace: Path,
) -> None:
    store = get_memory_store()
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("network error")
    chunk = [HumanMessage(content="will fail gracefully")]

    assert (
        archive_session_chunk(
            llm,
            store,
            chunk,
            "session.jsonl",
            message_plaintext=_message_plaintext,
        )
        is False
    )
    assert llm.invoke.call_count == CONSOLIDATION_MAX_RETRIES

    entries = store.read_unprocessed_history(since_cursor=0)
    assert any(
        "[CONSOLIDATION-FAILED]" in e.get("content", "")
        and "will fail gracefully" in e.get("content", "")
        for e in entries
    )
