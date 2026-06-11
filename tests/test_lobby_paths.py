from pathlib import Path

import pytest

from peas_agent.lobby.paths import InvalidRoomIdError, room_config_path, validate_room_id


def test_validate_room_id_accepts_safe_ids() -> None:
    assert validate_room_id("MATH-2026") == "MATH-2026"
    assert validate_room_id("  T  ") == "T"


@pytest.mark.parametrize(
    "room_id",
    ["../evil", "a/b", "..", "room/name", "room\\name", ""],
)
def test_validate_room_id_rejects_unsafe_ids(room_id: str) -> None:
    with pytest.raises(InvalidRoomIdError):
        validate_room_id(room_id)


def test_room_config_path_stays_under_rooms_dir(tmp_path: Path) -> None:
    path = room_config_path(tmp_path, "SAFE-ROOM")
    assert path.parent.name == "rooms"
    assert path.name == "SAFE-ROOM.json"
    assert path.is_relative_to((tmp_path / "rooms").resolve())


def test_room_config_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(InvalidRoomIdError):
        room_config_path(tmp_path, "../outside")
