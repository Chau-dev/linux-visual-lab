import os
import unittest
from pathlib import Path

from app.process.discovery import find_shell_processes, get_process_tty, get_process_ppid
from app.process.session import TerminalSession


class TestSessionDiscovery(unittest.TestCase):

    def test_find_shell_processes_returns_list(self):
        shells = find_shell_processes()
        self.assertIsInstance(shells, list)

        for s in shells:
            self.assertIsInstance(s, TerminalSession)
            self.assertIsInstance(s.pid, int)
            self.assertIsInstance(s.command, str)
            if s.ppid is not None:
                self.assertIsInstance(s.ppid, int)
            if s.cwd is not None:
                self.assertIsInstance(s.cwd, Path)

    def test_get_process_ppid_current_process(self):
        current_pid = os.getpid()
        ppid = get_process_ppid(current_pid)
        self.assertIsNotNone(ppid)
        self.assertEqual(ppid, os.getppid())

    def test_get_process_tty_invalid_pid(self):
        tty = get_process_tty(9999999)
        self.assertIsNone(tty)


if __name__ == "__main__":
    unittest.main()
