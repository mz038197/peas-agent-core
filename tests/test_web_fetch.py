"""Tests for web_fetch (MarkItDown-backed)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from peas_agent.core import (
    TOOLS,
    _extract_markitdown_text,
    _validate_fetch_url,
    web_fetch,
)


def test_tools_include_web_fetch() -> None:
    names = {t.name for t in TOOLS}
    assert "web_fetch" in names


@pytest.mark.parametrize(
    ("url", "fragment"),
    [
        ("http://127.0.0.1/", "blocked"),
        ("https://localhost/docs", "blocked"),
        ("file:///etc/passwd", "http/https"),
    ],
)
def test_validate_fetch_url_rejects_unsafe(url: str, fragment: str) -> None:
    cleaned, err = _validate_fetch_url(url)
    assert cleaned is None
    assert err is not None
    assert fragment in err


def test_validate_fetch_url_accepts_public_https() -> None:
    cleaned, err = _validate_fetch_url("https://example.com/page")
    assert err is None
    assert cleaned == "https://example.com/page"


def test_extract_markitdown_text_prefers_text_content() -> None:
    result = SimpleNamespace(text_content="# Title\n\nbody", markdown="ignored")
    assert "Title" in _extract_markitdown_text(result)


def test_web_fetch_returns_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(text_content="# Hello\n\nfrom the web")

    class FakeMarkItDown:
        def convert(self, url: str) -> SimpleNamespace:
            assert url == "https://example.com"
            return fake

    monkeypatch.setattr("peas_agent.core._MARKITDOWN", FakeMarkItDown())
    out = web_fetch.invoke({"url": "https://example.com"})
    assert "Hello" in out
    assert "from the web" in out


def test_web_fetch_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(text_content="x" * 200)

    class FakeMarkItDown:
        def convert(self, url: str) -> SimpleNamespace:
            return fake

    monkeypatch.setattr("peas_agent.core._MARKITDOWN", FakeMarkItDown())
    out = web_fetch.invoke({"url": "https://example.com", "max_chars": 100})
    assert len(out) < 200
    assert "[truncated at 100 characters]" in out


def test_web_fetch_blocks_localhost_without_network() -> None:
    out = web_fetch.invoke({"url": "http://127.0.0.1/"})
    assert "blocked" in out.lower()
