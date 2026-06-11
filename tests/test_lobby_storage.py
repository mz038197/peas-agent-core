from pathlib import Path

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.storage import delete_room, load_room_config, load_room_messages, save_room_config


def test_room_config_roundtrip(tmp_path: Path) -> None:
    config = RoomConfig(room_id="TEST", topic="hello", turn_gap_sec=3, discussion_started=True)
    save_room_config(tmp_path, config)
    loaded = load_room_config(tmp_path, "TEST")
    assert loaded is not None
    assert loaded.topic == "hello"
    assert loaded.turn_gap_sec == 3
    assert loaded.discussion_started is True


def test_delete_room_and_load_messages(tmp_path: Path) -> None:
    config = RoomConfig(room_id="TEST")
    save_room_config(tmp_path, config)
    log_path = tmp_path / "logs" / "TEST.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        '{"kind":"message","from":"system","display_name":"Host","text":"hi"}\n',
        encoding="utf-8",
    )

    messages = load_room_messages(tmp_path, "TEST")
    assert len(messages) == 1
    assert messages[0]["text"] == "hi"

    assert delete_room(tmp_path, "TEST") is True
    assert load_room_config(tmp_path, "TEST") is None
    assert not log_path.is_file()
