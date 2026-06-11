import asyncio
from pathlib import Path

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.room import Room


def _room_with_alice_and_bob(tmp_path: Path) -> Room:
    room = Room(
        config=RoomConfig(
            room_id="T",
            mention_enabled=True,
            round_robin_enabled=True,
        ),
        workspace=tmp_path,
    )

    async def setup() -> None:
        await room.handle_join("c1", display_name="Alice", rejoin_token=None)
        await room.handle_join("c2", display_name="Bob", rejoin_token=None)

    asyncio.run(setup())
    return room


def test_round_robin_when_message_has_no_mentions(tmp_path: Path) -> None:
    room = _room_with_alice_and_bob(tmp_path)

    room._enqueue_from_text("hello everyone", speaker_id="m001")

    assert room.speak_queue == ["m002"]


def test_round_robin_when_only_self_mention(tmp_path: Path) -> None:
    room = _room_with_alice_and_bob(tmp_path)

    room._enqueue_from_text("I'll go @Alice", speaker_id="m001")

    assert room.speak_queue == ["m002"]


def test_mention_takes_priority_over_round_robin(tmp_path: Path) -> None:
    room = _room_with_alice_and_bob(tmp_path)

    room._enqueue_from_text("question for @Bob", speaker_id="m001")

    assert room.speak_queue == ["m002"]
