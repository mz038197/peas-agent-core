"""MemoryStore thread safety."""

from __future__ import annotations

import threading
from pathlib import Path

from peas_agent.memory_store import configure_memory_store


def test_concurrent_append_history(tmp_path: Path) -> None:
    store = configure_memory_store(tmp_path)
    errors: list[str] = []

    def worker(prefix: str) -> None:
        try:
            for i in range(20):
                store.append_history(f"{prefix}-{i}")
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(f"t{n}",)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors
    entries = store.read_unprocessed_history(since_cursor=0)
    assert len(entries) == 80
    cursors = sorted(int(e["cursor"]) for e in entries)
    assert cursors == list(range(1, 81))
