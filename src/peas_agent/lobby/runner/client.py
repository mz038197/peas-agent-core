from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from peas_agent.core import Agent, set_host_context
from peas_agent.lobby.protocol import MemberInfo, RoomConfig
from peas_agent.lobby.runner.format import build_host_context, build_user_text


class LobbyRunner:
    def __init__(
        self,
        *,
        ws_url: str,
        room_id: str,
        display_name: str,
        workspace: str | None = None,
        chat_fn: Callable[[str, str], str] | None = None,
    ) -> None:
        self.ws_url = ws_url
        self.room_id = room_id
        self.display_name = display_name
        self.workspace = workspace
        self.chat_fn = chat_fn
        self.agent_id: str | None = None
        self.rejoin_token: str | None = None
        self.room_config = RoomConfig(room_id=room_id)
        self.members: list[MemberInfo] = []
        self.inbox: list[dict[str, str]] = []
        self._agent: Agent | None = None

    def _get_agent(self) -> Agent:
        if self._agent is None:
            self._agent = Agent.create(
                workspace=self.workspace,
                session_name=f"lobby-{self.room_id}",
            )
        return self._agent

    async def run(self) -> int:
        try:
            import websockets
        except ImportError as e:
            raise RuntimeError("請安裝 lobby extra：uv sync --extra lobby") from e

        async with websockets.connect(self.ws_url) as ws:
            join_payload: dict[str, Any] = {
                "type": "join",
                "room_id": self.room_id,
                "display_name": self.display_name,
            }
            if self.rejoin_token:
                join_payload = {
                    "type": "join",
                    "room_id": self.room_id,
                    "rejoin_token": self.rejoin_token,
                }
            await ws.send(json.dumps(join_payload, ensure_ascii=False))
            raw = await ws.recv()
            result = json.loads(raw)
            if result.get("type") == "join_rejected":
                print(result.get("message", "join 失敗"))
                return 1
            self.agent_id = result["agent_id"]
            self.rejoin_token = result.get("rejoin_token")
            self.members = [MemberInfo.from_dict(m) for m in result.get("members", [])]
            print(
                f"[join_ok] agent_id={self.agent_id} display_name={result.get('display_name')}"
            )

            while True:
                raw = await ws.recv()
                await self._handle_event(ws, json.loads(raw))
        return 0

    async def _handle_event(self, ws: Any, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "message":
            entry = {
                "from": event.get("from", ""),
                "display_name": event.get("display_name", ""),
                "text": event.get("text", ""),
            }
            self.inbox.append(entry)
            print(f"[inbox] {entry['display_name']}: {entry['text']}")
            return

        if kind in ("room_config", "room_config_updated"):
            payload = {k: v for k, v in event.items() if k != "type"}
            self.room_config = RoomConfig.from_dict(payload)
            return

        if kind == "members":
            self.members = [MemberInfo.from_dict(m) for m in event.get("members", [])]
            return

        if kind == "turn_pending":
            print(
                f"[turn_pending] 下一位 {event.get('next_display_name')} "
                f"({event.get('next_agent_id')}) in {event.get('gap_sec')}s"
            )
            return

        if kind == "turn_granted":
            if event.get("agent_id") != self.agent_id:
                return
            hint = event.get("prompt_hint")
            print(f"[turn_granted] turn_no={event.get('turn_no')} hint={hint}")
            reply = await asyncio.to_thread(self._chat_turn, hint)
            text = (reply or "").strip()
            if not text or text == "[pass]":
                await ws.send(json.dumps({"type": "pass"}, ensure_ascii=False))
                print("[pass]")
            else:
                await ws.send(json.dumps({"type": "say", "text": text}, ensure_ascii=False))
                print(f"[say] {text[:120]}{'…' if len(text) > 120 else ''}")
            await ws.send(json.dumps({"type": "turn_done"}, ensure_ascii=False))
            print("[turn_done]")
            return

        if kind == "turn_revoked":
            if event.get("agent_id") == self.agent_id:
                print("[turn_revoked] 逾時")
            return

    def _chat_turn(self, prompt_hint: str | None) -> str:
        host = build_host_context(
            room_config=self.room_config,
            members=self.members,
            my_agent_id=self.agent_id or "",
            my_display_name=self.display_name,
        )
        user_text = build_user_text(inbox=self.inbox, prompt_hint=prompt_hint)
        if self.chat_fn is not None:
            return self.chat_fn(host, user_text)
        set_host_context(host)
        agent = self._get_agent()
        return agent.chat(user_text)
