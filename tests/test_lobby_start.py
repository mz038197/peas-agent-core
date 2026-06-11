import json
from pathlib import Path

from lobby_helpers import app_with_room, recv_join_sequence, start_discussion


def test_start_discussion_grants_first_speaker(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        recv_join_sequence(ws)

        start_discussion(client)

        started = json.loads(ws.receive_text())
        assert started["type"] == "discussion_started"

        turn = json.loads(ws.receive_text())
        assert turn["type"] == "turn_granted"
        assert turn["agent_id"] == "m001"


def test_start_discussion_round_robin_with_two_members(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws1:
        recv_join_sequence(ws1, display_name="Alice")
        with client.websocket_connect("/ws") as ws2:
            recv_join_sequence(ws2, display_name="Bob")
            assert json.loads(ws1.receive_text())["type"] == "members"

            start_discussion(client)

            for ws in (ws1, ws2):
                assert json.loads(ws.receive_text())["type"] == "discussion_started"

            turn1 = json.loads(ws1.receive_text())
            assert turn1["type"] == "turn_granted"
            assert turn1["agent_id"] == "m001"


def test_join_before_start_has_no_turn(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)

    with client.websocket_connect("/ws") as ws:
        recv_join_sequence(ws)
        # No further events until teacher starts discussion.


def test_start_requires_members(tmp_path: Path) -> None:
    client = app_with_room(tmp_path)
    response = client.post("/admin/rooms/T/start", follow_redirects=False)
    assert response.status_code == 303
