import asyncio
from pathlib import Path

import pytest

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.room import Room


@pytest.mark.asyncio
async def test_turn_gap_before_next_grant(tmp_path: Path) -> None:
    events: list[str] = []

    async def broadcast(event: dict, target_connection_id: str | None = None) -> None:
        events.append(event.get("type", ""))

    room = Room(
        config=RoomConfig(room_id="T", turn_gap_sec=1, skip_gap_on_first_grant=True),
        workspace=tmp_path,
    )
    room.set_broadcast(broadcast)

    await room.handle_join("c1", display_name="Alice", rejoin_token=None)
    await room.handle_join("c2", display_name="Bob", rejoin_token=None)
    await room.grant_turn("m001", skip_gap=True)
    await room.handle_say("m001", "hello @Bob")
    await room.handle_turn_done("m001")

    assert "turn_pending" in events
    await asyncio.sleep(1.1)
    assert "turn_granted" in events
