from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from app.core.events import SystemEvent
from app.process.session import TerminalSession
from app.process.model import Process


class ProcessRegistry:
    """
    Thread-safe registry maintaining the current snapshot of Linux processes.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._processes: dict[int, Process] = {}

    def get_snapshot(self) -> dict[int, Process]:
        """Return a copy of the current process snapshot."""
        with self._lock:
            return dict(self._processes)

    def set_snapshot(self, snapshot: dict[int, Process]):
        """Replace current snapshot with a new one."""
        with self._lock:
            self._processes = dict(snapshot)

    def get(self, pid: int) -> Process | None:
        with self._lock:
            return self._processes.get(pid)

    def contains(self, pid: int) -> bool:
        with self._lock:
            return pid in self._processes

    def count(self) -> int:
        with self._lock:
            return len(self._processes)

    def clear(self):
        with self._lock:
            self._processes.clear()


def diff_process_snapshots(
    previous: dict[int, Process],
    current: dict[int, Process],
    observed_at: datetime | None = None,
) -> list[SystemEvent]:
    """
    Compare previous snapshot with current snapshot to detect established process events.

    Factual Linux events generated:
    - process.created: A PID was newly observed in /proc
    - process.removed: A PID is no longer present in /proc
    - process.state_changed: A process transitioned state (e.g. S -> R, S -> T)
    - process.cwd_changed: A process changed working directory
    """
    if observed_at is None:
        observed_at = datetime.now()

    events: list[SystemEvent] = []

    prev_pids = set(previous.keys())
    curr_pids = set(current.keys())

    # 1. Newly observed processes
    for pid in sorted(curr_pids - prev_pids):
        proc = current[pid]
        events.append(
            SystemEvent(
                event_type="process.created",
                data={
                    "pid": proc.pid,
                    "ppid": proc.ppid,
                    "command": proc.command,
                    "state": proc.state,
                    "observed_at": observed_at,
                    "process": proc,
                },
                timestamp=observed_at,
            )
        )

    # 2. Processes no longer present in /proc
    for pid in sorted(prev_pids - curr_pids):
        old_proc = previous[pid]
        events.append(
            SystemEvent(
                event_type="process.removed",
                data={
                    "pid": old_proc.pid,
                    "ppid": old_proc.ppid,
                    "command": old_proc.command,
                    "state": old_proc.state,
                    "observed_at": observed_at,
                },
                timestamp=observed_at,
            )
        )

    # 3. Persistent processes: check for state or CWD diffs
    for pid in sorted(prev_pids & curr_pids):
        old_proc = previous[pid]
        curr_proc = current[pid]

        if old_proc.state != curr_proc.state:
            events.append(
                SystemEvent(
                    event_type="process.state_changed",
                    data={
                        "pid": curr_proc.pid,
                        "old_state": old_proc.state,
                        "new_state": curr_proc.state,
                        "command": curr_proc.command,
                        "observed_at": observed_at,
                    },
                    timestamp=observed_at,
                )
            )

        if old_proc.cwd != curr_proc.cwd:
            events.append(
                SystemEvent(
                    event_type="process.cwd_changed",
                    data={
                        "pid": curr_proc.pid,
                        "old_cwd": str(old_proc.cwd) if old_proc.cwd else None,
                        "new_cwd": str(curr_proc.cwd) if curr_proc.cwd else None,
                        "command": curr_proc.command,
                        "observed_at": observed_at,
                    },
                    timestamp=observed_at,
                )
            )

    return events


class TerminalSessionRegistry:
    """
    Keeps track of currently known terminal sessions (backward compatibility).
    """

    def __init__(self):
        self._sessions: dict[int, TerminalSession] = {}

    def add(self, session: TerminalSession):
        self._sessions[session.pid] = session

    def remove(self, pid: int):
        self._sessions.pop(pid, None)

    def get(self, pid: int) -> TerminalSession | None:
        return self._sessions.get(pid)

    def all(self) -> list[TerminalSession]:
        return list(self._sessions.values())

    def contains(self, pid: int) -> bool:
        return pid in self._sessions

    def clear(self):
        self._sessions.clear()
