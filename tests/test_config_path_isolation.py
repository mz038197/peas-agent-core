"""Tests for per-Agent config_path isolation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage

from peas_agent.core import Agent, _default_config, init_workspace


@pytest.fixture
def peas_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "peas-agent"
    monkeypatch.setattr("peas_agent.core.DATA_DIR", home)
    monkeypatch.setattr("peas_agent.core.DEFAULT_WORKSPACE", home / "workspace")
    return home


def _write_config(path: Path, *, effort: str) -> None:
    cfg = _default_config()
    cfg["llm"]["api_key"] = "test-key"
    cfg["llm"]["reasoning"] = {"effort": effort, "summary": "auto"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _patch_agent_deps(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    build_calls: list[dict] = []

    def fake_build_llm(config: dict):
        build_calls.append(dict(config))
        llm = MagicMock(name="llm")
        llm.bind_tools.return_value = MagicMock(name="llm_tools")
        return llm

    monkeypatch.setattr("peas_agent.core._build_llm", fake_build_llm)
    monkeypatch.setattr("peas_agent.core._load_all_tools", lambda: [])
    monkeypatch.setattr("peas_agent.dream_scheduler.ensure_dream_scheduler", lambda *a, **k: None)
    return build_calls


def test_reload_reads_agent_config_path(
    peas_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = init_workspace(peas_home / "workspace")
    config_a = peas_home / "users" / "a" / "effective_config.json"
    config_b = peas_home / "users" / "b" / "effective_config.json"
    _write_config(config_a, effort="low")
    _write_config(config_b, effort="high")
    build_calls = _patch_agent_deps(monkeypatch)

    agent_a = Agent.create(workspace=ws, config_path=config_a)
    agent_b = Agent.create(workspace=ws, config_path=config_b)
    assert build_calls[0]["llm"]["reasoning"]["effort"] == "low"
    assert build_calls[1]["llm"]["reasoning"]["effort"] == "high"

    _write_config(config_a, effort="medium")
    agent_a.history.append(HumanMessage(content="hello"))
    original_history = list(agent_a.history)
    agent_a.reload_llm_config()

    assert agent_a.config["llm"]["reasoning"]["effort"] == "medium"
    assert build_calls[-1]["llm"]["reasoning"]["effort"] == "medium"
    assert agent_a.history == original_history
    assert agent_b.config["llm"]["reasoning"]["effort"] == "high"
