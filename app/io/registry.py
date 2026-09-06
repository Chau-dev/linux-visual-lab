from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.events import SystemEvent
from app.io.model import (
    FileDescriptor,
    PipeEndpoint,
    ProcessIoSnapshot,
    DerivedProcessIoRates,
)


@dataclass
class ProcessIoState:
    """
    Complete state representation for a single observed process in the I/O subsystem.
    """
    pid: int
    descriptors: list[FileDescriptor] = field(default_factory=list)
    error_reason: str | None = None
    io_snapshot: ProcessIoSnapshot | None = None
    derived_rates: DerivedProcessIoRates | None = None
    resolved_pipes: dict[int, list[PipeEndpoint]] = field(default_factory=dict)  # pipe_inode -> [PipeEndpoint, ...]


class IoRegistry:
    """
    State manager and diff engine for the Linux File Descriptors & I/O Subsystem.

    Operates in focus-driven mode for the target PID.
    Diffs consecutive samples to emit:
      - io.fd_appeared
      - io.fd_disappeared
      - io.pipe_shared (only when at least two endpoints are observed)
    """

    def __init__(self):
        self._target_pid: int | None = None
        self._previous_fds: dict[int, FileDescriptor] = {}  # fd_num -> FileDescriptor
        self._previous_io: ProcessIoSnapshot | None = None
        self._previous_shared_pipe_inodes: set[int] = set()

    @property
    def target_pid(self) -> int | None:
        return self._target_pid

    def set_target_pid(self, pid: int | None):
        """Switch tracked target process, clearing previous diff state."""
        if self._target_pid != pid:
            self._target_pid = pid
            self._previous_fds.clear()
            self._previous_io = None
            self._previous_shared_pipe_inodes.clear()

    def calculate_derived_rates(
        self, current: ProcessIoSnapshot, previous: ProcessIoSnapshot | None
    ) -> DerivedProcessIoRates | None:
        """
        Calculates derived rates (Δmetric / Δt) between two consecutive ProcessIoSnapshots.
        """
        if previous is None:
            return None

        dt = current.observed_at_timestamp - previous.observed_at_timestamp
        if dt <= 0.0001:
            return None

        return DerivedProcessIoRates(
            rchar_per_sec=max(0.0, (current.rchar - previous.rchar) / dt),
            wchar_per_sec=max(0.0, (current.wchar - previous.wchar) / dt),
            syscr_per_sec=max(0.0, (current.syscr - previous.syscr) / dt),
            syscw_per_sec=max(0.0, (current.syscw - previous.syscw) / dt),
            read_bytes_per_sec=max(0.0, (current.read_bytes - previous.read_bytes) / dt),
            write_bytes_per_sec=max(0.0, (current.write_bytes - previous.write_bytes) / dt),
            cancelled_write_bytes_per_sec=max(
                0.0, (current.cancelled_write_bytes - previous.cancelled_write_bytes) / dt
            ),
            interval_seconds=dt,
        )

    def update(
        self,
        pid: int,
        descriptors: list[FileDescriptor] | None,
        error_reason: str | None,
        io_snapshot: ProcessIoSnapshot | None,
        resolved_pipes: dict[int, list[PipeEndpoint]] | None = None,
        observed_at: datetime | None = None,
    ) -> tuple[ProcessIoState, list[SystemEvent]]:
        """
        Processes a new point-in-time sample for the given PID.

        Returns:
          (ProcessIoState, list[SystemEvent])
        """
        if observed_at is None:
            observed_at = datetime.now()

        if self._target_pid != pid:
            self.set_target_pid(pid)

        resolved_pipes = resolved_pipes or {}
        events: list[SystemEvent] = []

        # 1. Compute Derived I/O Rates
        derived_rates: DerivedProcessIoRates | None = None
        if io_snapshot is not None:
            derived_rates = self.calculate_derived_rates(io_snapshot, self._previous_io)
            self._previous_io = io_snapshot

        # 2. If descriptors is None (e.g. EACCES or ESRCH), record state and return
        if descriptors is None:
            self._previous_fds.clear()
            self._previous_shared_pipe_inodes.clear()
            state = ProcessIoState(
                pid=pid,
                descriptors=[],
                error_reason=error_reason,
                io_snapshot=io_snapshot,
                derived_rates=derived_rates,
                resolved_pipes=resolved_pipes,
            )
            return state, events

        # 3. Diff File Descriptors (io.fd_appeared, io.fd_disappeared)
        current_fds_map = {fd.fd: fd for fd in descriptors}

        # Check for appeared FDs
        for fd_num, fd_obj in current_fds_map.items():
            if fd_num not in self._previous_fds:
                events.append(
                    SystemEvent(
                        event_type="io.fd_appeared",
                        data={
                            "pid": pid,
                            "fd": fd_num,
                            "target": fd_obj.target,
                            "fd_type": fd_obj.fd_type.value,
                            "role": fd_obj.display_role,
                            "access_mode": fd_obj.access_mode,
                        },
                        observed_at=observed_at,
                        source="Linux /proc/<pid>/fd observer",
                        mechanism="/proc/<pid>/fd/*",
                    )
                )

        # Check for disappeared FDs
        for fd_num, prev_fd_obj in self._previous_fds.items():
            if fd_num not in current_fds_map:
                events.append(
                    SystemEvent(
                        event_type="io.fd_disappeared",
                        data={
                            "pid": pid,
                            "fd": fd_num,
                            "target": prev_fd_obj.target,
                            "fd_type": prev_fd_obj.fd_type.value,
                            "role": prev_fd_obj.display_role,
                        },
                        observed_at=observed_at,
                        source="Linux /proc/<pid>/fd observer",
                        mechanism="/proc/<pid>/fd/*",
                    )
                )

        self._previous_fds = current_fds_map

        # 4. Check for Shared Pipe Endpoints (io.pipe_shared)
        # Safeguard: Emit only when at least 2 endpoints are observed!
        current_shared_pipes = set()
        for pipe_inode, endpoints in resolved_pipes.items():
            if len(endpoints) >= 2:
                current_shared_pipes.add(pipe_inode)
                if pipe_inode not in self._previous_shared_pipe_inodes:
                    endpoints_info = [
                        {
                            "pid": ep.pid,
                            "fd": ep.fd,
                            "access_mode": ep.access_mode,
                            "role": ep.endpoint_role,
                            "command": ep.process_command,
                        }
                        for ep in endpoints
                    ]
                    events.append(
                        SystemEvent(
                            event_type="io.pipe_shared",
                            data={
                                "pipe_inode": pipe_inode,
                                "endpoints_count": len(endpoints),
                                "endpoints": endpoints_info,
                            },
                            observed_at=observed_at,
                            source="Linux Pipe Endpoint Resolver",
                            mechanism="/proc/<pid>/fd & /proc/<pid>/fdinfo",
                        )
                    )

        self._previous_shared_pipe_inodes = current_shared_pipes

        state = ProcessIoState(
            pid=pid,
            descriptors=descriptors,
            error_reason=None,
            io_snapshot=io_snapshot,
            derived_rates=derived_rates,
            resolved_pipes=resolved_pipes,
        )

        return state, events
