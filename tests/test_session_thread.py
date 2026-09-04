import unittest
import sys

from PySide6.QtWidgets import QApplication

from app.process.session_thread import TerminalSessionThread


class TestTerminalSessionThread(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_thread_initialization_and_stop(self):
        session_thread = TerminalSessionThread(interval_ms=500)
        self.assertIsNotNone(session_thread.thread)
        self.assertIsNotNone(session_thread.worker)

        # Test start
        session_thread.start()
        self.assertTrue(session_thread.thread.isRunning())

        # Test stop
        session_thread.stop()
        self.assertFalse(session_thread.thread.isRunning())


if __name__ == "__main__":
    unittest.main()
