"""Tests for Agent.reload_llm_config()."""

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
    config_path = home / "config.json"
    monkeypatch.setattr("peas_agent.core.CONFIG_PATH_OVERRIDE", config_path)
    monkeypatch.setattr("peas_agent.core.DATA_DIR", home)
    monkeypatch.setattr("peas_agent.core.CONFIG_PATH", config_path)
    monkeypatch.setattr("peas_agent.core.DEFAULT_WORKSPACE", home / "workspace")
    return home


def _patch_agent_create_deps(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
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


def _write_config(path: Path, cfg: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_reload_llm_config_rebuilds_clients_and_preserves_history(
    peas_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = init_workspace(peas_home / "workspace")
    config_path = peas_home / "config.json"
    cfg = _default_config()
    cfg["workspace"] = str(ws)
    cfg["llm"]["api_key"] = "test-key"
    cfg["llm"]["reasoning"] = {"effort": "medium", "summary": "auto"}
    _write_config(config_path, cfg)
    build_calls = _patch_agent_create_deps(monkeypatch)

    agent = Agent.create(workspace=ws)
    agent.history.append(HumanMessage(content="hello"))
    original_history = list(agent.history)
    original_llm_tools = agent.llm_tools

    cfg["llm"]["reasoning"] = {"effort": "high", "summary": "auto"}
    _write_config(config_path, cfg)
    agent.reload_llm_config()

    assert len(build_calls) == 2
    assert build_calls[-1]["llm"]["reasoning"]["effort"] == "high"
    assert agent.config["llm"]["reasoning"]["effort"] == "high"
    import peas_agent.core as core

    assert core._ACTIVE_CONFIG["llm"]["reasoning"]["effort"] == "high"
    assert agent.history == original_history
    assert agent.llm_tools is not original_llm_tools
