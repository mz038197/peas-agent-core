"""Tests for web_fetch (httpx + Jina/readability, nanobot-aligned)."""

from __future__ import annotations

import json
import socket
from unittest.mock import patch

import httpx
import pytest

from peas_agent.builtin_web import _run_web_fetch, configure_web, web_fetch
from peas_agent.core import _get_builtin_tools


def _fake_resolve_public(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


def _fake_resolve_private(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))]


def _fake_resolve_localhost(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]


@pytest.fixture(autouse=True)
def _web_config() -> None:
    configure_web(
        {
            "tools": {
                "web": {
                    "fetch": {"useJinaReader": False, "maxChars": 50000},
                }
            }
        }
    )


def test_tools_include_web_fetch() -> None:
    names = {t.name for t in _get_builtin_tools()}
    assert "web_fetch" in names


@pytest.mark.parametrize(
    ("url", "fragment"),
    [
        ("http://127.0.0.1/", "blocked"),
        ("https://localhost/docs", "blocked"),
        ("file:///etc/passwd", "http/https"),
    ],
)
def test_web_fetch_blocks_unsafe_urls(url: str, fragment: str) -> None:
    with patch("peas_agent.security.network.socket.getaddrinfo", _fake_resolve_localhost):
        out = _run_web_fetch(url)
    data = json.loads(out)
    assert "error" in data
    assert fragment.lower() in data["error"].lower()


def test_web_fetch_blocks_private_ip() -> None:
    with patch("peas_agent.security.network.socket.getaddrinfo", _fake_resolve_private):
        out = _run_web_fetch("http://169.254.169.254/computeMetadata/v1/")
    data = json.loads(out)
    assert "error" in data


def test_web_fetch_result_contains_untrusted_flag() -> None:
    fake_html = "<html><head><title>Test</title></head><body><p>Hello world</p></body></html>"

    class FakeResponse:
        status_code = 200
        url = "https://example.com/page"

        def __init__(self) -> None:
            self.headers = {"content-type": "text/html"}
            self.text = fake_html

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

        def close(self) -> None:
            return None

    def _fake_get(self, url, **kwargs):
        return FakeResponse()

    with (
        patch("peas_agent.security.network.socket.getaddrinfo", _fake_resolve_public),
        patch("httpx.Client.get", _fake_get),
    ):
        out = web_fetch.invoke({"url": "https://example.com/page"})

    data = json.loads(out)
    assert data.get("untrusted") is True
    assert "[External content" in data.get("text", "")
    assert "Hello world" in data.get("text", "")


def test_web_fetch_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_web({"tools": {"web": {"fetch": {"useJinaReader": False, "maxChars": 100}}}})
    fake_html = "<html><body>" + ("x" * 200) + "</body></html>"

    class FakeResponse:
        status_code = 200
        url = "https://example.com/page"

        def __init__(self) -> None:
            self.headers = {"content-type": "text/html"}
            self.text = fake_html

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {}

        def close(self) -> None:
            return None

    def _fake_get(self, url, **kwargs):
        return FakeResponse()

    with (
        patch("peas_agent.security.network.socket.getaddrinfo", _fake_resolve_public),
        patch("httpx.Client.get", _fake_get),
    ):
        out = web_fetch.invoke({"url": "https://example.com", "max_chars": 100})

    data = json.loads(out)
    assert data.get("truncated") is True
    assert len(data.get("text", "")) <= 200


def test_web_fetch_blocks_localhost_without_network() -> None:
    out = web_fetch.invoke({"url": "http://127.0.0.1/"})
    data = json.loads(out)
    assert "error" in data
