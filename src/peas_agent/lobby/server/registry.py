from __future__ import annotations

from pathlib import Path

from peas_agent.lobby.protocol import RoomConfig
from peas_agent.lobby.server.room import Room
from peas_agent.lobby.server.storage import default_room_config, list_room_ids, load_room_config


class RoomRegistry:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.rooms: dict[str, Room] = {}

    def load_from_disk(self) -> None:
        for room_id in list_room_ids(self.workspace):
            config = load_room_config(self.workspace, room_id)
            if config is None:
                config = default_room_config(room_id)
            self.rooms[room_id] = Room(config=config, workspace=self.workspace)

    def get_or_create(self, room_id: str) -> Room:
        if room_id not in self.rooms:
            config = load_room_config(self.workspace, room_id)
            if config is None:
                config = default_room_config(room_id)
            self.rooms[room_id] = Room(config=config, workspace=self.workspace)
        return self.rooms[room_id]

    def set_config(self, config: RoomConfig) -> Room:
        room = self.get_or_create(config.room_id)
        room.config = config
        return room
