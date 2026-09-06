from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CpuTimes:
    """
    Raw cumulative CPU-time counters extracted directly from Linux /proc/stat in USER_HZ clock ticks.

    Fields:
      - user: Time spent in user mode.
      - nice: Time spent in user mode with low priority (nice).
      - system: Time spent in system mode.
      - idle: Time spent in the idle task.
      - iowait: Time waiting for I/O to complete (Linux note: cumulative counter).
      - irq: Time servicing interrupts.
      - softirq: Time servicing softirqs.
      - steal: Stolen time spent in other operating systems in virtualized environments.
      - guest: Time spent running a virtual CPU for guest OS (already included in user).
      - guest_nice: Time spent running a niced guest (already included in nice).
    """

    user: int
    nice: int
    system: int
    idle: int
    iowait: int
    irq: int
    softirq: int
    steal: int
    guest: int = 0
    guest_nice: int = 0

    @property
    def accounting_total_ticks(self) -> int:
        """
        Total CPU interval ticks used as the denominator for utilization calculations.

        Note on Guest Time:
        Linux reports guest and guest_nice as already accounted for within user/nice.
        They are excluded from this denominator sum to prevent double-counting.
        """
        return (
            self.user
            + self.nice
            + self.system
            + self.idle
            + self.iowait
            + self.irq
            + self.softirq
            + self.steal
        )


@dataclass(frozen=True)
class CpuStatSnapshot:
    """
    Represents raw point-in-time CPU statistics extracted from /proc/stat.
    """

    total_cpu: CpuTimes
    cores: dict[int, CpuTimes]
    ctxt: int
    processes: int
    procs_running: int
    procs_blocked: int
    btime: int
    observed_at: datetime


@dataclass(frozen=True)
class CpuCoreUtilization:
    """
    Derived CPU utilization breakdown over a specific elapsed interval.

    All percentages are strictly marked as derived calculations from /proc/stat tick deltas.
    """

    core_id: int | None  # None indicates system-wide aggregate CPU
    total_utilization_pct: float
    user_pct: float
    system_pct: float
    nice_pct: float
    idle_pct: float
    iowait_pct: float
    irq_pct: float
    softirq_pct: float
    steal_pct: float
    elapsed_seconds: float

    @property
    def is_aggregate(self) -> bool:
        return self.core_id is None


@dataclass(frozen=True)
class CpuUtilization:
    """
    Container of derived CPU utilization metrics computed from two consecutive snapshots.
    """

    total: CpuCoreUtilization | None
    per_core: dict[int, CpuCoreUtilization]
    procs_running: int
    procs_blocked: int
    ctxt_rate: float | None
    forks_rate: float | None
    sample_interval_seconds: float
