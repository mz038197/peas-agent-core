"""Tests for web_search (DuckDuckGo / Brave / Tavily)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from peas_agent.builtin_web import (
    _dispatch_search,
    _resolve_search_provider,
    configure_web,
    web_search,
)
from peas_agent.core import _get_builtin_tools


@pytest.fixture(autouse=True)
def _web_config() -> None:
    configure_web({"tools": {"web": {"search": {"provider": "duckduckgo", "maxResults": 5}}}})


def test_tools_include_web_search() -> None:
    names = {t.name for t in _get_builtin_tools()}
    assert "web_search" in names


def test_web_search_formats_duckduckgo_results() -> None:
    fake_results = [
        {"title": "Python", "href": "https://python.org", "body": "Official site"},
        {"title": "Docs", "href": "https://docs.python.org", "body": "Documentation"},
    ]

    class FakeDDGS:
        def __init__(self, timeout: int = 10) -> None:
            pass

        def text(self, query: str, max_results: int = 5):
            assert query == "python"
            assert max_results == 3
            return fake_results

    with patch("ddgs.DDGS", FakeDDGS):
        out = web_search.invoke({"query": "python", "count": 3})

    assert "Results for: python" in out
    assert "https://python.org" in out
    assert "Official site" in out


def test_web_search_clamps_count() -> None:
    with patch("peas_agent.builtin_web._search_duckduckgo") as mock_search:
        mock_search.return_value = "ok"
        web_search.invoke({"query": "test", "count": 99})
        mock_search.assert_called_once_with("test", 10)


def test_brave_falls_back_without_api_key() -> None:
    configure_web({"tools": {"web": {"search": {"provider": "brave", "apiKey": ""}}}})
    assert _resolve_search_provider() == "duckduckgo"


def test_brave_search_uses_api(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_web(
        {
            "tools": {
                "web": {
                    "search": {"provider": "brave", "apiKey": "test-brave-key"},
                }
            }
        }
    )

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "web": {
                    "results": [
                        {
                            "title": "Example",
                            "url": "https://example.com",
                            "description": "An example site",
                        }
                    ]
                }
            }

    class FakeClient:
        def __init__(self, proxy=None) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            assert kwargs["headers"]["X-Subscription-Token"] == "test-brave-key"
            return FakeResponse()

    monkeypatch.setattr("peas_agent.builtin_web.httpx.Client", FakeClient)
    out = _dispatch_search("example", 1)
    assert "https://example.com" in out
    assert "Example" in out


def test_tavily_falls_back_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_web({"tools": {"web": {"search": {"provider": "tavily", "apiKey": ""}}}})
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert _resolve_search_provider() == "duckduckgo"


def test_unknown_provider_returns_error() -> None:
    configure_web({"tools": {"web": {"search": {"provider": "unknown-provider"}}}})
    out = _dispatch_search("test", 3)
    assert "unknown search provider" in out
