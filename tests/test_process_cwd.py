import os
import sys
import unittest
from pathlib import Path

from app.process.cwd import get_process_cwd


class TestProcessCwd(unittest.TestCase):

    def test_get_current_process_cwd(self):
        pid = os.getpid()
        cwd = get_process_cwd(pid)
        self.assertIsNotNone(cwd)
        self.assertTrue(isinstance(cwd, Path))
        self.assertTrue(cwd.exists())

    def test_get_nonexistent_process_cwd(self):
        cwd = get_process_cwd(99999999)
        self.assertIsNone(cwd)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        pid = int(sys.argv[1])
        print("Python PID:", os.getpid())
        print("Target PID:", pid)
        cwd = get_process_cwd(pid)
        print("Target process CWD:", cwd)
    else:
        unittest.main()
