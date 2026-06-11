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
