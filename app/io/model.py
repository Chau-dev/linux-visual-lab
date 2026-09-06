from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FdType(str, Enum):
    """
    Directly derived categorization of Linux file descriptors based on the observed target string.
    """
    REGULAR_FILE = "FILE"
    DIRECTORY = "DIR"
    PTY_TTY = "TTY"
    PIPE = "PIPE"
    SOCKET = "SOCKET"
    ANON_INODE = "ANON"
    DEVICE = "DEV"
    DELETED = "DELETED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FileDescriptor:
    """
    Point-in-time observation of an open file descriptor in /proc/<pid>/fd/<fd>.

    Fields:
      - fd: Integer file descriptor index (0, 1, 2, 3, ...)
      - target: Raw resolved symlink target string from readlink (/proc/<pid>/fd/<fd>)
      - fd_type: Directly derived categorization (FILE, TTY, PIPE, SOCKET, etc.)
      - target_inode: Raw extracted inode number (e.g. 78123 from pipe:[78123] or socket:[42819])
      - anon_type: Raw recognized tag for anon_inode targets (e.g. 'eventfd', 'epoll', 'timerfd')
      - pos: File offset cursor in bytes from fdinfo, or None if omitted / non-seekable
      - flags_octal: Raw octal string from fdinfo (e.g. '0200002'), or None if unreadable
      - access_mode: Directly decoded access mode ('O_RDONLY', 'O_WRONLY', 'O_RDWR')
      - status_flags: List of decoded POSIX flags ('O_APPEND', 'O_NONBLOCK', 'O_CLOEXEC', etc.)
      - mnt_id: Mount ID integer from fdinfo, or None
      - is_standard_stream: True if fd is in {0, 1, 2}
      - standard_stream_name: 'stdin' (0), 'stdout' (1), 'stderr' (2), or None
    """
    fd: int
    target: str
    fd_type: FdType
    target_inode: int | None = None
    anon_type: str | None = None
    pos: int | None = None
    flags_octal: str | None = None
    access_mode: str = "O_RDONLY"
    status_flags: tuple[str, ...] = ()
    mnt_id: int | None = None
    is_standard_stream: bool = False
    standard_stream_name: str | None = None

    @property
    def display_role(self) -> str:
        """Returns standard stream tag (e.g. 'stdin (0)') or general descriptor label."""
        if self.standard_stream_name:
            return f"{self.standard_stream_name} ({self.fd})"
        return f"fd {self.fd}"

    @property
    def is_pipe(self) -> bool:
        return self.fd_type == FdType.PIPE

    @property
    def is_socket(self) -> bool:
        return self.fd_type == FdType.SOCKET

    @property
    def pipe_endpoint_role(self) -> str:
        """
        Directly derived endpoint role from open access mode.
        Note: Describes descriptor configuration, not proof of active I/O.
        """
        if self.access_mode == "O_WRONLY":
            return "Write end"
        elif self.access_mode == "O_RDONLY":
            return "Read end"
        elif self.access_mode == "O_RDWR":
            return "Read/Write end"
        return "Unknown"


@dataclass(frozen=True)
class PipeEndpoint:
    """
    Represents an observed file descriptor referencing a pipe inode.
    """
    inode: int
    pid: int
    fd: int
    access_mode: str
    endpoint_role: str
    process_command: str


@dataclass(frozen=True)
class ProcessIoSnapshot:
    """
    Raw point-in-time cumulative I/O accounting from /proc/<pid>/io.

    Separates VFS system call counters from physical storage block counters.
    """
    # --- VFS Syscall Layer Counters ---
    rchar: int
    wchar: int
    syscr: int
    syscw: int

    # --- Storage / Block Layer Counters ---
    read_bytes: int
    write_bytes: int
    cancelled_write_bytes: int
    observed_at_timestamp: float


@dataclass(frozen=True)
class DerivedProcessIoRates:
    """
    Derived I/O rates computed from deltas between two consecutive ProcessIoSnapshot samples.

    All rates are explicitly marked as derived.
    """
    # --- VFS Syscall Rates ---
    rchar_per_sec: float
    wchar_per_sec: float
    syscr_per_sec: float
    syscw_per_sec: float

    # --- Storage / Block Layer Rates ---
    read_bytes_per_sec: float
    write_bytes_per_sec: float
    cancelled_write_bytes_per_sec: float
    interval_seconds: float


@dataclass(frozen=True)
class DiskDeviceStat:
    """
    Point-in-time block device statistics from /proc/diskstats.
    """
    major: int
    minor: int
    device_name: str
    reads_completed: int
    reads_merged: int
    sectors_read: int
    read_time_ms: int
    writes_completed: int
    writes_merged: int
    sectors_written: int
    write_time_ms: int
    io_in_progress: int
    io_time_ms: int
    weighted_io_time_ms: int


@dataclass(frozen=True)
class KernelFileLock:
    """
    Point-in-time active kernel file lock from /proc/locks.
    """
    lock_num: int
    lock_type: str  # POSIX, FLOCK, OFD
    mode: str       # READ, WRITE
    state: str      # ADVISORY, MANDATORY
    pid: int | None
    maj_min_ino: str
    start_pos: str
    end_pos: str
