"""Track in-flight Agent.chat() calls so background Dream can defer."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

_active_count = 0
_lock = threading.Lock()


def is_chat_active() -> bool:
    with _lock:
        return _active_count > 0


@contextmanager
def chat_activity() -> Iterator[None]:
    global _active_count
    with _lock:
        _active_count += 1
    try:
        yield
    finally:
        with _lock:
            _active_count -= 1
