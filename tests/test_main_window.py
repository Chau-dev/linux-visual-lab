import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.main import MainWindow
from app.process.session import TerminalSession


class TestMainWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_handle_sessions_updated_dict(self):
        window = MainWindow()

        # Simulate dictionary snapshot from TerminalSessionWorker
        dict_snapshot = {
            1234: TerminalSession(
                pid=1234,
                command="bash",
                tty="/dev/pts/0",
                cwd=Path("/home/dev/LinuxLab"),
            ),
            5678: TerminalSession(
                pid=5678,
                command="zsh",
                tty="/dev/pts/1",
                cwd=Path("/tmp"),
            ),
        }

        # Should not raise AttributeError: 'int' object has no attribute 'pid'
        window.handle_sessions_updated(dict_snapshot)
        self.assertEqual(len(window.session_snapshot), 2)
        self.assertEqual(window.session_widget.count(), 2)

        # Simulate list snapshot
        list_snapshot = list(dict_snapshot.values())
        window.handle_sessions_updated(list_snapshot)
        self.assertEqual(len(window.session_snapshot), 2)
        self.assertEqual(window.session_widget.count(), 2)

        # Cleanup
        window.close()


if __name__ == "__main__":
    unittest.main()
