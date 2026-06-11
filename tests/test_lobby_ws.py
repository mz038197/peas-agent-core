import json
from pathlib import Path

from starlette.testclient import TestClient

from peas_agent.lobby.server.app import create_app


def test_websocket_join_and_turn_flow(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Alice"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "join_ok"
        assert msg["agent_id"] == "m001"

        config = json.loads(ws.receive_text())
        assert config["type"] == "room_config"

        members = json.loads(ws.receive_text())
        assert members["type"] == "members"

        turn = json.loads(ws.receive_text())
        assert turn["type"] == "turn_granted"
        assert turn["agent_id"] == "m001"

        ws.send_text(json.dumps({"type": "say", "text": "hello"}))
        ws.send_text(json.dumps({"type": "turn_done"}))


def test_rejected_join_not_registered_in_hub(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws1:
        ws1.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Alice"}))
        assert json.loads(ws1.receive_text())["type"] == "join_ok"

        with client.websocket_connect("/ws") as ws2:
            ws2.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Alice"}))
            reject = json.loads(ws2.receive_text())
            assert reject["type"] == "join_rejected"

            assert len(app.state.hub.connections.get("T", {})) == 1


def test_rejected_join_can_retry_with_new_display_name(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": ""}))
        assert json.loads(ws.receive_text())["type"] == "join_rejected"

        ws.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Bob"}))
        ok = json.loads(ws.receive_text())
        assert ok["type"] == "join_ok"
        assert ok["display_name"] == "Bob"


def test_join_rejects_invalid_room_id(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "../evil", "display_name": "Alice"}))
        reject = json.loads(ws.receive_text())
        assert reject["type"] == "join_rejected"
        assert reject["reason"] == "invalid_room_id"


def test_admin_create_rejects_invalid_room_id(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    response = client.post("/admin/rooms/create", data={"room_id": "../evil"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert list((tmp_path / "rooms").glob("*.json")) == []


def test_join_rejects_invalid_rejoin_token(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws1:
        ws1.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Alice"}))
        assert json.loads(ws1.receive_text())["type"] == "join_ok"

        with client.websocket_connect("/ws") as ws2:
            ws2.send_text(
                json.dumps(
                    {
                        "type": "join",
                        "room_id": "T",
                        "display_name": "Bob",
                        "rejoin_token": "invalid-token",
                    }
                )
            )
            reject = json.loads(ws2.receive_text())
            assert reject["type"] == "join_rejected"
            assert reject["reason"] == "invalid_rejoin_token"
            assert len(app.state.hub.connections.get("T", {})) == 1
