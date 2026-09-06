from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def format_kb(val_kb: int | None) -> str:
    """Format an integer kB value into human-readable unit (KB, MB, GB, TB)."""
    if val_kb is None:
        return "N/A"
    if val_kb < 0:
        return f"{val_kb} KB"
    if val_kb < 1024:
        return f"{val_kb} KB"
    elif val_kb < 1024 * 1024:
        return f"{val_kb / 1024:.2f} MB"
    elif val_kb < 1024 * 1024 * 1024:
        return f"{val_kb / (1024 * 1024):.2f} GB"
    else:
        return f"{val_kb / (1024 * 1024 * 1024):.2f} TB"


@dataclass(frozen=True)
class MemorySnapshot:
    """
    Represents point-in-time raw Linux memory statistics extracted from /proc/meminfo.

    Required fields are directly parsed integers in kB.
    Optional fields are None if omitted by the kernel (never fabricated as 0).
    Derived properties are explicitly marked with `derived_`.
    """

    # --- Required Raw Linux /proc/meminfo Fields (in kB) ---
    mem_total_kb: int
    mem_free_kb: int
    mem_available_kb: int
    buffers_kb: int
    cached_kb: int
    swap_total_kb: int
    swap_free_kb: int

    # --- Optional Raw Linux /proc/meminfo Fields (in kB, or None) ---
    swap_cached_kb: int | None = None
    active_kb: int | None = None
    inactive_kb: int | None = None
    active_anon_kb: int | None = None
    inactive_anon_kb: int | None = None
    active_file_kb: int | None = None
    inactive_file_kb: int | None = None
    unevictable_kb: int | None = None
    mlocked_kb: int | None = None
    dirty_kb: int | None = None
    writeback_kb: int | None = None
    anon_pages_kb: int | None = None
    mapped_kb: int | None = None
    shmem_kb: int | None = None
    slab_kb: int | None = None
    sreclaimable_kb: int | None = None
    sunreclaim_kb: int | None = None
    kreclaimable_kb: int | None = None
    committed_as_kb: int | None = None
    commit_limit_kb: int | None = None

    # --- Explicitly Labeled Derived Properties ---

    @property
    def derived_used_approx_kb(self) -> int:
        """
        Derived approximation: MemTotal - MemAvailable.
        Note: This is an application-calculated estimate, not a raw Linux field.
        """
        return max(0, self.mem_total_kb - self.mem_available_kb)

    @property
    def derived_used_percent(self) -> float:
        """Derived percentage of used memory approximation."""
        if self.mem_total_kb <= 0:
            return 0.0
        return (self.derived_used_approx_kb / self.mem_total_kb) * 100.0

    @property
    def derived_available_percent(self) -> float:
        """Derived percentage of MemAvailable relative to MemTotal."""
        if self.mem_total_kb <= 0:
            return 0.0
        return (self.mem_available_kb / self.mem_total_kb) * 100.0

    @property
    def derived_free_percent(self) -> float:
        """Derived percentage of MemFree relative to MemTotal."""
        if self.mem_total_kb <= 0:
            return 0.0
        return (self.mem_free_kb / self.mem_total_kb) * 100.0

    @property
    def derived_swap_used_kb(self) -> int:
        """Derived swap used: SwapTotal - SwapFree."""
        return max(0, self.swap_total_kb - self.swap_free_kb)

    @property
    def derived_swap_used_percent(self) -> float:
        """Derived percentage of swap used."""
        if self.swap_total_kb <= 0:
            return 0.0
        return (self.derived_swap_used_kb / self.swap_total_kb) * 100.0

    @property
    def derived_buffers_cached_kreclaimable_kb(self) -> int:
        """
        Derived sum: Buffers + Cached + KReclaimable (or 0 if KReclaimable is None).
        Note: This is an application-defined sum, not a single Linux category.
        """
        return self.buffers_kb + self.cached_kb + (self.kreclaimable_kb or 0)


@dataclass(frozen=True)
class SystemLoadSnapshot:
    """
    Represents raw point-in-time system load and uptime statistics from /proc/loadavg & /proc/uptime.
    """

    load_1m: float
    load_5m: float
    load_15m: float
    runnable_entities: int
    total_entities: int
    last_pid: int
    uptime_seconds: float
    idle_seconds: float

    @property
    def running_threads(self) -> int:
        """Alias for runnable_entities."""
        return self.runnable_entities

    @property
    def total_threads(self) -> int:
        """Alias for total_entities."""
        return self.total_entities

    @property
    def uptime_formatted(self) -> str:
        """Derived string representation of uptime."""
        return self.derived_formatted_uptime

    @property
    def derived_formatted_uptime(self) -> str:
        """Derived string representation of uptime (e.g. '2d 4h 12m 30s')."""
        total_seconds = int(self.uptime_seconds)
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or hours > 0 or days > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        return " ".join(parts)
