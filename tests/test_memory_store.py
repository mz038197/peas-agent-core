"""Tests for MemoryStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from peas_agent.memory_store import MemoryStore, configure_memory_store


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return configure_memory_store(tmp_path)


def test_append_and_read_history(store: MemoryStore) -> None:
    c1 = store.append_history("first fact", session_key="a.jsonl")
    c2 = store.append_history("second fact", session_key="b.jsonl")
    assert c1 == 1
    assert c2 == 2

    entries = store.read_unprocessed_history(since_cursor=0)
    assert len(entries) == 2
    assert entries[0]["session_key"] == "a.jsonl"
    assert entries[1]["content"] == "second fact"


def test_dream_cursor(store: MemoryStore) -> None:
    store.append_history("x")
    assert store.get_last_dream_cursor() == 0
    store.set_last_dream_cursor(1)
    assert store.get_last_dream_cursor() == 1
    unprocessed = store.read_unprocessed_history(since_cursor=1)
    assert unprocessed == []


def test_migrate_legacy_history(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    legacy = mem_dir / "HISTORY.md"
    legacy.write_text(
        "[2026-01-01 10:00] 討論專案 A\n\n[2026-01-02 11:00] 偏好繁中回覆\n",
        encoding="utf-8",
    )
    store = MemoryStore(tmp_path)
    assert store.history_file.is_file()
    entries = store._read_entries()
    assert len(entries) == 2
    assert store.get_last_dream_cursor() == 2
    assert not legacy.exists()
    assert (mem_dir / "HISTORY.md.bak").is_file()


def test_pinned(store: MemoryStore) -> None:
    store.add_pin("安靜晚餐")
    assert store.read_pinned() == ["安靜晚餐"]
    store.add_pin("安靜晚餐")
    assert store.read_pinned() == ["安靜晚餐"]


def test_configure_memory_store_reuses_existing_workspace_instance(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    (ws / "memory").mkdir(parents=True)

    first = configure_memory_store(ws)
    first.append_history("stable entry")
    second = configure_memory_store(ws)

    assert second is first
    entries = second.read_unprocessed_history(since_cursor=0)
    assert any("stable entry" in e.get("content", "") for e in entries)
