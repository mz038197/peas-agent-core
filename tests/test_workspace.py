"""Tests for peas-agent workspace, config, session, and LLM setup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from peas_agent.core import (
    PACKAGE_DIR,
    SkillsLoader,
    _build_llm,
    _default_config,
    _ensure_config,
    _new_session_path,
    _resolve_session_path,
    _resolve_workspace,
    _validate_session_name,
    get_token_budget,
    init_workspace,
)


@pytest.fixture
def peas_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "peas-agent"
    config_path = home / "config.json"
    monkeypatch.setattr("peas_agent.core.CONFIG_PATH_OVERRIDE", config_path)
    monkeypatch.setattr("peas_agent.core.DATA_DIR", home)
    monkeypatch.setattr("peas_agent.core.CONFIG_PATH", config_path)
    monkeypatch.setattr("peas_agent.core.DEFAULT_WORKSPACE", home / "workspace")
    return home


def test_default_config_shape() -> None:
    cfg = _default_config()
    assert cfg["token_budget"] == 100000
    assert cfg["llm"]["model"] == "gpt-5.4-mini"
    assert cfg["llm"]["api_key"] == ""


def test_ensure_config_scaffolds_on_first_run(peas_home: Path) -> None:
    config_path = peas_home / "config.json"
    assert not config_path.exists()
    loaded = _ensure_config()
    assert config_path.is_file()
    on_disk = json.loads(config_path.read_text(encoding="utf-8"))
    assert on_disk["llm"]["api_key"] == ""
    assert loaded["workspace"] == str(peas_home / "workspace")


def test_ensure_config_does_not_overwrite_existing(peas_home: Path) -> None:
    config_path = peas_home / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"workspace": "/custom", "token_budget": 42, "llm": {"api_key": "k"}}),
        encoding="utf-8",
    )
    loaded = _ensure_config()
    assert loaded["token_budget"] == 42
    assert json.loads(config_path.read_text(encoding="utf-8"))["token_budget"] == 42


def test_resolve_workspace_priority(peas_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _default_config()
    config["workspace"] = str(peas_home / "from-config")
    cli = peas_home / "from-cli"
    monkeypatch.delenv("PEAS_AGENT_WORKSPACE", raising=False)
    assert _resolve_workspace(cli, config) == cli.resolve()
    monkeypatch.setenv("PEAS_AGENT_WORKSPACE", str(peas_home / "from-env"))
    assert _resolve_workspace(None, config) == (peas_home / "from-env").resolve()
    monkeypatch.delenv("PEAS_AGENT_WORKSPACE", raising=False)
    assert _resolve_workspace(None, config) == (peas_home / "from-config").resolve()


def test_init_workspace_creates_subdirs(peas_home: Path) -> None:
    ws = init_workspace(peas_home / "workspace")
    assert (ws / "memory").is_dir()
    assert (ws / "sessions").is_dir()
    assert (ws / "skills").is_dir()
    assert (ws / "tools").is_dir()
    assert (ws / "AGENTS.md").is_file()


def test_validate_session_name_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        _validate_session_name("../escape.jsonl")
    with pytest.raises(ValueError):
        _validate_session_name("sub/foo.jsonl")


def test_resolve_session_path_named_file(peas_home: Path) -> None:
    ws = init_workspace(peas_home / "workspace")
    path = _resolve_session_path(ws, "my_chat.jsonl")
    assert path == ws / "sessions" / "my_chat.jsonl"


def test_resolve_session_path_defaults_to_session_jsonl(peas_home: Path) -> None:
    ws = init_workspace(peas_home / "workspace")
    path = _resolve_session_path(ws, None)
    assert path == ws / "sessions" / "session.jsonl"


def test_new_session_path_unique(peas_home: Path) -> None:
    session_dir = peas_home / "workspace" / "sessions"
    session_dir.mkdir(parents=True)
    p1 = _new_session_path(session_dir)
    p2 = _new_session_path(session_dir)
    assert p1 != p2
    assert p1.name.startswith("session_")
    assert p1.suffix == ".jsonl"


def test_build_llm_requires_api_key(peas_home: Path) -> None:
    with pytest.raises(RuntimeError, match="api_key"):
        _build_llm(_default_config())


def test_build_llm_passes_base_url(peas_home: Path) -> None:
    cfg = _default_config()
    cfg["llm"]["api_key"] = "test-key"
    cfg["llm"]["base_url"] = "https://example.com/v1"
    with patch("peas_agent.core.ChatOpenAI") as mock_cls:
        _build_llm(cfg)
        mock_cls.assert_called_once()
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["api_key"] == "test-key"
        assert kwargs["base_url"] == "https://example.com/v1"


def test_build_llm_omits_empty_base_url(peas_home: Path) -> None:
    cfg = _default_config()
    cfg["llm"]["api_key"] = "test-key"
    cfg["llm"]["base_url"] = ""
    with patch("peas_agent.core.ChatOpenAI") as mock_cls:
        _build_llm(cfg)
        assert "base_url" not in mock_cls.call_args.kwargs


def test_get_token_budget_reads_active_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("peas_agent.core._ACTIVE_CONFIG", {"token_budget": 250000})
    assert get_token_budget() == 250000


def test_skills_loader_reads_package_builtin(peas_home: Path) -> None:
    ws = init_workspace(peas_home / "workspace")
    loader = SkillsLoader(ws, builtin_dir=PACKAGE_DIR / "builtin_skills")
    entries = loader.list_skills()
    names = {e.name for e in entries}
    assert "always-on" in names or "demo" in names
