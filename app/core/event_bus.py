from collections.abc import Callable

from app.core.events import SystemEvent


class EventBus:
    """
    Simple publish/subscribe event system.
    """

    def __init__(self):
        self._subscribers = {}

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[SystemEvent], None],
    ):
        self._subscribers.setdefault(
            event_type,
            []
        ).append(callback)

    def publish(
        self,
        event: SystemEvent
    ):
        callbacks = self._subscribers.get(
            event.event_type,
            []
        )

        for callback in callbacks:
            callback(event)
