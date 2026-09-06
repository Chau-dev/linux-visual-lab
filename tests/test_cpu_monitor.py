from __future__ import annotations

import sys
import time
import unittest
from PySide6.QtWidgets import QApplication

from app.cpu.model import CpuStatSnapshot
from app.cpu.monitor import CpuMonitor, CpuWorker


class TestCpuMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_cpu_worker_poll_once(self):
        worker = CpuWorker(interval_ms=100)
        received_snapshots = []
        received_utils = []

        def on_update(util, snap):
            received_utils.append(util)
            received_snapshots.append(snap)

        worker.cpu_updated.connect(on_update)

        # First poll establishes baseline (util is None)
        worker.poll_once()
        self.assertEqual(len(received_snapshots), 1)
        self.assertIsInstance(received_snapshots[0], CpuStatSnapshot)
        self.assertIsNone(received_utils[0])

        # Second poll calculates utilization
        worker.poll_once()
        self.assertEqual(len(received_snapshots), 2)
        # util might be None if dt is 0, or CpuUtilization if dt > 0

    def test_cpu_monitor_thread_lifecycle(self):
        monitor = CpuMonitor(interval_ms=50)
        received_snaps = []

        def on_update(util, snap):
            received_snaps.append(snap)

        monitor.cpu_updated.connect(on_update)
        monitor.start()

        start_time = time.time()
        while len(received_snaps) < 1 and time.time() - start_time < 2.0:
            QApplication.processEvents()
            time.sleep(0.02)

        monitor.stop()
        self.assertGreaterEqual(len(received_snaps), 1)
