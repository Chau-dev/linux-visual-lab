import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app.io.discovery import (
    read_process_fds,
    read_process_io,
    read_diskstats,
    read_kernel_locks,
    find_pipe_peer_endpoints,
    parse_fdinfo,
)
from app.io.model import FdType


class TestIoDiscovery(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_io_discovery_")
        self.proc_root = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_process_fds_synthetic(self):
        pid = 1234
        fd_dir = self.proc_root / str(pid) / "fd"
        fdinfo_dir = self.proc_root / str(pid) / "fdinfo"
        fd_dir.mkdir(parents=True)
        fdinfo_dir.mkdir(parents=True)

        # Create symlink fd 0 -> /dev/pts/1
        os.symlink("/dev/pts/1", fd_dir / "0")
        (fdinfo_dir / "0").write_text("pos:\t0\nflags:\t02\nmnt_id:\t15\n")

        # Create symlink fd 1 -> pipe:[78123]
        os.symlink("pipe:[78123]", fd_dir / "1")
        (fdinfo_dir / "1").write_text("pos:\t0\nflags:\t01\nmnt_id:\t15\n")

        # Create symlink fd 3 -> /home/dev/file.txt
        os.symlink("/home/dev/file.txt", fd_dir / "3")
        (fdinfo_dir / "3").write_text("pos:\t4096\nflags:\t02000000\nmnt_id:\t20\n")

        descriptors, err = read_process_fds(pid, self.proc_root)
        self.assertIsNone(err)
        self.assertIsNotNone(descriptors)
        self.assertEqual(len(descriptors), 3)

        # Check fd 0
        self.assertEqual(descriptors[0].fd, 0)
        self.assertEqual(descriptors[0].target, "/dev/pts/1")
        self.assertEqual(descriptors[0].fd_type, FdType.PTY_TTY)
        self.assertEqual(descriptors[0].access_mode, "O_RDWR")
        self.assertTrue(descriptors[0].is_standard_stream)
        self.assertEqual(descriptors[0].standard_stream_name, "stdin")

        # Check fd 1
        self.assertEqual(descriptors[1].fd, 1)
        self.assertEqual(descriptors[1].fd_type, FdType.PIPE)
        self.assertEqual(descriptors[1].target_inode, 78123)
        self.assertEqual(descriptors[1].access_mode, "O_WRONLY")
        self.assertEqual(descriptors[1].pipe_endpoint_role, "Write end")

        # Check fd 3
        self.assertEqual(descriptors[2].fd, 3)
        self.assertEqual(descriptors[2].fd_type, FdType.REGULAR_FILE)
        self.assertEqual(descriptors[2].pos, 4096)
        self.assertIn("O_CLOEXEC", descriptors[2].status_flags)

    def test_read_process_fds_nonexistent(self):
        descriptors, err = read_process_fds(999999, self.proc_root)
        self.assertIsNone(descriptors)
        self.assertEqual(err, "ESRCH")

    def test_find_pipe_peer_endpoints(self):
        # Process 100 has write end to pipe:[9999]
        p100_fd = self.proc_root / "100" / "fd"
        p100_info = self.proc_root / "100" / "fdinfo"
        p100_fd.mkdir(parents=True)
        p100_info.mkdir(parents=True)
        os.symlink("pipe:[9999]", p100_fd / "1")
        (p100_info / "1").write_text("pos:\t0\nflags:\t01\n")
        (self.proc_root / "100" / "comm").write_text("cat\n")

        # Process 200 has read end to pipe:[9999]
        p200_fd = self.proc_root / "200" / "fd"
        p200_info = self.proc_root / "200" / "fdinfo"
        p200_fd.mkdir(parents=True)
        p200_info.mkdir(parents=True)
        os.symlink("pipe:[9999]", p200_fd / "0")
        (p200_info / "0").write_text("pos:\t0\nflags:\t00\n")
        (self.proc_root / "200" / "comm").write_text("grep\n")

        # Search for peers of Process 100
        peers = find_pipe_peer_endpoints(
            pipe_inode=9999,
            exclude_pid=100,
            candidate_pids=[100, 200],
            proc_root=self.proc_root,
        )
        self.assertEqual(len(peers), 1)
        self.assertEqual(peers[0].pid, 200)
        self.assertEqual(peers[0].fd, 0)
        self.assertEqual(peers[0].access_mode, "O_RDONLY")
        self.assertEqual(peers[0].endpoint_role, "Read end")
        self.assertEqual(peers[0].process_command, "grep")

    def test_read_process_io(self):
        io_file = self.proc_root / "1234" / "io"
        io_file.parent.mkdir(parents=True)
        io_file.write_text(
            "rchar: 123456\n"
            "wchar: 654321\n"
            "syscr: 100\n"
            "syscw: 50\n"
            "read_bytes: 4096\n"
            "write_bytes: 8192\n"
            "cancelled_write_bytes: 0\n"
        )
        snap = read_process_io(1234, self.proc_root)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.rchar, 123456)
        self.assertEqual(snap.wchar, 654321)
        self.assertEqual(snap.syscr, 100)
        self.assertEqual(snap.syscw, 50)
        self.assertEqual(snap.read_bytes, 4096)
        self.assertEqual(snap.write_bytes, 8192)

    def test_read_diskstats(self):
        ds_file = self.proc_root / "diskstats"
        ds_file.write_text(
            "   8       0 sda 1000 50 8000 200 500 20 4000 100 0 150 300 0 0 0 0\n"
            "   8       1 sda1 500 25 4000 100 250 10 2000 50 0 75 150 0 0 0 0\n"
        )
        stats = read_diskstats(self.proc_root)
        self.assertEqual(len(stats), 2)
        self.assertEqual(stats[0].device_name, "sda")
        self.assertEqual(stats[0].reads_completed, 1000)
        self.assertEqual(stats[0].sectors_read, 8000)

    def test_read_kernel_locks(self):
        locks_file = self.proc_root / "locks"
        locks_file.write_text(
            "1: POSIX  ADVISORY  WRITE 1234 08:01:12345 0 EOF\n"
            "2: FLOCK  ADVISORY  READ  5678 08:02:67890 0 1024\n"
        )
        locks = read_kernel_locks(self.proc_root)
        self.assertEqual(len(locks), 2)
        self.assertEqual(locks[0].lock_num, 1)
        self.assertEqual(locks[0].lock_type, "POSIX")
        self.assertEqual(locks[0].mode, "WRITE")
        self.assertEqual(locks[0].pid, 1234)


if __name__ == "__main__":
    unittest.main()
