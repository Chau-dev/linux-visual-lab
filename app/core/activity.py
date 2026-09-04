import threading
from collections import deque
from datetime import datetime

from app.core.events import SystemEvent


class ActivityTimeline:
    """
    Thread-safe storage for recent Linux events.

    The timeline is intentionally independent
    of the GUI.
    """

    def __init__(self, max_events=100):
        self._lock = threading.Lock()
        self.events = deque(
            maxlen=max_events
        )

    def record(
        self,
        event: SystemEvent
    ):
        with self._lock:
            self.events.append(
                event
            )

    def get_events(self):
        with self._lock:
            return list(
                self.events
            )

    def clear(self):
        with self._lock:
            self.events.clear()

