from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.cpu.model import CpuStatSnapshot, CpuTimes


def _parse_cpu_times_line(parts: list[str]) -> CpuTimes | None:
    """
    Parse a list of string tokens representing CPU time counters from /proc/stat.

    Expects at least 4 tokens (user, nice, system, idle).
    Optionally parses iowait, irq, softirq, steal, guest, guest_nice.
    """
    if len(parts) < 4:
        return None

    try:
        user = int(parts[0])
        nice = int(parts[1])
        system = int(parts[2])
        idle = int(parts[3])
        iowait = int(parts[4]) if len(parts) > 4 else 0
        irq = int(parts[5]) if len(parts) > 5 else 0
        softirq = int(parts[6]) if len(parts) > 6 else 0
        steal = int(parts[7]) if len(parts) > 7 else 0
        guest = int(parts[8]) if len(parts) > 8 else 0
        guest_nice = int(parts[9]) if len(parts) > 9 else 0

        return CpuTimes(
            user=user,
            nice=nice,
            system=system,
            idle=idle,
            iowait=iowait,
            irq=irq,
            softirq=softirq,
            steal=steal,
            guest=guest,
            guest_nice=guest_nice,
        )
    except (ValueError, IndexError):
        return None


def read_cpu_stat(
    proc_root: Path = Path("/proc"),
    stat_path: Path | None = None,
) -> CpuStatSnapshot | None:
    """
    Extract factual Linux CPU statistics directly from /proc/stat.

    Strict Truth Rules:
      - Requires a valid aggregate 'cpu' line.
      - Extracts per-core 'cpu<N>' entries where present.
      - Extracts ctxt, processes, procs_running, procs_blocked, btime.
      - Returns None if /proc/stat is missing, unreadable, or missing aggregate CPU data.
    """
    if stat_path is not None:
        target_path = Path(stat_path)
    elif Path(proc_root).is_file() or Path(proc_root).name == "stat":
        target_path = Path(proc_root)
    else:
        target_path = Path(proc_root) / "stat"

    if not target_path.exists():
        return None

    try:
        content = target_path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError, UnicodeDecodeError):
        return None

    total_cpu: CpuTimes | None = None
    cores: dict[int, CpuTimes] = {}
    ctxt = 0
    processes = 0
    procs_running = 0
    procs_blocked = 0
    btime = 0

    core_regex = re.compile(r"^cpu(\d+)$")

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if not parts:
            continue

        key = parts[0]
        values = parts[1:]

        if key == "cpu":
            total_cpu = _parse_cpu_times_line(values)
        elif core_regex.match(key):
            m = core_regex.match(key)
            if m:
                core_id = int(m.group(1))
                core_times = _parse_cpu_times_line(values)
                if core_times is not None:
                    cores[core_id] = core_times
        elif key == "ctxt" and values:
            try:
                ctxt = int(values[0])
            except ValueError:
                pass
        elif key == "processes" and values:
            try:
                processes = int(values[0])
            except ValueError:
                pass
        elif key == "procs_running" and values:
            try:
                procs_running = int(values[0])
            except ValueError:
                pass
        elif key == "procs_blocked" and values:
            try:
                procs_blocked = int(values[0])
            except ValueError:
                pass
        elif key == "btime" and values:
            try:
                btime = int(values[0])
            except ValueError:
                pass

    if total_cpu is None:
        return None

    return CpuStatSnapshot(
        total_cpu=total_cpu,
        cores=cores,
        ctxt=ctxt,
        processes=processes,
        procs_running=procs_running,
        procs_blocked=procs_blocked,
        btime=btime,
        observed_at=datetime.now(),
    )
