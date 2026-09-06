from __future__ import annotations

import re
from pathlib import Path

from app.memory.model import MemorySnapshot, SystemLoadSnapshot


REQUIRED_MEMINFO_KEYS = {
    "MemTotal",
    "MemFree",
    "MemAvailable",
    "Buffers",
    "Cached",
    "SwapTotal",
    "SwapFree",
}


def read_memory_snapshot(
    proc_root: Path = Path("/proc"),
    meminfo_path: Path | None = None,
) -> MemorySnapshot | None:
    """
    Extract factual Linux memory state directly from /proc/meminfo.

    Strict Truth Rules:
      - Validates that lines follow the Linux kernel format (Key: <int> kB).
      - Checks that all required keys are present.
      - If any required key is missing or file is unreadable, returns None (never substitutes 0).
      - Optional fields default to None if not reported by the kernel.
    """
    if meminfo_path is not None:
        target_path = Path(meminfo_path)
    elif Path(proc_root).is_file() or Path(proc_root).name == "meminfo":
        target_path = Path(proc_root)
    else:
        target_path = Path(proc_root) / "meminfo"

    if not target_path.exists():
        return None

    parsed_kb: dict[str, int] = {}

    try:
        content = target_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue

            key, rest = line.split(":", 1)
            key = key.strip()
            rest = rest.strip()

            parts = rest.split()
            if not parts:
                continue

            try:
                val_int = int(parts[0])
            except ValueError:
                continue

            # Validate unit suffix if present
            if len(parts) > 1:
                unit = parts[1].lower()
                if unit != "kb":
                    # Unexpected unit - skip or reject to preserve accuracy
                    return None

            parsed_kb[key] = val_int

    except (FileNotFoundError, PermissionError, OSError, UnicodeDecodeError):
        return None

    # Strict check: all required keys must be present
    for req_key in REQUIRED_MEMINFO_KEYS:
        if req_key not in parsed_kb:
            return None

    return MemorySnapshot(
        mem_total_kb=parsed_kb["MemTotal"],
        mem_free_kb=parsed_kb["MemFree"],
        mem_available_kb=parsed_kb["MemAvailable"],
        buffers_kb=parsed_kb["Buffers"],
        cached_kb=parsed_kb["Cached"],
        swap_total_kb=parsed_kb["SwapTotal"],
        swap_free_kb=parsed_kb["SwapFree"],
        swap_cached_kb=parsed_kb.get("SwapCached"),
        active_kb=parsed_kb.get("Active"),
        inactive_kb=parsed_kb.get("Inactive"),
        active_anon_kb=parsed_kb.get("Active(anon)"),
        inactive_anon_kb=parsed_kb.get("Inactive(anon)"),
        active_file_kb=parsed_kb.get("Active(file)"),
        inactive_file_kb=parsed_kb.get("Inactive(file)"),
        unevictable_kb=parsed_kb.get("Unevictable"),
        mlocked_kb=parsed_kb.get("Mlocked"),
        dirty_kb=parsed_kb.get("Dirty"),
        writeback_kb=parsed_kb.get("Writeback"),
        anon_pages_kb=parsed_kb.get("AnonPages"),
        mapped_kb=parsed_kb.get("Mapped"),
        shmem_kb=parsed_kb.get("Shmem"),
        slab_kb=parsed_kb.get("Slab"),
        sreclaimable_kb=parsed_kb.get("SReclaimable"),
        sunreclaim_kb=parsed_kb.get("SUnreclaim"),
        kreclaimable_kb=parsed_kb.get("KReclaimable"),
        committed_as_kb=parsed_kb.get("Committed_AS"),
        commit_limit_kb=parsed_kb.get("CommitLimit"),
    )


def read_system_load(
    proc_root: Path = Path("/proc"),
    loadavg_path: Path | None = None,
    uptime_path: Path | None = None,
) -> SystemLoadSnapshot | None:
    """
    Extract factual system load averages and uptime from /proc/loadavg and /proc/uptime.

    Returns:
        SystemLoadSnapshot or None if files cannot be parsed.
    """
    if loadavg_path is None:
        loadavg_path = Path(proc_root) / "loadavg"
    else:
        loadavg_path = Path(loadavg_path)

    if uptime_path is None:
        uptime_path = Path(proc_root) / "uptime"
    else:
        uptime_path = Path(uptime_path)

    if not loadavg_path.exists() or not uptime_path.exists():
        return None

    try:
        # 1. Parse /proc/loadavg: "0.14 0.20 0.18 1/1542 27814"
        load_content = loadavg_path.read_text(encoding="utf-8").strip()
        load_parts = load_content.split()
        if len(load_parts) < 5:
            return None

        load_1m = float(load_parts[0])
        load_5m = float(load_parts[1])
        load_15m = float(load_parts[2])

        threads_part = load_parts[3]
        if "/" not in threads_part:
            return None
        running_str, total_str = threads_part.split("/", 1)
        runnable_entities = int(running_str)
        total_entities = int(total_str)

        last_pid = int(load_parts[4])

        # 2. Parse /proc/uptime: "47576.99 554584.57"
        uptime_content = uptime_path.read_text(encoding="utf-8").strip()
        uptime_parts = uptime_content.split()
        if len(uptime_parts) < 2:
            return None

        uptime_seconds = float(uptime_parts[0])
        idle_seconds = float(uptime_parts[1])

        return SystemLoadSnapshot(
            load_1m=load_1m,
            load_5m=load_5m,
            load_15m=load_15m,
            runnable_entities=runnable_entities,
            total_entities=total_entities,
            last_pid=last_pid,
            uptime_seconds=uptime_seconds,
            idle_seconds=idle_seconds,
        )

    except (FileNotFoundError, PermissionError, OSError, ValueError, IndexError, UnicodeDecodeError):
        return None
