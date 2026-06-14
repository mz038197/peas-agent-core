"""Memory file I/O: history.jsonl, dream cursor, MEMORY/SOUL/USER, pinned items."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from peas_agent.git_store import GitStore

_DEFAULT_MAX_HISTORY = 1000
_LEGACY_ENTRY_START_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}[^\]]*)\]\s*")
_LEGACY_TIMESTAMP_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*")
_LEGACY_RAW_MESSAGE_RE = re.compile(
    r"^\[\d{4}-\d{2}-\d{2}[^\]]*\]\s+[A-Z][A-Z0-9_]*(?:\s+\[tools:\s*[^\]]+\])?:"
)

_MEMORY_STORES: dict[str, MemoryStore] = {}
_ACTIVE_STORE_KEY: str | None = None


def _workspace_key(workspace: Path | str) -> str:
    return str(Path(workspace).expanduser().resolve())


def get_memory_store(workspace: Path | str | None = None) -> MemoryStore:
    if workspace is not None:
        key = _workspace_key(workspace)
        store = _MEMORY_STORES.get(key)
        if store is None:
            raise RuntimeError(
                f"MemoryStore not configured for workspace {key!r}; "
                "call configure_memory_store() first."
            )
        return store
    if _ACTIVE_STORE_KEY is None:
        raise RuntimeError("MemoryStore not configured; call configure_memory_store() first.")
    return _MEMORY_STORES[_ACTIVE_STORE_KEY]


def configure_memory_store(workspace: Path) -> MemoryStore:
    global _ACTIVE_STORE_KEY
    key = _workspace_key(workspace)
    store = _MEMORY_STORES.get(key)
    if store is None:
        store = MemoryStore(workspace)
        store.git.init()
        _MEMORY_STORES[key] = store
    _ACTIVE_STORE_KEY = key
    return store


class MemoryStore:
    """Pure file I/O for memory files under a workspace."""

    def __init__(self, workspace: Path, max_history_entries: int = _DEFAULT_MAX_HISTORY):
        self.workspace = workspace.expanduser().resolve()
        self.max_history_entries = max_history_entries
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "history.jsonl"
        self.legacy_history_file = self.memory_dir / "HISTORY.md"
        self.pinned_file = self.memory_dir / "pinned.json"
        self.summary_file = self.memory_dir / "SUMMARY.md"
        self.soul_file = self.workspace / "SOUL.md"
        self.user_file = self.workspace / "USER.md"
        self._cursor_file = self.memory_dir / ".cursor"
        self._dream_cursor_file = self.memory_dir / ".dream_cursor"
        self.git = GitStore(
            self.workspace,
            tracked_files=[
                "SOUL.md",
                "USER.md",
                "memory/MEMORY.md",
                "memory/.dream_cursor",
            ],
        )
        self._maybe_migrate_legacy_history()

    @staticmethod
    def read_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def read_memory(self) -> str:
        return self.read_file(self.memory_file)

    def write_memory(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def read_soul(self) -> str:
        return self.read_file(self.soul_file)

    def write_soul(self, content: str) -> None:
        self.soul_file.write_text(content, encoding="utf-8")

    def read_user(self) -> str:
        return self.read_file(self.user_file)

    def write_user(self, content: str) -> None:
        self.user_file.write_text(content, encoding="utf-8")

    def read_pinned(self) -> list[str]:
        if not self.pinned_file.is_file():
            return []
        try:
            data = json.loads(self.pinned_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()]
        return []

    def add_pin(self, keyword: str) -> None:
        keyword = keyword.strip()
        if not keyword:
            return
        pins = self.read_pinned()
        if keyword not in pins:
            pins.append(keyword)
            self.pinned_file.write_text(
                json.dumps(pins, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def append_history(self, entry: str, *, session_key: str | None = None) -> int:
        cursor = self._next_cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        record: dict[str, Any] = {
            "cursor": cursor,
            "timestamp": ts,
            "content": entry.rstrip(),
        }
        if session_key:
            record["session_key"] = session_key
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._cursor_file.write_text(str(cursor), encoding="utf-8")
        return cursor

    def raw_archive(self, text: str, *, session_key: str | None = None) -> int:
        return self.append_history(f"[RAW] {text}", session_key=session_key)

    def _next_cursor(self) -> int:
        if self._cursor_file.exists():
            try:
                return int(self._cursor_file.read_text(encoding="utf-8").strip()) + 1
            except (ValueError, OSError):
                pass
        last = self._read_last_entry()
        if last:
            return int(last["cursor"]) + 1
        return 1

    def read_unprocessed_history(self, since_cursor: int) -> list[dict[str, Any]]:
        return [e for e in self._read_entries() if int(e.get("cursor", 0)) > since_cursor]

    def compact_history(self) -> None:
        if self.max_history_entries <= 0:
            return
        entries = self._read_entries()
        if len(entries) <= self.max_history_entries:
            return
        self._write_entries(entries[-self.max_history_entries :])

    def get_last_dream_cursor(self) -> int:
        if self._dream_cursor_file.exists():
            try:
                return int(self._dream_cursor_file.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                pass
        return 0

    def set_last_dream_cursor(self, cursor: int) -> None:
        self._dream_cursor_file.write_text(str(cursor), encoding="utf-8")

    def _read_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        try:
            with open(self.history_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return entries

    def _read_last_entry(self) -> dict[str, Any] | None:
        try:
            with open(self.history_file, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return None
                read_size = min(size, 4096)
                f.seek(size - read_size)
                data = f.read().decode("utf-8")
                lines = [line for line in data.split("\n") if line.strip()]
                if not lines:
                    return None
                return json.loads(lines[-1])
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        with open(self.history_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _maybe_migrate_legacy_history(self) -> None:
        if not self.legacy_history_file.exists():
            return
        if self.history_file.exists() and self.history_file.stat().st_size > 0:
            return

        try:
            legacy_text = self.legacy_history_file.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return

        entries = self._parse_legacy_history(legacy_text)
        if entries:
            self._write_entries(entries)
            last_cursor = entries[-1]["cursor"]
            self._cursor_file.write_text(str(last_cursor), encoding="utf-8")
            self._dream_cursor_file.write_text(str(last_cursor), encoding="utf-8")

        backup_path = self._next_legacy_backup_path()
        self.legacy_history_file.replace(backup_path)

    def _parse_legacy_history(self, text: str) -> list[dict[str, Any]]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        fallback_timestamp = self._legacy_fallback_timestamp()
        entries: list[dict[str, Any]] = []
        for cursor, chunk in enumerate(self._split_legacy_history_chunks(normalized), start=1):
            timestamp = fallback_timestamp
            content = chunk
            match = _LEGACY_TIMESTAMP_RE.match(chunk)
            if match:
                timestamp = match.group(1)
                remainder = chunk[match.end() :].lstrip()
                if remainder:
                    content = remainder
            entries.append({"cursor": cursor, "timestamp": timestamp, "content": content})
        return entries

    def _split_legacy_history_chunks(self, text: str) -> list[str]:
        lines = text.split("\n")
        chunks: list[str] = []
        current: list[str] = []
        saw_blank_separator = False

        for line in lines:
            if saw_blank_separator and line.strip() and current:
                chunks.append("\n".join(current).strip())
                current = [line]
                saw_blank_separator = False
                continue
            if self._should_start_new_legacy_chunk(line, current):
                chunks.append("\n".join(current).strip())
                current = [line]
                saw_blank_separator = False
                continue
            current.append(line)
            saw_blank_separator = not line.strip()

        if current:
            chunks.append("\n".join(current).strip())
        return [chunk for chunk in chunks if chunk]

    def _should_start_new_legacy_chunk(self, line: str, current: list[str]) -> bool:
        if not current:
            return False
        if not _LEGACY_ENTRY_START_RE.match(line):
            return False
        if self._is_raw_legacy_chunk(current) and _LEGACY_RAW_MESSAGE_RE.match(line):
            return False
        return True

    def _is_raw_legacy_chunk(self, lines: list[str]) -> bool:
        first_nonempty = next((line for line in lines if line.strip()), "")
        match = _LEGACY_TIMESTAMP_RE.match(first_nonempty)
        if not match:
            return False
        return first_nonempty[match.end() :].lstrip().startswith("[RAW]")

    def _legacy_fallback_timestamp(self) -> str:
        try:
            return datetime.fromtimestamp(
                self.legacy_history_file.stat().st_mtime,
            ).strftime("%Y-%m-%d %H:%M")
        except OSError:
            return datetime.now().strftime("%Y-%m-%d %H:%M")

    def _next_legacy_backup_path(self) -> Path:
        candidate = self.memory_dir / "HISTORY.md.bak"
        suffix = 2
        while candidate.exists():
            candidate = self.memory_dir / f"HISTORY.md.bak.{suffix}"
            suffix += 1
        return candidate
