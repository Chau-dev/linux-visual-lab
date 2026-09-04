import os
import unittest
import tempfile
import shutil
from pathlib import Path

from app.process.discovery import (
    read_process_info,
    discover_all_processes,
    get_process_tty,
    get_process_ppid,
    decode_tty_nr,
    get_process_stdin_target,
)
from app.process.model import Process


class TestProcessDiscovery(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_proc_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_decode_tty_nr_mappings(self):
        """Verify Linux tty_nr device number decoding to canonical /dev paths."""
        # 0 or negative -> No controlling terminal
        self.assertIsNone(decode_tty_nr(0))
        self.assertIsNone(decode_tty_nr(-1))

        # Unix98 PTY slaves (major 136)
        self.assertEqual(decode_tty_nr(os.makedev(136, 0)), "/dev/pts/0")
        self.assertEqual(decode_tty_nr(os.makedev(136, 1)), "/dev/pts/1")
        self.assertEqual(decode_tty_nr(os.makedev(136, 5)), "/dev/pts/5")

        # Virtual consoles & serial ports (major 4)
        self.assertEqual(decode_tty_nr(os.makedev(4, 0)), "/dev/tty0")
        self.assertEqual(decode_tty_nr(os.makedev(4, 1)), "/dev/tty1")
        self.assertEqual(decode_tty_nr(os.makedev(4, 64)), "/dev/ttyS0")

        # TTY driver special devices (major 5)
        self.assertEqual(decode_tty_nr(os.makedev(5, 0)), "/dev/tty")
        self.assertEqual(decode_tty_nr(os.makedev(5, 1)), "/dev/console")
        self.assertEqual(decode_tty_nr(os.makedev(5, 2)), "/dev/ptmx")

    def test_read_process_info_live_process(self):
        """Verify real process state extraction from live /proc for the test runner."""
        current_pid = os.getpid()
        proc = read_process_info(current_pid)

        self.assertIsNotNone(proc)
        self.assertEqual(proc.pid, current_pid)
        self.assertIsInstance(proc.ppid, int)
        self.assertIsInstance(proc.pgid, int)
        self.assertIsInstance(proc.sid, int)
        self.assertIsInstance(proc.tpgid, int)
        self.assertIsInstance(proc.uid, int)
        self.assertIsInstance(proc.gid, int)
        self.assertIsInstance(proc.tty_nr, int)
        self.assertIn(proc.state, {"R", "S", "D", "Z", "T", "t", "X", "I"})
        self.assertTrue(len(proc.command) > 0)
        self.assertIsNotNone(proc.cwd)
        self.assertTrue(proc.cwd.exists())

    def test_read_process_info_invalid_pid(self):
        """Verify None returned for non-existent PID."""
        proc = read_process_info(99999999)
        self.assertIsNone(proc)

    def test_discover_all_processes_live(self):
        """Verify discovering all live Linux processes."""
        processes = discover_all_processes()
        self.assertIsInstance(processes, dict)
        self.assertIn(os.getpid(), processes)

    def test_synthetic_proc_parsing(self):
        """
        Verify exact parsing of synthetic /proc directory entries,
        testing the crucial Linux distinction between controlling terminal (tty_nr)
        and standard input target (/proc/<pid>/fd/0).
        """
        fake_pid = 21375
        pid_dir = self.temp_dir / str(fake_pid)
        pid_dir.mkdir(parents=True)

        # /proc/21375/stat
        # PID (comm with space) state ppid pgid sid tty_nr tpgid ...
        # tty_nr = 34816 (which decodes to /dev/pts/0)
        stat_content = "21375 (my worker process) S 21155 21375 21155 34816 21155 4194304 123 0 0 0 10 20"
        (pid_dir / "stat").write_text(stat_content)

        # /proc/21375/status
        status_content = (
            "Name:\tmy worker\n"
            "State:\tS (sleeping)\n"
            "Tgid:\t21375\n"
            "Pid:\t21375\n"
            "PPid:\t21155\n"
            "Uid:\t1001\t1001\t1001\t1001\n"
            "Gid:\t1002\t1002\t1002\t1002\n"
        )
        (pid_dir / "status").write_text(status_content)

        # /proc/21375/cmdline
        (pid_dir / "cmdline").write_bytes(b"/usr/bin/worker\x00--port\x008080\x00")

        # /proc/21375/cwd
        (pid_dir / "cwd").symlink_to(Path.cwd())

        # /proc/21375/fd/0 -> points to /dev/pts/3 (e.g. redirected or different fd)
        fd_dir = pid_dir / "fd"
        fd_dir.mkdir()
        (fd_dir / "0").symlink_to("/dev/pts/3")

        proc = read_process_info(fake_pid, proc_root=self.temp_dir)
        self.assertIsNotNone(proc)
        self.assertEqual(proc.pid, 21375)
        self.assertEqual(proc.command, "my worker process")
        self.assertEqual(proc.state, "S")
        self.assertEqual(proc.ppid, 21155)
        self.assertEqual(proc.pgid, 21375)
        self.assertEqual(proc.sid, 21155)
        self.assertEqual(proc.tpgid, 21155)
        self.assertEqual(proc.uid, 1001)
        self.assertEqual(proc.gid, 1002)
        self.assertEqual(proc.cmdline, "/usr/bin/worker --port 8080")
        # Controlling terminal from stat tty_nr (34816 -> /dev/pts/0)
        self.assertEqual(proc.tty_nr, 34816)
        self.assertEqual(proc.tty, "/dev/pts/0")
        # Standard input from fd/0 (/dev/pts/3)
        self.assertEqual(proc.stdin_target, "/dev/pts/3")
        self.assertEqual(proc.cwd, Path.cwd().resolve())

        # Test derived properties
        self.assertTrue(proc.is_process_group_leader)
        self.assertFalse(proc.is_session_leader)
        self.assertFalse(proc.is_foreground)


if __name__ == "__main__":
    unittest.main()

