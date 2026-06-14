"""Tests for GitStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from peas_agent.git_store import GitStore


@pytest.fixture
def git_store(tmp_path: Path) -> GitStore:
    store = GitStore(
        tmp_path,
        tracked_files=["SOUL.md", "USER.md", "memory/MEMORY.md", "memory/.dream_cursor"],
    )
    store.init()
    return store


def test_init_creates_repo(git_store: GitStore, tmp_path: Path) -> None:
    assert (tmp_path / ".git").is_dir()
    assert git_store.is_initialized()


def test_auto_commit(git_store: GitStore, tmp_path: Path) -> None:
    (tmp_path / "memory").mkdir(exist_ok=True)
    mem = tmp_path / "memory" / "MEMORY.md"
    mem.write_text("- fact\n", encoding="utf-8")
    sha = git_store.auto_commit("dream: test")
    assert sha is not None
    assert len(git_store.log()) >= 2
