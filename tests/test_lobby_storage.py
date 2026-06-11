from pathlib import Path

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.storage import load_room_config, save_room_config


def test_room_config_roundtrip(tmp_path: Path) -> None:
    config = RoomConfig(room_id="TEST", topic="hello", turn_gap_sec=3)
    save_room_config(tmp_path, config)
    loaded = load_room_config(tmp_path, "TEST")
    assert loaded is not None
    assert loaded.topic == "hello"
    assert loaded.turn_gap_sec == 3
