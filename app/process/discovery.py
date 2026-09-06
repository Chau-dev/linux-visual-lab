from __future__ import annotations

import os
from pathlib import Path

from app.process.session import TerminalSession
from app.process.model import Process


def decode_tty_nr(tty_nr: int) -> str | None:
    """
    Decode Linux controlling terminal device number (tty_nr from /proc/<pid>/stat field 7)
    into a canonical terminal device path (e.g. /dev/pts/1, /dev/tty1, /dev/ttyS0).

    Returns None if tty_nr is 0 or negative (process has no controlling terminal).
    """
    if not tty_nr or tty_nr <= 0:
        return None

    try:
        major = os.major(tty_nr)
        minor = os.minor(tty_nr)
    except (ValueError, OverflowError, OSError):
        return None

    # Unix98 PTY slaves: major 136 to 143
    if 136 <= major <= 143:
        pts_num = (major - 136) * 256 + minor
        return f"/dev/pts/{pts_num}"

    # Virtual consoles and standard serial ports: major 4
    if major == 4:
        if minor == 0:
            return "/dev/tty0"
        elif 1 <= minor < 64:
            return f"/dev/tty{minor}"
        else:
            return f"/dev/ttyS{minor - 64}"

    # TTY driver special devices: major 5
    if major == 5:
        if minor == 0:
            return "/dev/tty"
        elif minor == 1:
            return "/dev/console"
        elif minor == 2:
            return "/dev/ptmx"

    # USB serial devices: major 188
    if major == 188:
        return f"/dev/ttyUSB{minor}"

    # Low-density / ARM serial: major 204
    if major == 204:
        return f"/dev/ttyAMA{minor}"

    return f"/dev/char({major}:{minor})"


def get_process_stdin_target(pid: int, proc_root: Path = Path("/proc")) -> str | None:
    """
    Read the target of /proc/<pid>/fd/0 (file descriptor 0 = standard input).
    Can be a terminal device (/dev/pts/1), pipe, socket, regular file, or None if inaccessible.
    """
    fd_path = proc_root / str(pid) / "fd" / "0"
    try:
        target = fd_path.resolve(strict=True)
        return str(target)
    except (FileNotFoundError, PermissionError, OSError, ProcessLookupError):
        pass

    try:
        return os.readlink(fd_path)
    except (FileNotFoundError, PermissionError, OSError, ProcessLookupError):
        return None


def get_process_tty(pid: int, proc_root: Path = Path("/proc")) -> str | None:
    """
    Get the controlling terminal associated with a process via /proc/<pid>/stat field 7 (tty_nr).
    """
    stat_path = proc_root / str(pid) / "stat"
    try:
        content = stat_path.read_text(encoding="utf-8").strip()
        closing_paren = content.rfind(")")
        if closing_paren == -1:
            return None
        remainder = content[closing_paren + 2:].split()
        tty_nr = int(remainder[4])
        return decode_tty_nr(tty_nr)
    except (FileNotFoundError, PermissionError, OSError, ValueError, IndexError, ProcessLookupError):
        return None


def get_process_ppid(pid: int, proc_root: Path = Path("/proc")) -> int | None:
    """
    Read the parent PID from /proc/<pid>/stat.
    """
    stat_path = proc_root / str(pid) / "stat"
    try:
        content = stat_path.read_text(encoding="utf-8").strip()
        closing_paren = content.rfind(")")
        if closing_paren == -1:
            return None
        remainder = content[closing_paren + 2:].split()
        return int(remainder[1])
    except (FileNotFoundError, PermissionError, OSError, ValueError, IndexError, ProcessLookupError):
        return None


def read_process_info(pid: int, proc_root: Path = Path("/proc")) -> Process | None:
    """
    Extract factual Linux process state from /proc/<pid>/*.

    Returns:
        Process instance or None if the process disappeared or is inaccessible.
    """
    pid_dir = proc_root / str(pid)
    stat_path = pid_dir / "stat"
    status_path = pid_dir / "status"
    cmdline_path = pid_dir / "cmdline"
    cwd_path = pid_dir / "cwd"

    try:
        stat_content = stat_path.read_text(encoding="utf-8").strip()
        closing_paren = stat_content.rfind(")")
        opening_paren = stat_content.find("(")
        if closing_paren == -1 or opening_paren == -1:
            return None

        comm = stat_content[opening_paren + 1:closing_paren]
        remainder = stat_content[closing_paren + 2:].split()

        state = remainder[0]
        ppid = int(remainder[1])
        pgid = int(remainder[2])
        sid = int(remainder[3])
        tty_nr = int(remainder[4])
        tpgid = int(remainder[5])
        utime_ticks = int(remainder[11]) if len(remainder) > 11 else 0
        stime_ticks = int(remainder[12]) if len(remainder) > 12 else 0
        starttime = int(remainder[19]) if len(remainder) > 19 else 0

    except (FileNotFoundError, PermissionError, OSError, ValueError, IndexError, ProcessLookupError):
        return None

    # Parse Uid & Gid from /proc/<pid>/status
    uid = 0
    gid = 0
    try:
        status_lines = status_path.read_text(encoding="utf-8").splitlines()
        for line in status_lines:
            if line.startswith("Uid:"):
                parts = line.split()
                if len(parts) >= 2:
                    uid = int(parts[1])
            elif line.startswith("Gid:"):
                parts = line.split()
                if len(parts) >= 2:
                    gid = int(parts[1])
    except (FileNotFoundError, PermissionError, OSError, ValueError, ProcessLookupError):
        pass

    # Parse command line arguments from /proc/<pid>/cmdline
    cmdline = ""
    try:
        raw_cmdline = cmdline_path.read_bytes()
        args = [arg.decode("utf-8", errors="replace") for arg in raw_cmdline.split(b"\x00") if arg]
        cmdline = " ".join(args)
    except (FileNotFoundError, PermissionError, OSError, ProcessLookupError):
        pass

    if not cmdline:
        cmdline = f"[{comm}]"

    # Resolve CWD
    cwd: Path | None = None
    try:
        cwd = cwd_path.resolve(strict=True)
    except (FileNotFoundError, PermissionError, OSError, ProcessLookupError):
        cwd = None

    # Controlling terminal decoded directly from /proc/<pid>/stat field 7 (tty_nr)
    tty = decode_tty_nr(tty_nr)

    # Standard input target from /proc/<pid>/fd/0
    stdin_target = get_process_stdin_target(pid, proc_root=proc_root)

    return Process(
        pid=pid,
        ppid=ppid,
        pgid=pgid,
        sid=sid,
        tpgid=tpgid,
        uid=uid,
        gid=gid,
        tty=tty,
        tty_nr=tty_nr,
        stdin_target=stdin_target,
        state=state,
        command=comm,
        cmdline=cmdline,
        cwd=cwd,
        utime_ticks=utime_ticks,
        stime_ticks=stime_ticks,
        starttime=starttime,
    )



def discover_all_processes(proc_root: Path = Path("/proc")) -> dict[int, Process]:
    """
    Scan /proc and build a dictionary of all observable Linux processes.

    Returns:
        dict[int, Process] mapping PID to Process snapshot.
    """
    processes: dict[int, Process] = {}

    try:
        entries = list(proc_root.iterdir())
    except (FileNotFoundError, PermissionError, OSError):
        return {}

    for entry in entries:
        if not entry.name.isdigit():
            continue

        try:
            pid = int(entry.name)
            p = read_process_info(pid, proc_root=proc_root)
            if p is not None:
                processes[pid] = p
        except (ValueError, ProcessLookupError):
            continue

    return processes


def find_shell_processes(proc_root: Path = Path("/proc")) -> list[TerminalSession]:
    """
    Find running interactive shell processes for the Terminal Sessions panel.

    Returns:
        list[TerminalSession]
    """
    shells = []

    try:
        entries = list(proc_root.iterdir())
    except (FileNotFoundError, PermissionError, OSError):
        return []

    for entry in entries:
        if not entry.name.isdigit():
            continue

        pid = int(entry.name)
        comm_path = entry / "comm"

        try:
            command = comm_path.read_text(encoding="utf-8").strip()
        except (FileNotFoundError, PermissionError, OSError, ProcessLookupError):
            continue

        if command not in {
            "bash",
            "sh",
            "zsh",
            "fish",
            "dash",
            "ksh",
            "tcsh",
            "csh",
        }:
            continue

        cwd_path = entry / "cwd"
        try:
            cwd = cwd_path.resolve(strict=True)
        except (FileNotFoundError, PermissionError, OSError, ProcessLookupError):
            cwd = None

        tty = get_process_tty(pid, proc_root=proc_root)
        ppid = get_process_ppid(pid, proc_root=proc_root)

        if ppid is None:
            continue

        shells.append(
            TerminalSession(
                pid=pid,
                ppid=ppid,
                command=command,
                tty=tty,
                cwd=cwd,
            )
        )

    shells.sort(key=lambda session: session.pid)
    return shells
