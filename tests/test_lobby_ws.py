import json
from pathlib import Path

from lobby_helpers import app_with_room, recv_join_sequence, start_discussion


def test_websocket_join_and_turn_flow(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        recv_join_sequence(ws)

        start_discussion(client)

        assert json.loads(ws.receive_text())["type"] == "discussion_started"
        turn = json.loads(ws.receive_text())
        assert turn["type"] == "turn_granted"
        assert turn["agent_id"] == "m001"

        ws.send_text(json.dumps({"type": "say", "text": "hello"}))
        ws.send_text(json.dumps({"type": "turn_done"}))


def test_rejected_join_not_registered_in_hub(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)
    app = client.app

    with client.websocket_connect("/ws") as ws1:
        recv_join_sequence(ws1)

        with client.websocket_connect("/ws") as ws2:
            ws2.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Alice"}))
            reject = json.loads(ws2.receive_text())
            assert reject["type"] == "join_rejected"

            assert len(app.state.hub.connections.get("T", {})) == 1


def test_rejected_join_can_retry_with_new_display_name(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": ""}))
        assert json.loads(ws.receive_text())["type"] == "join_rejected"

        ok = recv_join_sequence(ws, display_name="Bob")
        assert ok["display_name"] == "Bob"


def test_join_rejects_invalid_room_id(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "../evil", "display_name": "Alice"}))
        reject = json.loads(ws.receive_text())
        assert reject["type"] == "join_rejected"
        assert reject["reason"] == "invalid_room_id"


def test_join_rejects_unknown_room(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "MISSING", "display_name": "Alice"}))
        reject = json.loads(ws.receive_text())
        assert reject["type"] == "join_rejected"
        assert reject["reason"] == "room_not_found"


def test_admin_create_rejects_invalid_room_id(tmp_path: Path) -> None:
    from starlette.testclient import TestClient

    from peas_agent.lobby.server.app import create_app

    client = TestClient(create_app(tmp_path))

    response = client.post("/admin/rooms/create", data={"room_id": "../evil"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert list((tmp_path / "rooms").glob("*.json")) == []


def test_invalid_rejoin_token(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)
    app = client.app

    with client.websocket_connect("/ws") as ws1:
        recv_join_sequence(ws1)

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


def test_join_replays_message_history(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "T.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        json.dumps(
            {
                "kind": "message",
                "from": "system",
                "display_name": "Host",
                "text": "welcome",
                "ts": "2026-01-01T00:00:00+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "join", "room_id": "T", "display_name": "Alice"}))
        assert json.loads(ws.receive_text())["type"] == "join_ok"
        assert json.loads(ws.receive_text())["type"] == "room_config"
        assert json.loads(ws.receive_text())["type"] == "members"
        history = json.loads(ws.receive_text())
        assert history["type"] == "message_history"
        assert len(history["messages"]) == 1
        assert history["messages"][0]["text"] == "welcome"
