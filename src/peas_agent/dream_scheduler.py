"""Background Dream scheduler (cron) per workspace."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from peas_agent.chat_activity import is_chat_active
from peas_agent.dream import Dream

_schedulers: dict[str, DreamScheduler] = {}
_registry_lock = threading.Lock()


class DreamScheduler:
    def __init__(
        self,
        workspace: Path,
        config: dict[str, Any],
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.config = config
        from peas_agent.core import _build_dream_llm

        self.dream_llm = _build_dream_llm(config)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._dream_cfg = self._dream_config()

    def _dream_config(self) -> dict[str, Any]:
        raw = self.config.get("dream", {})
        return raw if isinstance(raw, dict) else {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"dream-scheduler-{self.workspace.name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def next_run_at(self) -> datetime | None:
        if not self._dream_cfg.get("enabled", True):
            return None
        try:
            from croniter import croniter

            cron_expr = str(self._dream_cfg.get("cron", "0 */2 * * *"))
            base = datetime.now()
            return croniter(cron_expr, base).get_next(datetime)
        except Exception:
            return None

    def _run_loop(self) -> None:
        try:
            from croniter import croniter
        except ImportError:
            return

        cron_expr = str(self._dream_cfg.get("cron", "0 */2 * * *"))
        while not self._stop.is_set():
            try:
                base = datetime.now()
                next_run = croniter(cron_expr, base).get_next(datetime)
                wait_seconds = max(0.0, (next_run - datetime.now()).total_seconds())
                if self._stop.wait(timeout=wait_seconds):
                    break
                self._tick()
            except Exception:
                if self._stop.wait(timeout=60):
                    break

    def _tick(self) -> None:
        if is_chat_active():
            print("（Dream 排程延後：chat 進行中。）", flush=True)
            return
        dream = Dream(self.workspace, self.config, self.dream_llm)
        dream.run(active_session_path=None)


def ensure_dream_scheduler(
    workspace: Path,
    config: dict[str, Any],
) -> DreamScheduler | None:
    dream_cfg = config.get("dream", {})
    if isinstance(dream_cfg, dict) and not dream_cfg.get("enabled", True):
        return None

    key = str(workspace.expanduser().resolve())
    with _registry_lock:
        existing = _schedulers.get(key)
        if existing is not None:
            return existing
        scheduler = DreamScheduler(workspace, config)
        scheduler.start()
        _schedulers[key] = scheduler
        return scheduler
