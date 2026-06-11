from __future__ import annotations

import json
from pathlib import Path

from peas_agent.lobby.paths import ensure_lobby_dirs, room_config_path
from peas_agent.lobby.protocol import RoomConfig


def load_room_config(workspace: Path, room_id: str) -> RoomConfig | None:
    path = room_config_path(workspace, room_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return RoomConfig.from_dict(data)


def save_room_config(workspace: Path, config: RoomConfig) -> Path:
    ensure_lobby_dirs(workspace)
    path = room_config_path(workspace, config.room_id)
    path.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def list_room_ids(workspace: Path) -> list[str]:
    rooms_dir = ensure_lobby_dirs(workspace) / "rooms"
    return sorted(p.stem for p in rooms_dir.glob("*.json"))


def default_room_config(room_id: str) -> RoomConfig:
    return RoomConfig(room_id=room_id)
