from collections import deque
from datetime import datetime

from app.core.events import SystemEvent


class ActivityTimeline:
    """
    Stores recent Linux events.

    The timeline is intentionally independent
    of the GUI.
    """

    def __init__(self, max_events=100):

        self.events = deque(
            maxlen=max_events
        )

    def record(
        self,
        event: SystemEvent
    ):

        self.events.append(
            event
        )

    def get_events(self):

        return list(
            self.events
        )

    def clear(self):

        self.events.clear()
