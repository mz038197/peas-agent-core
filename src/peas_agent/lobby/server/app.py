from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from peas_agent.lobby.paths import InvalidRoomIdError, ensure_lobby_dirs, validate_room_id
from peas_agent.lobby.protocol import JoinMessage, PassMessage, RoomConfig, SayMessage, TurnDoneMessage, parse_client_message
from peas_agent.lobby.server.registry import RoomRegistry
from peas_agent.lobby.server.storage import (
    delete_room,
    list_room_ids,
    load_room_config,
    load_room_messages,
    load_room_timeline,
    save_room_config,
)


class ConnectionHub:
    def __init__(self) -> None:
        self.connections: dict[str, dict[str, WebSocket]] = {}
        self.admin_connections: dict[str, dict[str, WebSocket]] = {}

    def add(self, room_id: str, connection_id: str, ws: WebSocket) -> None:
        self.connections.setdefault(room_id, {})[connection_id] = ws

    def add_admin(self, room_id: str, connection_id: str, ws: WebSocket) -> None:
        self.admin_connections.setdefault(room_id, {})[connection_id] = ws

    def remove(self, room_id: str, connection_id: str) -> None:
        room = self.connections.get(room_id)
        if not room:
            return
        room.pop(connection_id, None)
        if not room:
            self.connections.pop(room_id, None)

    def remove_admin(self, room_id: str, connection_id: str) -> None:
        room = self.admin_connections.get(room_id)
        if not room:
            return
        room.pop(connection_id, None)
        if not room:
            self.admin_connections.pop(room_id, None)

    async def close_room(self, room_id: str) -> None:
        for pool in (self.connections, self.admin_connections):
            room = pool.pop(room_id, {})
            for ws in list(room.values()):
                try:
                    await ws.close()
                except Exception:
                    pass

    async def _send_to(self, room: dict[str, WebSocket], payload: str, *, target: str | None) -> None:
        if target:
            ws = room.get(target)
            if ws:
                await ws.send_text(payload)
            return
        for ws in list(room.values()):
            try:
                await ws.send_text(payload)
            except Exception:
                pass

    async def send(
        self,
        room_id: str,
        event: dict[str, Any],
        *,
        target_connection_id: str | None = None,
    ) -> None:
        room = self.connections.get(room_id, {})
        payload = json.dumps(event, ensure_ascii=False)
        await self._send_to(room, payload, target=target_connection_id)

    async def send_admin(self, room_id: str, event: dict[str, Any]) -> None:
        room = self.admin_connections.get(room_id, {})
        payload = json.dumps(event, ensure_ascii=False)
        await self._send_to(room, payload, target=None)


def create_app(workspace: Path) -> FastAPI:
    ensure_lobby_dirs(workspace)
    registry = RoomRegistry(workspace)
    registry.load_from_disk()
    hub = ConnectionHub()

    app = FastAPI(title="PEAS Agent Lobby")
    app.state.hub = hub
    templates_dir = Path(__file__).parent / "admin" / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    def wire_room(room: Any) -> None:
        room_id = room.config.room_id

        async def _broadcast(
            event: dict[str, Any],
            target_connection_id: str | None = None,
        ) -> None:
            if target_connection_id:
                await hub.send(room_id, event, target_connection_id=target_connection_id)
            else:
                await hub.send(room_id, event)
                await hub.send_admin(room_id, event)

        room.set_broadcast(_broadcast)

    for room in registry.rooms.values():
        wire_room(room)

    def _require_room_id(room_id: str) -> str:
        try:
            return validate_room_id(room_id)
        except InvalidRoomIdError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"room_ids": list_room_ids(workspace)},
        )

    @app.get("/admin/rooms/{room_id}", response_class=HTMLResponse)
    async def admin_room(request: Request, room_id: str) -> HTMLResponse:
        room_id = _require_room_id(room_id)
        room = registry.get(room_id)
        if room is None:
            raise HTTPException(status_code=404, detail="room not found")
        wire_room(room)
        return templates.TemplateResponse(
            request,
            "room.html",
            {
                "room": room,
                "config": room.config,
                "members": room.member_list(),
            },
        )

    @app.post("/admin/rooms/{room_id}/config")
    async def admin_save_config(
        room_id: str,
        topic: str = Form(""),
        rules: str = Form(""),
        turn_timeout_sec: int = Form(60),
        turn_gap_sec: int = Form(5),
        mention_enabled: str | None = Form(None),
        round_robin_enabled: str | None = Form(None),
        skip_gap_on_first_grant: str | None = Form(None),
        paused: str | None = Form(None),
    ) -> RedirectResponse:
        room_id = _require_room_id(room_id)
        existing = load_room_config(workspace, room_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="room not found")
        config = RoomConfig(
            room_id=room_id,
            topic=topic,
            rules=rules,
            turn_timeout_sec=turn_timeout_sec,
            turn_gap_sec=turn_gap_sec,
            mention_enabled=mention_enabled == "on",
            round_robin_enabled=round_robin_enabled == "on",
            discussion_started=existing.discussion_started,
            skip_gap_on_first_grant=skip_gap_on_first_grant == "on",
            paused=paused == "on",
        )
        save_room_config(workspace, config)
        room = registry.set_config(config)
        wire_room(room)
        await room.update_config(config)
        return RedirectResponse(url=f"/admin/rooms/{room_id}", status_code=303)

    @app.post("/admin/rooms/{room_id}/start")
    async def admin_start_discussion(room_id: str) -> RedirectResponse:
        room_id = _require_room_id(room_id)
        room = registry.get(room_id)
        if room is None:
            raise HTTPException(status_code=404, detail="room not found")
        wire_room(room)
        await room.start_discussion()
        return RedirectResponse(url=f"/admin/rooms/{room_id}", status_code=303)

    @app.post("/admin/rooms/{room_id}/delete")
    async def admin_delete_room(room_id: str) -> RedirectResponse:
        room_id = _require_room_id(room_id)
        room = registry.get(room_id)
        if room is not None:
            wire_room(room)
            await room.shutdown()
            await hub.close_room(room_id)
        delete_room(workspace, room_id)
        registry.remove(room_id)
        return RedirectResponse(url="/admin", status_code=303)

    @app.post("/admin/rooms/create")
    async def admin_create_room(room_id: str = Form(...)) -> RedirectResponse:
        try:
            room_id = validate_room_id(room_id)
        except InvalidRoomIdError:
            return RedirectResponse(url="/admin", status_code=303)
        config = RoomConfig(room_id=room_id)
        save_room_config(workspace, config)
        room = registry.set_config(config)
        wire_room(room)
        return RedirectResponse(url=f"/admin/rooms/{room_id}", status_code=303)

    @app.post("/admin/rooms/{room_id}/broadcast")
    async def admin_broadcast(room_id: str, text: str = Form(...)) -> RedirectResponse:
        room_id = _require_room_id(room_id)
        room = registry.get(room_id)
        if room is None:
            raise HTTPException(status_code=404, detail="room not found")
        wire_room(room)
        await room.broadcast_system(text.strip())
        return RedirectResponse(url=f"/admin/rooms/{room_id}", status_code=303)

    async def _send_admin_snapshot(ws: WebSocket, room: Any) -> None:
        await ws.send_text(
            json.dumps(
                {
                    "type": "history",
                    "entries": load_room_timeline(workspace, room.config.room_id),
                },
                ensure_ascii=False,
            )
        )
        await ws.send_text(
            json.dumps({"type": "room_config", **room.config.to_dict()}, ensure_ascii=False)
        )
        await ws.send_text(
            json.dumps(
                {
                    "type": "members",
                    "room_id": room.config.room_id,
                    "members": [m.to_dict() for m in room.member_list()],
                },
                ensure_ascii=False,
            )
        )
        await ws.send_text(
            json.dumps(
                {
                    "type": "admin_status",
                    "current_speaker": room.current_speaker,
                    "turn_no": room.turn_no,
                    "discussion_started": room.config.discussion_started,
                    "paused": room.config.paused,
                },
                ensure_ascii=False,
            )
        )

    @app.websocket("/admin/ws/{room_id}")
    async def admin_websocket(ws: WebSocket, room_id: str) -> None:
        try:
            room_id = validate_room_id(room_id)
        except InvalidRoomIdError:
            await ws.close(code=1008)
            return

        room = registry.get(room_id)
        if room is None:
            await ws.close(code=1008)
            return
        wire_room(room)
        await ws.accept()
        connection_id = uuid.uuid4().hex
        hub.add_admin(room_id, connection_id, ws)
        try:
            await _send_admin_snapshot(ws, room)
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            hub.remove_admin(room_id, connection_id)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        connection_id = uuid.uuid4().hex
        joined_room_id: str | None = None
        agent_id: str | None = None

        try:
            while True:
                raw = await ws.receive_text()
                msg = parse_client_message(json.loads(raw))

                if isinstance(msg, JoinMessage):
                    try:
                        validate_room_id(msg.room_id)
                    except InvalidRoomIdError as exc:
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "join_rejected",
                                    "reason": "invalid_room_id",
                                    "message": str(exc),
                                },
                                ensure_ascii=False,
                            )
                        )
                        continue

                    room = registry.get(msg.room_id)
                    if room is None:
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "join_rejected",
                                    "reason": "room_not_found",
                                    "message": f"Room {msg.room_id} does not exist",
                                },
                                ensure_ascii=False,
                            )
                        )
                        continue
                    wire_room(room)
                    result = await room.handle_join(
                        connection_id,
                        display_name=msg.display_name,
                        rejoin_token=msg.rejoin_token,
                    )
                    await ws.send_text(json.dumps(result, ensure_ascii=False))
                    if result.get("type") == "join_ok":
                        joined_room_id = msg.room_id
                        hub.add(joined_room_id, connection_id, ws)
                        agent_id = result["agent_id"]
                        await room.send_room_config(connection_id)
                        await room.publish_members()
                        messages = load_room_messages(workspace, msg.room_id)
                        await hub.send(
                            joined_room_id,
                            {"type": "message_history", "messages": messages},
                            target_connection_id=connection_id,
                        )
                    continue

                if not joined_room_id or not agent_id:
                    continue

                room = registry.get(joined_room_id)
                if room is None:
                    continue
                wire_room(room)

                if isinstance(msg, SayMessage):
                    await room.handle_say(agent_id, msg.text)
                elif isinstance(msg, TurnDoneMessage):
                    await room.handle_turn_done(agent_id)
                elif isinstance(msg, PassMessage):
                    await room.handle_pass(agent_id)
        except WebSocketDisconnect:
            pass
        finally:
            if joined_room_id:
                room = registry.get(joined_room_id)
                if room is not None:
                    wire_room(room)
                    await room.disconnect(connection_id)
                hub.remove(joined_room_id, connection_id)

    return app
