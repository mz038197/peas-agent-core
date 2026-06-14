"""Tests for per-agent MemoryStore isolation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from peas_agent.core import Agent, init_workspace
from peas_agent.memory_store import configure_memory_store, get_memory_store


@pytest.fixture
def agent_config() -> dict:
    return {
        "token_budget": 128000,
        "dream": {"enabled": False, "cross_session_archive": False},
    }


def _make_workspace(root: Path, name: str) -> Path:
    ws = init_workspace(root / name)
    (ws / "memory" / "MEMORY.md").write_text(f"# memory for {name}\n", encoding="utf-8")
    return ws


def test_configure_memory_store_keeps_workspace_specific_instances(tmp_path: Path) -> None:
    ws_a = tmp_path / "a"
    ws_b = tmp_path / "b"
    (ws_a / "memory").mkdir(parents=True)
    (ws_b / "memory").mkdir(parents=True)

    store_a = configure_memory_store(ws_a)
    store_a.append_history("history for A")

    store_b = configure_memory_store(ws_b)
    store_b.append_history("history for B")

    assert get_memory_store(ws_a) is store_a
    assert get_memory_store(ws_b) is store_b
    assert store_a is not store_b

    a_entries = store_a.read_unprocessed_history(since_cursor=0)
    b_entries = store_b.read_unprocessed_history(since_cursor=0)
    assert any("history for A" in e.get("content", "") for e in a_entries)
    assert not any("history for A" in e.get("content", "") for e in b_entries)
    assert any("history for B" in e.get("content", "") for e in b_entries)


def test_agent_create_preserves_store_when_later_agent_uses_other_workspace(
    tmp_path: Path, agent_config: dict
) -> None:
    ws_a = _make_workspace(tmp_path, "workspace-a")
    ws_b = _make_workspace(tmp_path, "workspace-b")

    class FakeBound:
        def __init__(self, tools: list) -> None:
            self.tools = tools

    class FakeLLM:
        def bind_tools(self, tools: list) -> FakeBound:
            return FakeBound(tools)

    fake_llm = FakeLLM()

    with (
        patch("peas_agent.core._ensure_config", return_value=agent_config),
        patch("peas_agent.core._build_llm", return_value=fake_llm),
        patch("peas_agent.core.load_session_jsonl", return_value=([], None)),
        patch("peas_agent.dream_scheduler.ensure_dream_scheduler", return_value=None),
    ):
        agent_a = Agent.create(workspace=ws_a)
        agent_b = Agent.create(workspace=ws_b)

    agent_a.store.append_history("agent A memory")
    agent_b.store.append_history("agent B memory")

    assert agent_a.store.workspace == ws_a.resolve()
    assert agent_b.store.workspace == ws_b.resolve()
    assert agent_a.store is not agent_b.store

    a_entries = agent_a.store.read_unprocessed_history(since_cursor=0)
    b_entries = agent_b.store.read_unprocessed_history(since_cursor=0)
    assert any("agent A memory" in e.get("content", "") for e in a_entries)
    assert not any("agent A memory" in e.get("content", "") for e in b_entries)
    assert any("agent B memory" in e.get("content", "") for e in b_entries)
