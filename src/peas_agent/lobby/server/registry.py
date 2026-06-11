from __future__ import annotations

from pathlib import Path

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.room import Room
from peas_agent.lobby.server.storage import list_room_ids, load_room_config, room_exists


class RoomRegistry:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.rooms: dict[str, Room] = {}

    def load_from_disk(self) -> None:
        for room_id in list_room_ids(self.workspace):
            config = load_room_config(self.workspace, room_id)
            if config is not None:
                self.rooms[room_id] = Room(config=config, workspace=self.workspace)

    def get(self, room_id: str) -> Room | None:
        if room_id in self.rooms:
            return self.rooms[room_id]
        if not room_exists(self.workspace, room_id):
            return None
        config = load_room_config(self.workspace, room_id)
        if config is None:
            return None
        room = Room(config=config, workspace=self.workspace)
        self.rooms[room_id] = room
        return room

    def set_config(self, config: RoomConfig) -> Room:
        room = self.get(config.room_id)
        if room is None:
            room = Room(config=config, workspace=self.workspace)
            self.rooms[config.room_id] = room
        else:
            room.config = config
        return room

    def remove(self, room_id: str) -> None:
        self.rooms.pop(room_id, None)
