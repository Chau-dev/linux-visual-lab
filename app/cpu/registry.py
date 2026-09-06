from __future__ import annotations

import threading
from app.cpu.model import (
    CpuCoreUtilization,
    CpuStatSnapshot,
    CpuTimes,
    CpuUtilization,
)


def _compute_core_utilization(
    prev_times: CpuTimes,
    curr_times: CpuTimes,
    core_id: int | None,
    elapsed_seconds: float,
) -> CpuCoreUtilization | None:
    """
    Derive CPU utilization breakdown for a single core or aggregate total.

    Granular Counter-Reset Policy:
    If any cumulative counter decreases (curr < prev), this interval is invalid.
    Returns None to suppress negative or invalid metrics without corrupting other cores.
    """
    if (
        curr_times.user < prev_times.user
        or curr_times.nice < prev_times.nice
        or curr_times.system < prev_times.system
        or curr_times.idle < prev_times.idle
        or curr_times.iowait < prev_times.iowait
        or curr_times.irq < prev_times.irq
        or curr_times.softirq < prev_times.softirq
        or curr_times.steal < prev_times.steal
    ):
        return None

    d_user = curr_times.user - prev_times.user
    d_nice = curr_times.nice - prev_times.nice
    d_system = curr_times.system - prev_times.system
    d_idle = curr_times.idle - prev_times.idle
    d_iowait = curr_times.iowait - prev_times.iowait
    d_irq = curr_times.irq - prev_times.irq
    d_softirq = curr_times.softirq - prev_times.softirq
    d_steal = curr_times.steal - prev_times.steal

    # Total interval denominator (excludes guest time to prevent double counting)
    d_total = (
        d_user
        + d_nice
        + d_system
        + d_idle
        + d_iowait
        + d_irq
        + d_softirq
        + d_steal
    )

    if d_total <= 0:
        return None

    # Busy time = Total - (Idle + I/O Wait)
    d_busy = d_total - (d_idle + d_iowait)
    total_util_pct = max(0.0, min(100.0, (d_busy / d_total) * 100.0))

    return CpuCoreUtilization(
        core_id=core_id,
        total_utilization_pct=total_util_pct,
        user_pct=(d_user / d_total) * 100.0,
        system_pct=(d_system / d_total) * 100.0,
        nice_pct=(d_nice / d_total) * 100.0,
        idle_pct=(d_idle / d_total) * 100.0,
        iowait_pct=(d_iowait / d_total) * 100.0,
        irq_pct=(d_irq / d_total) * 100.0,
        softirq_pct=(d_softirq / d_total) * 100.0,
        steal_pct=(d_steal / d_total) * 100.0,
        elapsed_seconds=elapsed_seconds,
    )


class CpuRegistry:
    """
    Thread-safe registry maintaining historical CPU snapshots and computing derived utilization deltas.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._previous_snapshot: CpuStatSnapshot | None = None

    def update(self, snapshot: CpuStatSnapshot) -> CpuUtilization | None:
        """
        Ingest a new CPU snapshot and compute derived utilization deltas against the previous snapshot.

        Returns:
            CpuUtilization object if a valid baseline exists and elapsed time > 0, otherwise None.
        """
        with self._lock:
            prev = self._previous_snapshot
            self._previous_snapshot = snapshot

            if prev is None:
                return None

            dt = (snapshot.observed_at - prev.observed_at).total_seconds()
            if dt <= 0:
                return None

            # 1. Compute aggregate system CPU utilization
            total_util = _compute_core_utilization(
                prev.total_cpu,
                snapshot.total_cpu,
                core_id=None,
                elapsed_seconds=dt,
            )

            # 2. Compute per-core utilizations independently
            per_core_utils: dict[int, CpuCoreUtilization] = {}
            for core_id, curr_core_times in snapshot.cores.items():
                if core_id in prev.cores:
                    core_util = _compute_core_utilization(
                        prev.cores[core_id],
                        curr_core_times,
                        core_id=core_id,
                        elapsed_seconds=dt,
                    )
                    if core_util is not None:
                        per_core_utils[core_id] = core_util

            # 3. Compute context switches rate
            ctxt_rate: float | None = None
            if snapshot.ctxt >= prev.ctxt:
                ctxt_rate = (snapshot.ctxt - prev.ctxt) / dt

            # 4. Compute process forks rate
            forks_rate: float | None = None
            if snapshot.processes >= prev.processes:
                forks_rate = (snapshot.processes - prev.processes) / dt

            return CpuUtilization(
                total=total_util,
                per_core=per_core_utils,
                procs_running=snapshot.procs_running,
                procs_blocked=snapshot.procs_blocked,
                ctxt_rate=ctxt_rate,
                forks_rate=forks_rate,
                sample_interval_seconds=dt,
            )

    def reset(self):
        """Clear historical baseline."""
        with self._lock:
            self._previous_snapshot = None
