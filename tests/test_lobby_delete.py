import json
from pathlib import Path

from lobby_helpers import app_with_room, recv_join_sequence


def test_delete_room_removes_config_and_rejects_join(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        recv_join_sequence(ws)

    response = client.post("/admin/rooms/T/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert not (tmp_path / "rooms" / "T.json").is_file()
    assert client.app.state.hub.connections.get("T") is None

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Alice"}))
        reject = json.loads(ws.receive_text())
        assert reject["type"] == "join_rejected"
        assert reject["reason"] == "room_not_found"
