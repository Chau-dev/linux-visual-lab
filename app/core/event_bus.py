import threading
from collections.abc import Callable

from app.core.events import SystemEvent


class EventBus:
    """
    Thread-safe publish/subscribe event system.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers = {}

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[SystemEvent], None],
    ):
        with self._lock:
            self._subscribers.setdefault(
                event_type,
                []
            ).append(callback)

    def unsubscribe(
        self,
        event_type: str,
        callback: Callable[[SystemEvent], None],
    ):
        """
        Unsubscribe a callback from an event type in a thread-safe manner.
        """
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    cb for cb in self._subscribers[event_type]
                    if cb != callback
                ]

    def publish(
        self,
        event: SystemEvent
    ):
        with self._lock:
            callbacks = list(self._subscribers.get(
                event.event_type,
                []
            ))

        for callback in callbacks:
            try:
                callback(event)
            except Exception as error:
                import sys
                print(
                    f"[EventBus] Error in callback for '{event.event_type}': {error}",
                    file=sys.stderr
                )


