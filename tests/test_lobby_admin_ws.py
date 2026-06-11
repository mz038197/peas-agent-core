import asyncio
import json
from pathlib import Path

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.room import Room
from lobby_helpers import app_with_room, recv_join_sequence, start_discussion


def _app_with_room(tmp_path: Path, *, turn_timeout_sec: int = 600):
    return app_with_room(tmp_path, turn_timeout_sec=turn_timeout_sec)


def test_admin_ws_history_on_connect(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "T.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        json.dumps(
            {
                "kind": "message",
                "from": "m001",
                "display_name": "Alice",
                "text": "earlier hello",
                "ts": "2026-01-01T00:00:00+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    client = _app_with_room(tmp_path)

    with client.websocket_connect("/admin/ws/T") as admin_ws:
        history = json.loads(admin_ws.receive_text())
        assert history["type"] == "history"
        assert len(history["entries"]) == 1
        assert history["entries"][0]["text"] == "earlier hello"

        config = json.loads(admin_ws.receive_text())
        assert config["type"] == "room_config"

        members = json.loads(admin_ws.receive_text())
        assert members["type"] == "members"

        status = json.loads(admin_ws.receive_text())
        assert status["type"] == "admin_status"
        assert status["discussion_started"] is False


def test_admin_ws_receives_live_message(tmp_path: Path) -> None:
    admin_client = _app_with_room(tmp_path)
    student_client = admin_client

    with admin_client.websocket_connect("/admin/ws/T") as admin_ws:
        for _ in range(4):
            admin_ws.receive_text()

        with student_client.websocket_connect("/ws") as student_ws:
            recv_join_sequence(student_ws)
            start_discussion(admin_client)
            assert json.loads(student_ws.receive_text())["type"] == "discussion_started"
            assert json.loads(student_ws.receive_text())["type"] == "turn_granted"
            student_ws.send_text(json.dumps({"type": "say", "text": "hello admin"}))
            assert json.loads(student_ws.receive_text())["type"] == "message"

        events = [json.loads(admin_ws.receive_text()) for _ in range(4)]
        types = [event["type"] for event in events]
        assert "discussion_started" in types
        assert "members" in types
        assert "turn_granted" in types
        assert "message" in types
        message = next(event for event in events if event["type"] == "message")
        assert message["text"] == "hello admin"


def test_admin_ws_members_update(tmp_path: Path) -> None:
    admin_client = _app_with_room(tmp_path)
    student_client = admin_client

    with admin_client.websocket_connect("/admin/ws/T") as admin_ws:
        for _ in range(4):
            admin_ws.receive_text()

        with student_client.websocket_connect("/ws") as ws1:
            recv_join_sequence(ws1, display_name="Alice")
            assert json.loads(admin_ws.receive_text())["type"] == "members"

            with student_client.websocket_connect("/ws") as ws2:
                recv_join_sequence(ws2, display_name="Bob")

            members2 = json.loads(admin_ws.receive_text())
            assert members2["type"] == "members"
            assert len(members2["members"]) == 2


def test_broadcast_writes_log(tmp_path: Path) -> None:
    async def _run() -> None:
        room = Room(config=RoomConfig(room_id="T"), workspace=tmp_path)
        await room.broadcast_system("class begins")

    asyncio.run(_run())

    log_path = tmp_path / "logs" / "T.jsonl"
    assert log_path.is_file()
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["kind"] == "message"
    assert entry["from"] == "system"
    assert entry["text"] == "class begins"
