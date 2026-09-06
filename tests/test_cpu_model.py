from __future__ import annotations

import unittest
from datetime import datetime

from app.cpu.model import (
    CpuCoreUtilization,
    CpuStatSnapshot,
    CpuTimes,
    CpuUtilization,
)


class TestCpuModel(unittest.TestCase):
    def test_cpu_times_accounting_total_ticks(self):
        times = CpuTimes(
            user=100,
            nice=10,
            system=50,
            idle=800,
            iowait=20,
            irq=5,
            softirq=10,
            steal=5,
            guest=30,       # Already included in user
            guest_nice=5,   # Already included in nice
        )
        # Denominator must exclude guest and guest_nice
        expected_total = 100 + 10 + 50 + 800 + 20 + 5 + 10 + 5
        self.assertEqual(times.accounting_total_ticks, expected_total)
        self.assertEqual(times.accounting_total_ticks, 1000)

    def test_cpu_core_utilization_properties(self):
        core_util = CpuCoreUtilization(
            core_id=0,
            total_utilization_pct=25.0,
            user_pct=10.0,
            system_pct=5.0,
            nice_pct=1.0,
            idle_pct=75.0,
            iowait_pct=2.0,
            irq_pct=0.5,
            softirq_pct=1.0,
            steal_pct=0.5,
            elapsed_seconds=0.5,
        )
        self.assertFalse(core_util.is_aggregate)
        self.assertEqual(core_util.core_id, 0)
        self.assertEqual(core_util.total_utilization_pct, 25.0)

        agg_util = CpuCoreUtilization(
            core_id=None,
            total_utilization_pct=30.0,
            user_pct=15.0,
            system_pct=10.0,
            nice_pct=0.0,
            idle_pct=70.0,
            iowait_pct=0.0,
            irq_pct=1.0,
            softirq_pct=1.0,
            steal_pct=0.0,
            elapsed_seconds=0.5,
        )
        self.assertTrue(agg_util.is_aggregate)
        self.assertIsNone(agg_util.core_id)

    def test_cpu_utilization_container(self):
        agg_util = CpuCoreUtilization(
            core_id=None,
            total_utilization_pct=20.0,
            user_pct=10.0,
            system_pct=5.0,
            nice_pct=0.0,
            idle_pct=80.0,
            iowait_pct=0.0,
            irq_pct=1.0,
            softirq_pct=1.0,
            steal_pct=0.0,
            elapsed_seconds=1.0,
        )
        core0_util = CpuCoreUtilization(
            core_id=0,
            total_utilization_pct=20.0,
            user_pct=10.0,
            system_pct=5.0,
            nice_pct=0.0,
            idle_pct=80.0,
            iowait_pct=0.0,
            irq_pct=1.0,
            softirq_pct=1.0,
            steal_pct=0.0,
            elapsed_seconds=1.0,
        )
        container = CpuUtilization(
            total=agg_util,
            per_core={0: core0_util},
            procs_running=2,
            procs_blocked=0,
            ctxt_rate=15000.0,
            forks_rate=10.5,
            sample_interval_seconds=1.0,
        )
        self.assertEqual(container.procs_running, 2)
        self.assertEqual(container.procs_blocked, 0)
        self.assertEqual(container.ctxt_rate, 15000.0)
        self.assertEqual(container.forks_rate, 10.5)
        self.assertEqual(container.sample_interval_seconds, 1.0)
        self.assertEqual(len(container.per_core), 1)
