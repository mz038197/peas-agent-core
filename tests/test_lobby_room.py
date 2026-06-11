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


def test_rejoin_removes_stale_connection_index(tmp_path: Path) -> None:
    room = Room(config=RoomConfig(room_id="T"), workspace=tmp_path)

    ok1 = asyncio.run(room.handle_join("c1", display_name="Alice", rejoin_token=None))
    token = ok1["rejoin_token"]

    ok2 = asyncio.run(room.handle_join("c2", display_name=None, rejoin_token=token))
    assert ok2["type"] == "join_ok"
    assert room.members["m001"].connection_id == "c2"
    assert "c1" not in room.connection_index
    assert room.connection_index["c2"] == "m001"

    asyncio.run(room.disconnect("c1"))
    assert room.members["m001"].online is True

    asyncio.run(room.disconnect("c2"))
    assert room.members["m001"].online is False


def test_rejoin_stale_disconnect_preserves_turn(tmp_path: Path) -> None:
    async def _run() -> None:
        room = Room(config=RoomConfig(room_id="T"), workspace=tmp_path)

        ok = await room.handle_join("c1", display_name="Alice", rejoin_token=None)
        await room.grant_turn("m001", skip_gap=True)

        await room.handle_join("c2", display_name=None, rejoin_token=ok["rejoin_token"])
        await room.disconnect("c1")

        assert room.members["m001"].online is True
        assert room.current_speaker == "m001"

    asyncio.run(_run())


def test_invalid_rejoin_token_is_rejected(tmp_path: Path) -> None:
    room = Room(config=RoomConfig(room_id="T"), workspace=tmp_path)

    asyncio.run(room.handle_join("c1", display_name="Alice", rejoin_token=None))

    reject = asyncio.run(
        room.handle_join("c2", display_name="Bob", rejoin_token="not-a-real-token")
    )
    assert reject["type"] == "join_rejected"
    assert reject["reason"] == "invalid_rejoin_token"
    assert len(room.members) == 1
    assert "m002" not in room.members
