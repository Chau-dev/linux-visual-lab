from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from app.io.model import (
    FdType,
    FileDescriptor,
    PipeEndpoint,
    ProcessIoSnapshot,
    DiskDeviceStat,
    KernelFileLock,
)


def decode_open_flags(flags_val: int) -> tuple[str, tuple[str, ...]]:
    """
    Decodes raw Linux POSIX open flags integer into an access mode and tuple of status flags.

    Linux Access Modes (flags & 3):
      - 0 (00): O_RDONLY
      - 1 (01): O_WRONLY
      - 2 (02): O_RDWR

    Common Linux Status & Creation Flags:
      - O_APPEND (0o2000)
      - O_NONBLOCK / O_NDELAY (0o4000)
      - O_SYNC (0o4010000 or 0o10000)
      - O_ASYNC (0o20000)
      - O_DIRECT (0o40000)
      - O_LARGEFILE (0o100000)
      - O_DIRECTORY (0o200000)
      - O_NOFOLLOW (0o400000)
      - O_NOATIME (0o1000000)
      - O_CLOEXEC (0o2000000)
      - O_PATH (0o10000000)
    """
    # 1. Determine Access Mode
    acc_mode_raw = flags_val & 3
    if acc_mode_raw == 0:
        access_mode = "O_RDONLY"
    elif acc_mode_raw == 1:
        access_mode = "O_WRONLY"
    elif acc_mode_raw == 2:
        access_mode = "O_RDWR"
    else:
        access_mode = "O_RDONLY"

    # 2. Extract Status & Creation Flags
    status_flags: list[str] = []

    FLAG_MAP = [
        (0o2000, "O_APPEND"),
        (0o4000, "O_NONBLOCK"),
        (0o20000, "O_ASYNC"),
        (0o40000, "O_DIRECT"),
        (0o100000, "O_LARGEFILE"),
        (0o200000, "O_DIRECTORY"),
        (0o400000, "O_NOFOLLOW"),
        (0o1000000, "O_NOATIME"),
        (0o2000000, "O_CLOEXEC"),
        (0o10000000, "O_PATH"),
    ]

    # Special check for O_SYNC (which on Linux can be 0o4010000 or 0o10000)
    if (flags_val & 0o10000) or (flags_val & 0o4000000):
        status_flags.append("O_SYNC")

    for bitmask, name in FLAG_MAP:
        if flags_val & bitmask:
            status_flags.append(name)

    return access_mode, tuple(status_flags)


def parse_target_type(target: str) -> tuple[FdType, int | None, str | None]:
    """
    Directly derives FdType, extracted Inode integer, and recognized anon_tag from raw readlink target.
    """
    if target.startswith("pipe:[") and target.endswith("]"):
        try:
            inode = int(target[6:-1])
            return FdType.PIPE, inode, None
        except ValueError:
            return FdType.PIPE, None, None

    if target.startswith("socket:[") and target.endswith("]"):
        try:
            inode = int(target[8:-1])
            return FdType.SOCKET, inode, None
        except ValueError:
            return FdType.SOCKET, None, None

    if target.startswith("anon_inode:"):
        anon_tag = target[11:].strip("[]")
        return FdType.ANON_INODE, None, anon_tag

    if (
        target.startswith("/dev/pts/")
        or target.startswith("/dev/tty")
        or target.startswith("/dev/char(")
    ):
        return FdType.PTY_TTY, None, None

    if target.startswith("/dev/"):
        return FdType.DEVICE, None, None

    if target.endswith(" (deleted)"):
        return FdType.DELETED, None, None

    if target.startswith("/"):
        return FdType.REGULAR_FILE, None, None

    return FdType.UNKNOWN, None, None


def parse_fdinfo(fdinfo_path: Path) -> dict[str, Any]:
    """
    Parses key-value pairs from /proc/<pid>/fdinfo/<fd>.
    """
    result: dict[str, Any] = {}
    try:
        content = fdinfo_path.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if key == "pos":
                try:
                    result["pos"] = int(val)
                except ValueError:
                    result["pos"] = None
            elif key == "flags":
                result["flags_octal"] = val
                try:
                    result["flags_int"] = int(val, 8)
                except ValueError:
                    result["flags_int"] = 0
            elif key == "mnt_id":
                try:
                    result["mnt_id"] = int(val)
                except ValueError:
                    result["mnt_id"] = None
            elif key == "ino":
                try:
                    result["ino"] = int(val)
                except ValueError:
                    result["ino"] = None
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        pass

    return result


def read_process_fds(
    pid: int, proc_root: Path = Path("/proc")
) -> tuple[list[FileDescriptor] | None, str | None]:
    """
    Reads and parses all open file descriptors for the given PID.

    Returns:
      (list[FileDescriptor], None) on success
      (None, "EACCES") if unreadable due to permission restrictions
      (None, "ESRCH") if process terminated or does not exist
      (None, "ERROR") for unexpected OS errors
    """
    fd_dir = proc_root / str(pid) / "fd"
    fdinfo_dir = proc_root / str(pid) / "fdinfo"

    if not fd_dir.exists():
        return None, "ESRCH"

    try:
        entries = sorted(os.listdir(fd_dir), key=lambda x: int(x) if x.isdigit() else 999999)
    except PermissionError:
        return None, "EACCES"
    except (FileNotFoundError, ProcessLookupError):
        return None, "ESRCH"
    except OSError:
        return None, "ERROR"

    descriptors: list[FileDescriptor] = []

    for entry_name in entries:
        if not entry_name.isdigit():
            continue
        fd_num = int(entry_name)
        fd_path = fd_dir / entry_name
        fdinfo_path = fdinfo_dir / entry_name

        try:
            target = os.readlink(fd_path)
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            target = "<access denied>"
        except OSError:
            target = "<unreadable>"

        fd_type, target_inode, anon_tag = parse_target_type(target)

        # Parse fdinfo metadata if accessible
        info = parse_fdinfo(fdinfo_path)
        pos = info.get("pos")
        flags_octal = info.get("flags_octal")
        flags_int = info.get("flags_int", 0)
        mnt_id = info.get("mnt_id")

        access_mode, status_flags = decode_open_flags(flags_int)

        # Standard stream roles
        is_std = fd_num in (0, 1, 2)
        std_name = {0: "stdin", 1: "stdout", 2: "stderr"}.get(fd_num)

        descriptors.append(
            FileDescriptor(
                fd=fd_num,
                target=target,
                fd_type=fd_type,
                target_inode=target_inode,
                anon_type=anon_tag,
                pos=pos,
                flags_octal=flags_octal,
                access_mode=access_mode,
                status_flags=status_flags,
                mnt_id=mnt_id,
                is_standard_stream=is_std,
                standard_stream_name=std_name,
            )
        )

    return descriptors, None


def find_pipe_peer_endpoints(
    pipe_inode: int,
    exclude_pid: int,
    candidate_pids: list[int] | None = None,
    proc_root: Path = Path("/proc"),
    max_scan_limit: int = 150,
) -> list[PipeEndpoint]:
    """
    Targeted, bounded search across accessible running processes to find peer endpoints
    referencing the specified pipe inode.

    Runs strictly inside the background worker thread.
    """
    peers: list[PipeEndpoint] = []
    target_str = f"pipe:[{pipe_inode}]"

    if candidate_pids is not None:
        pids_to_check = [p for p in candidate_pids if p != exclude_pid][:max_scan_limit]
    else:
        try:
            all_entries = os.listdir(proc_root)
            pids_to_check = [
                int(e) for e in all_entries if e.isdigit() and int(e) != exclude_pid
            ][:max_scan_limit]
        except (OSError, PermissionError):
            return peers

    for cand_pid in pids_to_check:
        cand_fd_dir = proc_root / str(cand_pid) / "fd"
        try:
            fd_entries = os.listdir(cand_fd_dir)
        except (PermissionError, FileNotFoundError, ProcessLookupError, OSError):
            continue

        for fd_str in fd_entries:
            if not fd_str.isdigit():
                continue
            fd_num = int(fd_str)
            try:
                link_target = os.readlink(cand_fd_dir / fd_str)
            except (OSError, PermissionError, FileNotFoundError, ProcessLookupError):
                continue

            if link_target == target_str:
                # Read access mode from fdinfo
                fdinfo_path = proc_root / str(cand_pid) / "fdinfo" / fd_str
                info = parse_fdinfo(fdinfo_path)
                flags_int = info.get("flags_int", 0)
                access_mode, _ = decode_open_flags(flags_int)

                if access_mode == "O_WRONLY":
                    role = "Write end"
                elif access_mode == "O_RDONLY":
                    role = "Read end"
                elif access_mode == "O_RDWR":
                    role = "Read/Write end"
                else:
                    role = "Unknown"

                # Get process command name
                comm_path = proc_root / str(cand_pid) / "comm"
                try:
                    cmd_name = comm_path.read_text(encoding="utf-8").strip()
                except OSError:
                    cmd_name = f"PID {cand_pid}"

                peers.append(
                    PipeEndpoint(
                        inode=pipe_inode,
                        pid=cand_pid,
                        fd=fd_num,
                        access_mode=access_mode,
                        endpoint_role=role,
                        process_command=cmd_name,
                    )
                )

    return peers


def read_process_io(
    pid: int, proc_root: Path = Path("/proc")
) -> ProcessIoSnapshot | None:
    """
    Parses raw cumulative I/O accounting from /proc/<pid>/io.
    Returns None if unreadable or permission denied.
    """
    io_path = proc_root / str(pid) / "io"
    try:
        content = io_path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None

    data: dict[str, int] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        try:
            data[key.strip()] = int(val.strip())
        except ValueError:
            continue

    required_keys = ["rchar", "wchar", "syscr", "syscw", "read_bytes", "write_bytes"]
    if not all(k in data for k in required_keys):
        return None

    return ProcessIoSnapshot(
        rchar=data.get("rchar", 0),
        wchar=data.get("wchar", 0),
        syscr=data.get("syscr", 0),
        syscw=data.get("syscw", 0),
        read_bytes=data.get("read_bytes", 0),
        write_bytes=data.get("write_bytes", 0),
        cancelled_write_bytes=data.get("cancelled_write_bytes", 0),
        observed_at_timestamp=time.time(),
    )


def read_diskstats(proc_root: Path = Path("/proc")) -> list[DiskDeviceStat]:
    """
    Parses point-in-time storage device statistics from /proc/diskstats.
    Filters to physical block devices and partitions (e.g. sda, nvme0n1, vda).
    """
    diskstats_path = proc_root / "diskstats"
    stats: list[DiskDeviceStat] = []
    try:
        content = diskstats_path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError):
        return stats

    for line in content.splitlines():
        parts = line.strip().split()
        if len(parts) < 14:
            continue

        try:
            major = int(parts[0])
            minor = int(parts[1])
            dev_name = parts[2]

            # Filter out virtual loop / ram devices for clearer educational view
            if dev_name.startswith(("loop", "ram", "dm-", "zram")):
                continue

            reads_comp = int(parts[3])
            reads_merged = int(parts[4])
            sec_read = int(parts[5])
            read_time = int(parts[6])
            writes_comp = int(parts[7])
            writes_merged = int(parts[8])
            sec_written = int(parts[9])
            write_time = int(parts[10])
            io_prog = int(parts[11])
            io_time = int(parts[12])
            w_io_time = int(parts[13])

            stats.append(
                DiskDeviceStat(
                    major=major,
                    minor=minor,
                    device_name=dev_name,
                    reads_completed=reads_comp,
                    reads_merged=reads_merged,
                    sectors_read=sec_read,
                    read_time_ms=read_time,
                    writes_completed=writes_comp,
                    writes_merged=writes_merged,
                    sectors_written=sec_written,
                    write_time_ms=write_time,
                    io_in_progress=io_prog,
                    io_time_ms=io_time,
                    weighted_io_time_ms=w_io_time,
                )
            )
        except (ValueError, IndexError):
            continue

    return stats


def read_kernel_locks(proc_root: Path = Path("/proc")) -> list[KernelFileLock]:
    """
    Parses active kernel file locks from /proc/locks.
    """
    locks_path = proc_root / "locks"
    locks: list[KernelFileLock] = []
    try:
        content = locks_path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError):
        return locks

    for line in content.splitlines():
        parts = line.strip().split()
        if len(parts) < 6:
            continue

        try:
            # 1: POSIX  ADVISORY  WRITE 1234 08:01:12345 0 EOF
            lock_num_str = parts[0].rstrip(":")
            lock_num = int(lock_num_str) if lock_num_str.isdigit() else 0
            lock_type = parts[1]
            state = parts[2]
            mode = parts[3]

            # Check if PID is specified
            pid_str = parts[4]
            pid = int(pid_str) if pid_str.isdigit() else None

            maj_min_ino = parts[5] if len(parts) > 5 else "-"
            start_pos = parts[6] if len(parts) > 6 else "0"
            end_pos = parts[7] if len(parts) > 7 else "EOF"

            locks.append(
                KernelFileLock(
                    lock_num=lock_num,
                    lock_type=lock_type,
                    mode=mode,
                    state=state,
                    pid=pid,
                    maj_min_ino=maj_min_ino,
                    start_pos=start_pos,
                    end_pos=end_pos,
                )
            )
        except (ValueError, IndexError):
            continue

    return locks
