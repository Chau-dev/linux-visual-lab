import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from app.process.focused_session import FocusedSession
from app.process.focused_cwd import FocusedSessionCwd


class TestFocusedSessionCwd(unittest.TestCase):

    def test_get_without_focused_session(self):
        focused = FocusedSession()
        cwd_reader = FocusedSessionCwd(focused)
        self.assertIsNone(cwd_reader.get())

    def test_get_with_focused_session(self):
        focused = FocusedSession()
        focused.set_pid(1234)
        cwd_reader = FocusedSessionCwd(focused)

        with patch("app.process.focused_cwd.get_process_cwd", return_value=Path("/tmp")):
            self.assertEqual(cwd_reader.get(), Path("/tmp"))


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        pid = int(sys.argv[1])
        focused = FocusedSession()
        focused.set_pid(pid)
        cwd_reader = FocusedSessionCwd(focused)
        print("Focused PID:", pid)
        print("Focused CWD:", cwd_reader.get())
    else:
        unittest.main()
