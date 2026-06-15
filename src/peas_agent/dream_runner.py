"""Background Dream execution with completion notifications."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from peas_agent.dream import Dream, get_workspace_lock
from peas_agent.memory_store import MemoryStore

_runners: dict[str, DreamRunner] = {}
_registry_lock = threading.Lock()


class DreamRunner:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.expanduser().resolve()
        self._pending_message: str | None = None
        self._message_lock = threading.Lock()
        self._manual_running = False

    def submit(
        self,
        config: dict[str, Any],
        store: MemoryStore,
        dream_llm: Any,
        *,
        session_path: str | None,
    ) -> bool:
        lock = get_workspace_lock(self.workspace)
        if not lock.acquire(blocking=False):
            return False
        lock.release()

        with self._message_lock:
            if self._manual_running:
                return False

        thread = threading.Thread(
            target=self._run,
            args=(config, store, dream_llm, session_path),
            name=f"dream-manual-{self.workspace.name}",
            daemon=True,
        )
        with self._message_lock:
            self._manual_running = True
        thread.start()
        return True

    def poll_message(self) -> str | None:
        with self._message_lock:
            message = self._pending_message
            self._pending_message = None
            return message

    def _run(
        self,
        config: dict[str, Any],
        store: MemoryStore,
        dream_llm: Any,
        session_path: str | None,
    ) -> None:
        try:
            print("（Dream 背景：開始執行…）", flush=True)
            dream = Dream(self.workspace, config, dream_llm, store=store)
            ok = dream.run(active_session_path=session_path)
            message = (
                "（Dream 背景完成。）"
                if ok
                else "（Dream 背景：無待處理 history 或未能取得 lock。）"
            )
        except Exception as exc:
            message = f"（Dream 背景失敗：{exc}）"
        finally:
            with self._message_lock:
                self._pending_message = message
                self._manual_running = False


def get_dream_runner(workspace: Path) -> DreamRunner:
    key = str(workspace.expanduser().resolve())
    with _registry_lock:
        runner = _runners.get(key)
        if runner is None:
            runner = DreamRunner(workspace)
            _runners[key] = runner
        return runner


def submit_background_dream(
    workspace: Path,
    config: dict[str, Any],
    store: MemoryStore,
    dream_llm: Any,
    *,
    session_path: str | None,
) -> bool:
    return get_dream_runner(workspace).submit(
        config,
        store,
        dream_llm,
        session_path=session_path,
    )


def poll_dream_message(workspace: Path) -> str | None:
    return get_dream_runner(workspace).poll_message()
