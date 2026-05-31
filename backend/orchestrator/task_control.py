"""Cooperative task cancellation for batch execution."""

from __future__ import annotations

import threading
from typing import Optional


class StopRequested(Exception):
    """Raised when a batch run has been stopped by the user."""


class TaskControlRegistry:
    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self, batch_id: str) -> threading.Event:
        with self._lock:
            existing = self._events.get(batch_id)
            if existing and not existing.is_set():
                raise RuntimeError("Batch is already running")
            event = threading.Event()
            self._events[batch_id] = event
            return event

    def finish(self, batch_id: str, event: Optional[threading.Event] = None) -> None:
        with self._lock:
            current = self._events.get(batch_id)
            if current is not None and (event is None or current is event):
                self._events.pop(batch_id, None)

    def stop(self, batch_id: str) -> bool:
        with self._lock:
            event = self._events.get(batch_id)
            if not event:
                return False
            event.set()
            return True

    def is_active(self, batch_id: str) -> bool:
        with self._lock:
            event = self._events.get(batch_id)
            return bool(event and not event.is_set())

    def is_stop_requested(self, batch_id: str) -> bool:
        with self._lock:
            event = self._events.get(batch_id)
            return bool(event and event.is_set())

    def ensure_running(self, batch_id: str) -> None:
        if self.is_stop_requested(batch_id):
            raise StopRequested("Batch generation was stopped by the user")


task_control = TaskControlRegistry()
