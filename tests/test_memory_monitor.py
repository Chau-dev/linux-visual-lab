from __future__ import annotations

import sys
import time
import unittest
from PySide6.QtWidgets import QApplication

from app.memory.monitor import MemoryMonitor, MemoryWorker
from app.memory.model import MemorySnapshot, SystemLoadSnapshot


class TestMemoryMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_memory_worker_poll_once(self):
        worker = MemoryWorker(interval_ms=100)
        received_mem = []
        received_load = []
        received_events = []

        def on_update(mem, load):
            received_mem.append(mem)
            received_load.append(load)

        def on_event(ev):
            received_events.append(ev)

        worker.memory_updated.connect(on_update)
        worker.event_detected.connect(on_event)

        # Trigger poll_once directly
        worker.poll_once()

        self.assertEqual(len(received_mem), 1)
        self.assertIsInstance(received_mem[0], MemorySnapshot)
        if received_load[0] is not None:
            self.assertIsInstance(received_load[0], SystemLoadSnapshot)

    def test_memory_monitor_thread_lifecycle(self):
        monitor = MemoryMonitor(interval_ms=50)
        received_mem = []

        def on_update(mem, load):
            received_mem.append(mem)

        monitor.memory_updated.connect(on_update)
        monitor.start()

        # Wait briefly for worker timer to fire
        start_time = time.time()
        while len(received_mem) < 1 and time.time() - start_time < 2.0:
            QApplication.processEvents()
            time.sleep(0.02)

        monitor.stop()

        self.assertGreaterEqual(len(received_mem), 1)
        self.assertIsInstance(received_mem[0], MemorySnapshot)


if __name__ == "__main__":
    unittest.main()
