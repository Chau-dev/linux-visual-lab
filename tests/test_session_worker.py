import sys
import unittest

from PySide6.QtWidgets import QApplication

from app.process.session_worker import TerminalSessionWorker


class TestTerminalSessionWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_worker_init_and_refresh(self):
        worker = TerminalSessionWorker(interval_ms=500)
        self.assertIsNotNone(worker.manager)
        # Running refresh directly
        worker._running = True
        worker.refresh()
        worker._running = False


if __name__ == "__main__":
    from PySide6.QtCore import QTimer

    def on_event(event):
        print("EVENT:", event.event_type, event.data)

    app = QApplication(sys.argv)
    worker = TerminalSessionWorker(interval_ms=500)
    worker.event_detected.connect(on_event)
    worker.start()

    def stop():
        worker.stop()
        app.quit()

    QTimer.singleShot(3000, stop)
    sys.exit(app.exec())
