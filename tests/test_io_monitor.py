from __future__ import annotations

import os
import sys
import time
import unittest
from PySide6.QtWidgets import QApplication

from app.io.monitor import IoMonitor, IoWorker
from app.io.registry import ProcessIoState


class TestIoMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_io_worker_poll_once(self):
        current_pid = os.getpid()
        worker = IoWorker(target_pid=current_pid, interval_ms=100)
        received_states = []

        def on_update(state: ProcessIoState):
            received_states.append(state)

        worker.io_updated.connect(on_update)
        worker.poll_once()

        self.assertEqual(len(received_states), 1)
        state = received_states[0]
        self.assertEqual(state.pid, current_pid)
        self.assertGreaterEqual(len(state.descriptors), 1)

    def test_io_monitor_thread_lifecycle(self):
        current_pid = os.getpid()
        monitor = IoMonitor(target_pid=current_pid, interval_ms=50)
        received_states = []

        def on_update(state: ProcessIoState):
            received_states.append(state)

        monitor.io_updated.connect(on_update)
        monitor.start()

        start_time = time.time()
        while len(received_states) < 1 and time.time() - start_time < 2.0:
            QApplication.processEvents()
            time.sleep(0.02)

        monitor.stop()
        self.assertGreaterEqual(len(received_states), 1)

    def test_io_monitor_target_switch(self):
        monitor = IoMonitor(target_pid=1, interval_ms=100)
        self.assertEqual(monitor.target_pid, 1)

        monitor.set_target_pid(os.getpid())
        self.assertEqual(monitor.target_pid, os.getpid())


if __name__ == "__main__":
    unittest.main()
