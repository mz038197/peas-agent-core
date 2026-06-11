import asyncio
from pathlib import Path

import pytest

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.room import Room


@pytest.mark.asyncio
async def test_join_rejects_duplicate_display_name(tmp_path: Path) -> None:
    events: list[dict] = []

    async def broadcast(event: dict, target_connection_id: str | None = None) -> None:
        events.append(event)

    room = Room(config=RoomConfig(room_id="T"), workspace=tmp_path)
    room.set_broadcast(broadcast)

    ok1 = await room.handle_join("c1", display_name="Alice", rejoin_token=None)
    assert ok1["type"] == "join_ok"

    ok2 = await room.handle_join("c2", display_name="Alice", rejoin_token=None)
    assert ok2["type"] == "join_rejected"
    assert ok2["reason"] == "display_name_taken"


@pytest.mark.asyncio
async def test_first_join_auto_grants(tmp_path: Path) -> None:
    granted: list[str] = []

    async def broadcast(event: dict, target_connection_id: str | None = None) -> None:
        if event.get("type") == "turn_granted":
            granted.append(event["agent_id"])

    room = Room(config=RoomConfig(room_id="T"), workspace=tmp_path)
    room.set_broadcast(broadcast)

    await room.handle_join("c1", display_name="Alice", rejoin_token=None)
    await room.grant_turn("m001", skip_gap=True)
    await asyncio.sleep(0.05)
    assert granted == ["m001"]
