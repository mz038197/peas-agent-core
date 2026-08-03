from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from peas_agent.core import (
    _read_image_tool,
    _sync_tools_config,
    get_exec_default_timeout,
)


def _set_project_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", root.resolve())


def test_get_exec_default_timeout_from_config(monkeypatch) -> None:
    monkeypatch.setattr(
        "peas_agent.core._ACTIVE_CONFIG",
        {"exec": {"default_timeout": 90}},
    )
    assert get_exec_default_timeout() == 90


def test_get_exec_default_timeout_fallback(monkeypatch) -> None:
    monkeypatch.setattr("peas_agent.core._ACTIVE_CONFIG", {})
    assert get_exec_default_timeout() == 120


def test_read_image_missing_file(tmp_path: Path, monkeypatch) -> None:
    _set_project_root(monkeypatch, tmp_path)
    out = _read_image_tool().invoke({"path": "missing.png"})
    assert out.startswith("Error: not a file:")


def test_read_image_unsupported_extension(tmp_path: Path, monkeypatch) -> None:
    _set_project_root(monkeypatch, tmp_path)
    gif = tmp_path / "x.gif"
    gif.write_bytes(b"GIF89a")
    out = _read_image_tool().invoke({"path": "x.gif"})
    assert "unsupported image type" in out


def test_read_image_too_large(tmp_path: Path, monkeypatch) -> None:
    _set_project_root(monkeypatch, tmp_path)
    png = tmp_path / "big.png"
    png.write_bytes(b"\x00" * (8 * 1024 * 1024 + 1))
    out = _read_image_tool().invoke({"path": "big.png"})
    assert "image too large" in out


def test_read_image_success(tmp_path: Path, monkeypatch) -> None:
    _set_project_root(monkeypatch, tmp_path)
    png = tmp_path / "screen.png"
    png.write_bytes(b"\x89PNG\r\n")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="filter chip 顯示 BMW")

    with patch("peas_agent.core._build_llm", return_value=mock_llm):
        out = _read_image_tool().invoke(
            {"path": "screen.png", "question": "filter 是否為 BMW？"}
        )

    assert "[read_image: screen.png]" in out
    assert "Question: filter 是否為 BMW？" in out
    assert "Analysis:" in out
    assert "BMW" in out
    mock_llm.invoke.assert_called_once()
    human = mock_llm.invoke.call_args.args[0][0]
    assert isinstance(human.content, list)
    assert any(b.get("type") == "image_url" for b in human.content if isinstance(b, dict))


def test_read_image_vision_api_error(tmp_path: Path, monkeypatch) -> None:
    _set_project_root(monkeypatch, tmp_path)
    png = tmp_path / "screen.png"
    png.write_bytes(b"\x89PNG\r\n")

    with patch(
        "peas_agent.core._build_llm",
        side_effect=RuntimeError("尚未設定 llm.api_key"),
    ):
        out = _read_image_tool().invoke({"path": "screen.png"})

    assert out.startswith("Error:")


def test_read_image_empty_vision_response(tmp_path: Path, monkeypatch) -> None:
    _set_project_root(monkeypatch, tmp_path)
    png = tmp_path / "screen.png"
    png.write_bytes(b"\x89PNG\r\n")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="   ")

    with patch("peas_agent.core._build_llm", return_value=mock_llm):
        out = _read_image_tool().invoke({"path": "screen.png"})

    assert "empty response" in out


def test_sync_tools_config_uses_core_globals(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", project.resolve())
    monkeypatch.setattr("peas_agent.core.WORKSPACE", workspace.resolve())
    _sync_tools_config()
    from peas_agent_tools import get_settings

    settings = get_settings()
    assert settings.project_root == project.resolve()
    assert settings.workspace == workspace.resolve()
