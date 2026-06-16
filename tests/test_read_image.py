from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from peas_agent.core import (
    get_exec_default_timeout,
    read_image,
)


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
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", tmp_path.resolve())
    out = read_image.invoke({"path": "missing.png"})
    assert out.startswith("Error: not a file:")


def test_read_image_unsupported_extension(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", tmp_path.resolve())
    gif = tmp_path / "x.gif"
    gif.write_bytes(b"GIF89a")
    out = read_image.invoke({"path": "x.gif"})
    assert "unsupported image type" in out


def test_read_image_too_large(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", tmp_path.resolve())
    png = tmp_path / "big.png"
    png.write_bytes(b"\x00" * (8 * 1024 * 1024 + 1))
    out = read_image.invoke({"path": "big.png"})
    assert "image too large" in out


def test_read_image_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", tmp_path.resolve())
    png = tmp_path / "screen.png"
    png.write_bytes(b"\x89PNG\r\n")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="filter chip 顯示 BMW")

    with patch("peas_agent.core._build_llm", return_value=mock_llm):
        out = read_image.invoke(
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
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", tmp_path.resolve())
    png = tmp_path / "screen.png"
    png.write_bytes(b"\x89PNG\r\n")

    with patch(
        "peas_agent.core._build_llm",
        side_effect=RuntimeError("尚未設定 llm.api_key"),
    ):
        out = read_image.invoke({"path": "screen.png"})

    assert out.startswith("Error:")


def test_read_image_empty_vision_response(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("peas_agent.core.PROJECT_ROOT", tmp_path.resolve())
    png = tmp_path / "screen.png"
    png.write_bytes(b"\x89PNG\r\n")

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="   ")

    with patch("peas_agent.core._build_llm", return_value=mock_llm):
        out = read_image.invoke({"path": "screen.png"})

    assert "empty response" in out
