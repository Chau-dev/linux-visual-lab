from __future__ import annotations

import sys
import unittest
from datetime import datetime
from PySide6.QtWidgets import QApplication

from app.cpu.model import (
    CpuCoreUtilization,
    CpuStatSnapshot,
    CpuTimes,
    CpuUtilization,
)
from app.visualizers.cpu_view import CpuLabWidget


class TestCpuVisualizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_cpu_lab_widget_initialization_and_update(self):
        widget = CpuLabWidget()
        self.assertIsNotNone(widget)

        # Baseline snapshot
        snap = CpuStatSnapshot(
            total_cpu=CpuTimes(1000, 50, 500, 8000, 100, 20, 30, 0, 0, 0),
            cores={
                0: CpuTimes(500, 25, 250, 4000, 50, 10, 15, 0, 0, 0),
                1: CpuTimes(500, 25, 250, 4000, 50, 10, 15, 0, 0, 0),
            },
            ctxt=500000,
            processes=12000,
            procs_running=3,
            procs_blocked=0,
            btime=1700000000,
            observed_at=datetime.now(),
        )

        agg_util = CpuCoreUtilization(
            core_id=None,
            total_utilization_pct=35.0,
            user_pct=20.0,
            system_pct=10.0,
            nice_pct=1.0,
            idle_pct=65.0,
            iowait_pct=2.0,
            irq_pct=1.0,
            softirq_pct=1.0,
            steal_pct=0.0,
            elapsed_seconds=0.5,
        )
        core0_util = CpuCoreUtilization(
            core_id=0,
            total_utilization_pct=40.0,
            user_pct=25.0,
            system_pct=10.0,
            nice_pct=1.0,
            idle_pct=60.0,
            iowait_pct=2.0,
            irq_pct=1.0,
            softirq_pct=1.0,
            steal_pct=0.0,
            elapsed_seconds=0.5,
        )
        core1_util = CpuCoreUtilization(
            core_id=1,
            total_utilization_pct=30.0,
            user_pct=15.0,
            system_pct=10.0,
            nice_pct=1.0,
            idle_pct=70.0,
            iowait_pct=2.0,
            irq_pct=1.0,
            softirq_pct=1.0,
            steal_pct=0.0,
            elapsed_seconds=0.5,
        )

        util = CpuUtilization(
            total=agg_util,
            per_core={0: core0_util, 1: core1_util},
            procs_running=3,
            procs_blocked=0,
            ctxt_rate=12500.0,
            forks_rate=8.0,
            sample_interval_seconds=0.5,
        )

        # Apply update
        widget.update_cpu(util, snap)

        self.assertEqual(widget.overall_pct_lbl.text(), "35.0%")
        self.assertEqual(widget.card_user.value_lbl.text(), "20.0%")
        self.assertEqual(widget.card_system.value_lbl.text(), "10.0%")
        self.assertEqual(widget.card_idle.value_lbl.text(), "65.0%")
        self.assertEqual(widget.card_running.value_lbl.text(), "3")
        self.assertEqual(widget.card_blocked.value_lbl.text(), "0")
        self.assertIn("12,500 / s", widget.card_ctxt_rate.value_lbl.text())
        self.assertIn("8 / s", widget.card_forks_rate.value_lbl.text())

        # Check core widgets
        self.assertIn(0, widget.core_widgets)
        self.assertIn(1, widget.core_widgets)
        self.assertEqual(widget.core_widgets[0].pct_lbl.text(), "40.0%")
        self.assertEqual(widget.core_widgets[1].pct_lbl.text(), "30.0%")

        # Check raw table rows
        self.assertEqual(widget.raw_table.rowCount(), 3)  # total + 2 cores
