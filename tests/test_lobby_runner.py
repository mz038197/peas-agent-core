import asyncio
import json

from peas_agent.lobby.runner.client import LobbyRunner


class _MockWs:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, data: str) -> None:
        self.sent.append(json.loads(data))


def test_turn_granted_chat_error_sends_pass_and_turn_done() -> None:
    runner = LobbyRunner(
        ws_url="ws://example/ws",
        room_id="T",
        display_name="Alice",
        chat_fn=lambda _host, _user: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    runner.agent_id = "m001"
    ws = _MockWs()

    asyncio.run(
        runner._handle_event(
            ws,
            {
                "type": "turn_granted",
                "agent_id": "m001",
                "turn_no": 1,
                "prompt_hint": "speak",
            },
        )
    )

    assert ws.sent == [{"type": "pass"}, {"type": "turn_done"}]


def test_turn_granted_success_sends_say_and_turn_done() -> None:
    runner = LobbyRunner(
        ws_url="ws://example/ws",
        room_id="T",
        display_name="Alice",
        chat_fn=lambda _host, _user: "hello room",
    )
    runner.agent_id = "m001"
    ws = _MockWs()

    asyncio.run(
        runner._handle_event(
            ws,
            {
                "type": "turn_granted",
                "agent_id": "m001",
                "turn_no": 1,
                "prompt_hint": "speak",
            },
        )
    )

    assert ws.sent == [{"type": "say", "text": "hello room"}, {"type": "turn_done"}]
