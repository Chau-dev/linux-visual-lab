import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.event_bus import EventBus
from app.process.session import TerminalSession
from app.process.session_manager import TerminalSessionManager


class TestTerminalSessionManager(unittest.TestCase):

    def test_session_lifecycle_events(self):
        bus = EventBus()
        events = []

        bus.subscribe("shell.session_created", lambda e: events.append(e))
        bus.subscribe("shell.session_removed", lambda e: events.append(e))
        bus.subscribe("shell.cwd_changed", lambda e: events.append(e))

        manager = TerminalSessionManager(bus)

        # 1. Initial discovery with one session
        session1 = TerminalSession(
            pid=1001,
            ppid=1000,
            command="bash",
            tty="/dev/pts/0",
            cwd=Path("/home/dev/LinuxLab"),
        )
        with patch("app.process.session_manager.find_shell_processes", return_value=[session1]):
            manager.refresh()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "shell.session_created")
        self.assertEqual(events[0].data["pid"], 1001)

        # 2. Working directory changes
        session1_moved = TerminalSession(
            pid=1001,
            ppid=1000,
            command="bash",
            tty="/dev/pts/0",
            cwd=Path("/home/dev/LinuxLab/subdir"),
        )
        with patch("app.process.session_manager.find_shell_processes", return_value=[session1_moved]):
            manager.refresh()

        self.assertEqual(len(events), 2)
        self.assertEqual(events[1].event_type, "shell.cwd_changed")
        self.assertEqual(events[1].data["old_path"], "/home/dev/LinuxLab")
        self.assertEqual(events[1].data["new_path"], "/home/dev/LinuxLab/subdir")

        # 3. Session terminated
        with patch("app.process.session_manager.find_shell_processes", return_value=[]):
            manager.refresh()

        self.assertEqual(len(events), 3)
        self.assertEqual(events[2].event_type, "shell.session_removed")
        self.assertEqual(events[2].data["pid"], 1001)
        self.assertEqual(len(manager.sessions()), 0)


if __name__ == "__main__":
    unittest.main()
