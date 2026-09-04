from __future__ import annotations

import os
import pwd
import grp
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Process:
    """
    Represents an observed Linux process directly extracted from /proc.

    All attributes correspond directly to Linux kernel state:
    - /proc/<pid>/stat: pid, ppid, pgid, sid, tpgid, state, comm
    - /proc/<pid>/status: uid, gid
    - /proc/<pid>/cmdline: cmdline
    - /proc/<pid>/cwd: cwd
    - /proc/<pid>/fd/0: tty
    """

    pid: int
    ppid: int
    pgid: int
    sid: int
    tpgid: int
    uid: int
    gid: int
    tty: str | None          # Controlling terminal decoded from /proc/<pid>/stat field 7 (tty_nr)
    tty_nr: int = 0          # Raw controlling terminal device number from /proc/<pid>/stat
    stdin_target: str | None = None  # Standard input target from /proc/<pid>/fd/0
    state: str = "S"         # Single-char Linux code ('R', 'S', 'D', 'Z', 'T', 't', 'X', 'I')
    command: str = ""        # comm or executable basename
    cmdline: str = ""        # Full argument string from /proc/<pid>/cmdline
    cwd: Path | None = None  # Resolved target of /proc/<pid>/cwd

    @property
    def state_description(self) -> str:
        """Factual Linux kernel state code mapping."""
        descriptions = {
            "R": "R (Running / Ready)",
            "S": "S (Interruptible Sleep)",
            "D": "D (Uninterruptible Disk Sleep)",
            "Z": "Z (Zombie / Defunct)",
            "T": "T (Stopped by job control signal)",
            "t": "t (Tracing stop)",
            "X": "X (Dead)",
            "x": "x (Dead)",
            "K": "K (Wakekill)",
            "W": "W (Waking)",
            "P": "P (Parked)",
            "I": "I (Idle kernel thread)",
        }
        return descriptions.get(self.state, f"{self.state} (Unknown State)")

    @property
    def user_name(self) -> str:
        """Resolve username from real Linux UID."""
        try:
            return pwd.getpwuid(self.uid).pw_name
        except (KeyError, OSError):
            return str(self.uid)

    @property
    def group_name(self) -> str:
        """Resolve group name from real Linux GID."""
        try:
            return grp.getgrgid(self.gid).gr_name
        except (KeyError, OSError):
            return str(self.gid)

    @property
    def is_session_leader(self) -> bool:
        """Linux kernel definition: PID equals Session ID (SID)."""
        return self.pid == self.sid

    @property
    def is_process_group_leader(self) -> bool:
        """Linux kernel definition: PID equals Process Group ID (PGID)."""
        return self.pid == self.pgid

    @property
    def is_foreground(self) -> bool:
        """Linux kernel definition: Process Group ID equals TTY Foreground PGID (TPGID)."""
        return self.tpgid > 0 and self.pgid == self.tpgid
