from __future__ import annotations

from pathlib import Path

DATA_DIR = Path.home() / ".peas-agent"
DEFAULT_LOBBY_WORKSPACE = DATA_DIR / "lobby"


def resolve_lobby_workspace(path: str | Path | None = None) -> Path:
    if path is None:
        return DEFAULT_LOBBY_WORKSPACE.expanduser().resolve()
    return Path(path).expanduser().resolve()


def ensure_lobby_dirs(workspace: Path) -> Path:
    root = workspace.expanduser().resolve()
    (root / "rooms").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "clients").mkdir(parents=True, exist_ok=True)
    return root


def room_config_path(workspace: Path, room_id: str) -> Path:
    return workspace / "rooms" / f"{room_id}.json"


def room_log_path(workspace: Path, room_id: str) -> Path:
    return workspace / "logs" / f"{room_id}.jsonl"
