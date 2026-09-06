from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SystemEvent:
    """
    Represents an observed Linux fact or state transition.

    Every event contains:
      - event_type: structured domain identifier (e.g. process.created, file.modified)
      - data: factual payload dictionary
      - observed_at: timestamp when the observer sampled or received the event
      - source: observer component (e.g. 'Linux /proc snapshot', 'Filesystem observer')
      - mechanism: low-level OS mechanism (e.g. 'inotify', '/proc/<pid>/stat', 'stat()')
    """

    event_type: str
    data: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=datetime.now)
    source: str = "Linux Subsystem"
    mechanism: str | None = None

    def __init__(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        observed_at: datetime | None = None,
        source: str = "Linux Subsystem",
        mechanism: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.event_type = event_type
        self.data = data if data is not None else {}
        self.observed_at = observed_at or timestamp or datetime.now()
        self.source = source
        self.mechanism = mechanism

    @property
    def timestamp(self) -> datetime:
        """Backwards-compatible alias for observed_at."""
        return self.observed_at

    @timestamp.setter
    def timestamp(self, val: datetime):
        self.observed_at = val

    @property
    def formatted_time(self) -> str:
        """Return observed_at formatted with millisecond precision (HH:MM:SS.mmm)."""
        return self.observed_at.strftime("%H:%M:%S.%f")[:-3]

