import sys
import unittest
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.process.monitor import ProcessWorker, ProcessMonitor
from app.process.model import Process


class TestProcessMonitor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_worker_refresh(self):
        """Verify ProcessWorker single sampling cycle."""
        worker = ProcessWorker(interval_ms=100)
        emitted_snapshots = []
        worker.processes_updated.connect(lambda s: emitted_snapshots.append(s))

        worker.refresh()
        self.assertTrue(len(emitted_snapshots) > 0)
        snapshot = emitted_snapshots[0]
        self.assertIsInstance(snapshot, dict)
        self.assertTrue(len(snapshot) > 0)

    def test_monitor_lifecycle(self):
        """Verify ProcessMonitor thread start and clean shutdown."""
        monitor = ProcessMonitor(interval_ms=100)
        self.assertFalse(monitor.is_running())

        emitted_updates = []
        monitor.processes_updated.connect(lambda s: emitted_updates.append(s))

        monitor.start()
        self.assertTrue(monitor.is_running())

        # Wait briefly for worker to emit initial sample
        start_time = time.time()
        while len(emitted_updates) == 0 and time.time() - start_time < 2.0:
            QApplication.processEvents()
            time.sleep(0.05)

        self.assertTrue(len(emitted_updates) > 0)
        self.assertTrue(monitor.registry.count() > 0)

        monitor.stop()
        self.assertFalse(monitor.is_running())


if __name__ == "__main__":
    unittest.main()
