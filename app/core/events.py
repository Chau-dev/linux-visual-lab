from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SystemEvent:
    """
    Represents one thing that happened in Linux.
    """

    event_type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=datetime.now
    )
