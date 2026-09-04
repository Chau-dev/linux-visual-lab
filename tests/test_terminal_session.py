import unittest
from pathlib import Path

from app.process.session import TerminalSession


class TestTerminalSession(unittest.TestCase):

    def test_session_creation_with_defaults(self):
        session = TerminalSession(
            pid=1234,
            command="bash",
        )
        self.assertEqual(session.pid, 1234)
        self.assertEqual(session.command, "bash")
        self.assertIsNone(session.ppid)
        self.assertIsNone(session.cwd)
        self.assertIsNone(session.tty)

    def test_session_creation_full(self):
        session = TerminalSession(
            pid=5678,
            ppid=1000,
            command="zsh",
            tty="/dev/pts/2",
            cwd=Path("/home/dev/LinuxLab"),
        )
        self.assertEqual(session.pid, 5678)
        self.assertEqual(session.ppid, 1000)
        self.assertEqual(session.command, "zsh")
        self.assertEqual(session.tty, "/dev/pts/2")
        self.assertEqual(session.cwd, Path("/home/dev/LinuxLab"))


if __name__ == "__main__":
    unittest.main()
