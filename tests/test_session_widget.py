import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.process.session import TerminalSession
from app.visualizers.session_panel import (
    TerminalSessionWidget,
)


class TestTerminalSessionWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_update_sessions(self):
        widget = TerminalSessionWidget()
        sessions = [
            TerminalSession(
                pid=8798,
                ppid=8786,
                command="bash",
                tty="/dev/pts/0",
                cwd=Path("/home/dev/LinuxLab/project"),
            ),
            TerminalSession(
                pid=19691,
                ppid=8786,
                command="bash",
                tty="/dev/pts/1",
                cwd=Path("/home/dev/LinuxLab/permissions_demo"),
            ),
        ]
        widget.update_sessions(sessions)
        self.assertEqual(widget.count(), 2)

    def test_update_sessions_dict(self):
        widget = TerminalSessionWidget()
        sessions = {
            8798: TerminalSession(
                pid=8798,
                command="bash",
            ),
            19691: TerminalSession(
                pid=19691,
                command="zsh",
            ),
        }
        widget.update_sessions(sessions)
        self.assertEqual(widget.count(), 2)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    sessions = [
        TerminalSession(
            pid=8798,
            ppid=8786,
            command="bash",
            tty="/dev/pts/0",
            cwd=Path("/home/dev/LinuxLab/project"),
        ),
        TerminalSession(
            pid=19691,
            ppid=8786,
            command="bash",
            tty="/dev/pts/1",
            cwd=Path("/home/dev/LinuxLab/permissions_demo"),
        ),
    ]
    widget = TerminalSessionWidget()
    widget.update_sessions(sessions)
    widget.resize(500, 300)
    widget.show()
    sys.exit(app.exec())
