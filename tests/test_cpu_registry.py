from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from app.cpu.model import CpuStatSnapshot, CpuTimes
from app.cpu.registry import CpuRegistry


class TestCpuRegistry(unittest.TestCase):
    def test_first_update_returns_none(self):
        registry = CpuRegistry()
        snap1 = CpuStatSnapshot(
            total_cpu=CpuTimes(100, 0, 50, 850, 0, 0, 0, 0),
            cores={0: CpuTimes(100, 0, 50, 850, 0, 0, 0, 0)},
            ctxt=1000,
            processes=50,
            procs_running=1,
            procs_blocked=0,
            btime=1700000000,
            observed_at=datetime.now(),
        )
        self.assertIsNone(registry.update(snap1))

    def test_second_update_computes_exact_utilization(self):
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        snap1 = CpuStatSnapshot(
            total_cpu=CpuTimes(user=100, nice=0, system=50, idle=850, iowait=0, irq=0, softirq=0, steal=0),
            cores={
                0: CpuTimes(user=50, nice=0, system=25, idle=425, iowait=0, irq=0, softirq=0, steal=0),
                1: CpuTimes(user=50, nice=0, system=25, idle=425, iowait=0, irq=0, softirq=0, steal=0),
            },
            ctxt=1000,
            processes=50,
            procs_running=2,
            procs_blocked=0,
            btime=1700000000,
            observed_at=t0,
        )
        registry.update(snap1)

        # After 1 second: user increases by 20, system by 10, idle by 70 -> Δtotal = 100
        snap2 = CpuStatSnapshot(
            total_cpu=CpuTimes(user=120, nice=0, system=60, idle=920, iowait=0, irq=0, softirq=0, steal=0),
            cores={
                0: CpuTimes(user=60, nice=0, system=30, idle=460, iowait=0, irq=0, softirq=0, steal=0),
                1: CpuTimes(user=60, nice=0, system=30, idle=460, iowait=0, irq=0, softirq=0, steal=0),
            },
            ctxt=1500,
            processes=55,
            procs_running=2,
            procs_blocked=0,
            btime=1700000000,
            observed_at=t1,
        )
        util = registry.update(snap2)
        self.assertIsNotNone(util)
        self.assertIsNotNone(util.total)
        # Total util: (100 - 70) / 100 * 100 = 30.0%
        self.assertAlmostEqual(util.total.total_utilization_pct, 30.0, places=1)
        self.assertAlmostEqual(util.total.user_pct, 20.0, places=1)
        self.assertAlmostEqual(util.total.system_pct, 10.0, places=1)
        self.assertAlmostEqual(util.total.idle_pct, 70.0, places=1)
        self.assertEqual(util.sample_interval_seconds, 1.0)

        # Rates: (1500 - 1000) / 1.0 = 500 / s
        self.assertAlmostEqual(util.ctxt_rate, 500.0, places=1)
        # Forks: (55 - 50) / 1.0 = 5 / s
        self.assertAlmostEqual(util.forks_rate, 5.0, places=1)

        # Per core checks
        self.assertIn(0, util.per_core)
        self.assertIn(1, util.per_core)
        self.assertAlmostEqual(util.per_core[0].total_utilization_pct, 30.0, places=1)

    def test_granular_counter_reset_handling(self):
        """Verify that a counter decrease on one core invalidates only that core, not unaffected cores."""
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        snap1 = CpuStatSnapshot(
            total_cpu=CpuTimes(user=100, nice=0, system=50, idle=850, iowait=0, irq=0, softirq=0, steal=0),
            cores={
                0: CpuTimes(user=50, nice=0, system=25, idle=425, iowait=0, irq=0, softirq=0, steal=0),
                1: CpuTimes(user=50, nice=0, system=25, idle=425, iowait=0, irq=0, softirq=0, steal=0),
            },
            ctxt=1000,
            processes=50,
            procs_running=1,
            procs_blocked=0,
            btime=1700000000,
            observed_at=t0,
        )
        registry.update(snap1)

        # Core 1 has a counter reset (user decreases from 50 to 10), but Core 0 is valid and aggregate is valid
        snap2 = CpuStatSnapshot(
            total_cpu=CpuTimes(user=120, nice=0, system=60, idle=920, iowait=0, irq=0, softirq=0, steal=0),
            cores={
                0: CpuTimes(user=60, nice=0, system=30, idle=460, iowait=0, irq=0, softirq=0, steal=0),
                1: CpuTimes(user=10, nice=0, system=25, idle=425, iowait=0, irq=0, softirq=0, steal=0),  # Reset
            },
            ctxt=1100,
            processes=52,
            procs_running=1,
            procs_blocked=0,
            btime=1700000000,
            observed_at=t1,
        )
        util = registry.update(snap2)
        self.assertIsNotNone(util)
        self.assertIsNotNone(util.total)
        self.assertIn(0, util.per_core)
        # Core 1 should be suppressed due to counter decrease
        self.assertNotIn(1, util.per_core)

    def test_invalid_elapsed_time_returns_none(self):
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        snap1 = CpuStatSnapshot(
            total_cpu=CpuTimes(100, 0, 50, 850, 0, 0, 0, 0),
            cores={},
            ctxt=1000,
            processes=50,
            procs_running=1,
            procs_blocked=0,
            btime=1700000000,
            observed_at=t0,
        )
        registry.update(snap1)
        # Same timestamp (dt = 0)
        self.assertIsNone(registry.update(snap1))
