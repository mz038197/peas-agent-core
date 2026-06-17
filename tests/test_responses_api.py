"""Tests for Responses API streaming and config merge."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from peas_agent.core import (
    _build_llm,
    _default_config,
    _ensure_config,
    _merge_config_defaults,
    _stream_model_response,
    run_react_turn,
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


def test_merge_config_defaults_adds_missing_nested_keys() -> None:
    loaded = {"llm": {"api_key": "k", "model": "m"}}
    merged, changed = _merge_config_defaults(loaded, _default_config())
    assert changed is True
    assert merged["llm"]["api_key"] == "k"
    assert merged["llm"]["use_responses_api"] is True
    assert merged["llm"]["reasoning"]["effort"] == "medium"


def test_merge_config_defaults_does_not_overwrite_existing() -> None:
    loaded = {"token_budget": 42, "llm": {"api_key": "k", "use_responses_api": False}}
    merged, changed = _merge_config_defaults(loaded, _default_config())
    assert merged["token_budget"] == 42
    assert merged["llm"]["use_responses_api"] is False


def test_ensure_config_merges_old_file(peas_home: Path) -> None:
    config_path = peas_home / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"workspace": "/custom", "token_budget": 42, "llm": {"api_key": "k"}}),
        encoding="utf-8",
    )
    loaded = _ensure_config()
    assert loaded["token_budget"] == 42
    on_disk = json.loads(config_path.read_text(encoding="utf-8"))
    assert on_disk["llm"]["use_responses_api"] is True
    assert on_disk["llm"]["api_key"] == "k"


def test_build_llm_passes_responses_api_flags() -> None:
    cfg = _default_config()
    cfg["llm"]["api_key"] = "test-key"
    cfg["llm"]["use_responses_api"] = True
    cfg["llm"]["output_version"] = "responses/v1"
    cfg["llm"]["reasoning"] = {"effort": "low", "summary": "auto"}
    with patch("peas_agent.core.ChatOpenAI") as mock_cls:
        _build_llm(cfg)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["use_responses_api"] is True
        assert kwargs["output_version"] == "responses/v1"
        assert kwargs["reasoning"] == {"effort": "low", "summary": "auto"}


def test_stream_model_response_routes_callbacks() -> None:
    chunks = [
        AIMessageChunk(content=[{"type": "reasoning", "reasoning": "a"}]),
        AIMessageChunk(content=[{"type": "text", "text": "b"}]),
    ]
    llm = MagicMock()
    llm.stream.return_value = iter(chunks)
    reasoning: list[str] = []
    tokens: list[str] = []

    message = _stream_model_response(
        llm,
        [HumanMessage(content="hi")],
        on_token=tokens.append,
        on_reasoning=reasoning.append,
    )

    assert reasoning == ["a"]
    assert tokens == ["b"]
    assert isinstance(message, AIMessage)


def test_run_react_turn_calls_on_stream_reset_on_tool_round(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_response = AIMessage(
        content="",
        tool_calls=[{"name": "add_numbers", "args": {"a": 1, "b": 2}, "id": "1"}],
    )
    final_response = AIMessage(content=[{"type": "text", "text": "done"}])
    calls = {"n": 0}

    def fake_stream(*_args, **_kwargs):
        calls["n"] += 1
        return final_response if calls["n"] > 1 else tool_response

    monkeypatch.setattr("peas_agent.core._stream_model_response", fake_stream)
    monkeypatch.setattr("peas_agent.core._run_bound_tool", lambda name, args: "3")

    resets: list[str] = []

    final_text, _turn = run_react_turn(
        MagicMock(),
        "sys",
        [],
        HumanMessage(content="q"),
        on_stream_reset=lambda: resets.append("reset"),
    )

    assert resets == ["reset"]
    assert final_text == "done"
