from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.app import create_app
from peas_agent.lobby.server.storage import save_room_config


def app_with_room(tmp_path: Path, room_id: str = "T", **config_kwargs: Any) -> TestClient:
    kwargs = {"turn_timeout_sec": 600}
    kwargs.update(config_kwargs)
    save_room_config(tmp_path, RoomConfig(room_id=room_id, **kwargs))
    return TestClient(create_app(tmp_path))


def recv_join_sequence(ws: Any, *, room_id: str = "T", display_name: str = "Alice") -> dict:
    ws.send_text(json.dumps({"type": "join", "room_id": room_id, "display_name": display_name}))
    ok = json.loads(ws.receive_text())
    assert ok["type"] == "join_ok"
    assert json.loads(ws.receive_text())["type"] == "room_config"
    assert json.loads(ws.receive_text())["type"] == "members"
    history = json.loads(ws.receive_text())
    assert history["type"] == "message_history"
    return ok


def start_discussion(client: TestClient, room_id: str = "T") -> None:
    response = client.post(f"/admin/rooms/{room_id}/start", follow_redirects=False)
    assert response.status_code == 303
