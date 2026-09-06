from __future__ import annotations

import threading
from datetime import datetime

from app.core.events import SystemEvent
from app.memory.model import MemorySnapshot, SystemLoadSnapshot


class MemoryRegistry:
    """
    Thread-safe registry maintaining the current snapshot of Linux memory and system load.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._current_memory: MemorySnapshot | None = None
        self._current_load: SystemLoadSnapshot | None = None

    def get_memory(self) -> MemorySnapshot | None:
        with self._lock:
            return self._current_memory

    def set_memory(self, snapshot: MemorySnapshot | None):
        with self._lock:
            self._current_memory = snapshot

    def get_load(self) -> SystemLoadSnapshot | None:
        with self._lock:
            return self._current_load

    def set_load(self, snapshot: SystemLoadSnapshot | None):
        with self._lock:
            self._current_load = snapshot

    def get_latest_memory(self) -> MemorySnapshot | None:
        return self.get_memory()

    def get_latest_load(self) -> SystemLoadSnapshot | None:
        return self.get_load()

    def update(
        self,
        memory: MemorySnapshot | None,
        load: SystemLoadSnapshot | None,
        observed_at: datetime | None = None,
    ) -> list[SystemEvent]:
        with self._lock:
            events: list[SystemEvent] = []
            if memory is not None:
                if self._current_memory is not None:
                    events = diff_memory_snapshots(
                        self._current_memory,
                        memory,
                        observed_at=observed_at,
                    )
                self._current_memory = memory

            if load is not None:
                self._current_load = load

            return events

    def clear(self):
        with self._lock:
            self._current_memory = None
            self._current_load = None


def diff_memory_snapshots(
    previous: MemorySnapshot | None,
    current: MemorySnapshot,
    observed_at: datetime | None = None,
) -> list[SystemEvent]:
    """
    Compare previous memory snapshot with current memory snapshot to detect verifiable state changes.

    Strict Truth Rules:
      - Emits events ONLY upon verifiable state transitions.
      - Steady-state polling produces 0 events to prevent timeline spam.
      - Does not guess underlying kernel causes (e.g. asserts swap reported usage changed, not why).
    """
    if previous is None:
        return []

    if observed_at is None:
        observed_at = datetime.now()

    events: list[SystemEvent] = []

    # 1. Swap Usage Transition
    if previous.derived_swap_used_kb != current.derived_swap_used_kb:
        delta = current.derived_swap_used_kb - previous.derived_swap_used_kb
        events.append(
            SystemEvent(
                event_type="memory.swap_usage_changed",
                data={
                    "old_swap_used_kb": previous.derived_swap_used_kb,
                    "new_swap_used_kb": current.derived_swap_used_kb,
                    "delta_swap_used_kb": delta,
                    "swap_total_kb": current.swap_total_kb,
                    "mechanism": "/proc/meminfo",
                },
                observed_at=observed_at,
                source="Linux /proc/meminfo snapshot",
                mechanism="/proc/meminfo",
            )
        )

    return events
