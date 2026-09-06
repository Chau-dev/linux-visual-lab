from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from app.core.events import SystemEvent
from app.cpu.clock import get_clk_tck
from app.process.session import TerminalSession
from app.process.model import Process


class ProcessRegistry:
    """
    Thread-safe registry maintaining the current snapshot of Linux processes
    and tracking process CPU tick baselines keyed by (pid, starttime).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._processes: dict[int, Process] = {}
        self._cpu_baselines: dict[tuple[int, int], tuple[int, datetime]] = {}

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
            self._cpu_baselines.clear()

    def compute_cpu_utilization(
        self,
        current: dict[int, Process],
        observed_at: datetime | None = None,
        clk_tck: int | None = None,
    ) -> dict[int, Process]:
        """
        Derive wall-time CPU percentage for each active process.

        Formula:
          Δticks = (utime2 + stime2) - (utime1 + stime1)
          Δt = (curr_time - prev_time).total_seconds()
          derived_cpu_percent = (Δticks / clk_tck) / Δt * 100.0

        Safety & Reliability Rules:
          - Baseline identity is tracked by (pid, starttime) to protect against PID reuse.
          - If cumulative ticks decrease or dt <= 0, the interval is treated as invalid and baseline is reset.
          - Multi-core SMP scaling is preserved without clamping to 100%.
        """
        if observed_at is None:
            observed_at = datetime.now()

        resolved_tck = clk_tck if clk_tck is not None else get_clk_tck()
        enriched: dict[int, Process] = {}
        current_keys: set[tuple[int, int]] = set()

        with self._lock:
            for pid, proc in current.items():
                key = (proc.pid, proc.starttime)
                current_keys.add(key)
                derived_pct: float | None = None

                if key in self._cpu_baselines and resolved_tck is not None and resolved_tck > 0:
                    prev_ticks, prev_time = self._cpu_baselines[key]
                    dt = (observed_at - prev_time).total_seconds()
                    curr_ticks = proc.total_cpu_ticks

                    if curr_ticks < prev_ticks or dt <= 0:
                        # Counter reset or invalid delta - reset baseline without producing negative metric
                        self._cpu_baselines[key] = (curr_ticks, observed_at)
                    else:
                        d_ticks = curr_ticks - prev_ticks
                        derived_pct = (d_ticks / resolved_tck) / dt * 100.0
                        self._cpu_baselines[key] = (curr_ticks, observed_at)
                else:
                    self._cpu_baselines[key] = (proc.total_cpu_ticks, observed_at)

                if proc.derived_cpu_percent != derived_pct:
                    enriched[pid] = Process(
                        pid=proc.pid,
                        ppid=proc.ppid,
                        pgid=proc.pgid,
                        sid=proc.sid,
                        tpgid=proc.tpgid,
                        uid=proc.uid,
                        gid=proc.gid,
                        tty=proc.tty,
                        tty_nr=proc.tty_nr,
                        stdin_target=proc.stdin_target,
                        state=proc.state,
                        command=proc.command,
                        cmdline=proc.cmdline,
                        cwd=proc.cwd,
                        utime_ticks=proc.utime_ticks,
                        stime_ticks=proc.stime_ticks,
                        starttime=proc.starttime,
                        derived_cpu_percent=derived_pct,
                    )
                else:
                    enriched[pid] = proc

            # Prune baselines for terminated processes
            stale_keys = [k for k in self._cpu_baselines if k not in current_keys]
            for k in stale_keys:
                del self._cpu_baselines[k]

            self._processes = dict(enriched)
            return enriched


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
                    "cmdline": proc.cmdline or proc.command,
                    "state": proc.state,
                    "tty": proc.tty,
                    "cwd": str(proc.cwd) if proc.cwd else None,
                    "pgid": proc.pgid,
                    "sid": proc.sid,
                    "tpgid": proc.tpgid,
                    "observed_at": observed_at,
                    "process": proc,
                },
                observed_at=observed_at,
                source="Linux /proc snapshot",
                mechanism="/proc/<pid>/stat",
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
                observed_at=observed_at,
                source="Linux /proc snapshot",
                mechanism="/proc/<pid>",
            )
        )

    # 3. Persistent processes: check for PID-reuse, state diffs, or CWD diffs
    for pid in sorted(prev_pids & curr_pids):
        old_proc = previous[pid]
        curr_proc = current[pid]

        # PID reuse protection: starttime changed
        if old_proc.starttime != curr_proc.starttime and old_proc.starttime > 0 and curr_proc.starttime > 0:
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
                    observed_at=observed_at,
                    source="Linux /proc snapshot",
                    mechanism="/proc/<pid>",
                )
            )
            events.append(
                SystemEvent(
                    event_type="process.created",
                    data={
                        "pid": curr_proc.pid,
                        "ppid": curr_proc.ppid,
                        "command": curr_proc.command,
                        "cmdline": curr_proc.cmdline or curr_proc.command,
                        "state": curr_proc.state,
                        "tty": curr_proc.tty,
                        "cwd": str(curr_proc.cwd) if curr_proc.cwd else None,
                        "pgid": curr_proc.pgid,
                        "sid": curr_proc.sid,
                        "tpgid": curr_proc.tpgid,
                        "observed_at": observed_at,
                        "process": curr_proc,
                    },
                    observed_at=observed_at,
                    source="Linux /proc snapshot",
                    mechanism="/proc/<pid>/stat",
                )
            )
            continue

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
                    observed_at=observed_at,
                    source="Linux /proc snapshot",
                    mechanism="/proc/<pid>/stat",
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
                    observed_at=observed_at,
                    source="Linux /proc snapshot",
                    mechanism="/proc/<pid>/cwd",
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
