"""測試預設不連 Vans MCP Portal。個別測試可再覆寫 fetch_tools_async。"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def portal_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refuse(connections: dict) -> list:
        raise RuntimeError("unit tests do not call the Portal")

    monkeypatch.setattr("peas_agent_mcp.registry.fetch_tools_async", refuse)
