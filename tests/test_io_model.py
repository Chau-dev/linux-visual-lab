import os
import unittest
from app.io.model import (
    FdType,
    FileDescriptor,
    PipeEndpoint,
    ProcessIoSnapshot,
    DerivedProcessIoRates,
    DiskDeviceStat,
    KernelFileLock,
)
from app.io.discovery import decode_open_flags, parse_target_type


class TestIoModel(unittest.TestCase):

    def test_fd_type_derivation(self):
        # Regular file
        t_type, ino, tag = parse_target_type("/home/dev/file.txt")
        self.assertEqual(t_type, FdType.REGULAR_FILE)
        self.assertIsNone(ino)

        # Pipe with inode
        t_type, ino, tag = parse_target_type("pipe:[78123]")
        self.assertEqual(t_type, FdType.PIPE)
        self.assertEqual(ino, 78123)

        # Socket with inode
        t_type, ino, tag = parse_target_type("socket:[42819]")
        self.assertEqual(t_type, FdType.SOCKET)
        self.assertEqual(ino, 42819)

        # Anon inode
        t_type, ino, tag = parse_target_type("anon_inode:[eventfd]")
        self.assertEqual(t_type, FdType.ANON_INODE)
        self.assertEqual(tag, "eventfd")

        # PTY / TTY
        t_type, ino, tag = parse_target_type("/dev/pts/1")
        self.assertEqual(t_type, FdType.PTY_TTY)

        # Device
        t_type, ino, tag = parse_target_type("/dev/null")
        self.assertEqual(t_type, FdType.DEVICE)

        # Deleted
        t_type, ino, tag = parse_target_type("/tmp/test.tmp (deleted)")
        self.assertEqual(t_type, FdType.DELETED)

    def test_open_flags_decoding(self):
        # Read-only
        mode, flags = decode_open_flags(0)
        self.assertEqual(mode, "O_RDONLY")
        self.assertEqual(flags, ())

        # Write-only + O_APPEND (0o2000)
        mode, flags = decode_open_flags(1 | 0o2000)
        self.assertEqual(mode, "O_WRONLY")
        self.assertIn("O_APPEND", flags)

        # Read-Write + O_CLOEXEC (0o2000000) + O_NONBLOCK (0o4000)
        mode, flags = decode_open_flags(2 | 0o2000000 | 0o4000)
        self.assertEqual(mode, "O_RDWR")
        self.assertIn("O_CLOEXEC", flags)
        self.assertIn("O_NONBLOCK", flags)

    def test_file_descriptor_properties(self):
        fd0 = FileDescriptor(
            fd=0,
            target="/dev/pts/1",
            fd_type=FdType.PTY_TTY,
            is_standard_stream=True,
            standard_stream_name="stdin",
            access_mode="O_RDONLY",
        )
        self.assertEqual(fd0.display_role, "stdin (0)")
        self.assertFalse(fd0.is_pipe)
        self.assertFalse(fd0.is_socket)
        self.assertEqual(fd0.pipe_endpoint_role, "Read end")

        fd1 = FileDescriptor(
            fd=1,
            target="pipe:[12345]",
            fd_type=FdType.PIPE,
            target_inode=12345,
            access_mode="O_WRONLY",
        )
        self.assertTrue(fd1.is_pipe)
        self.assertEqual(fd1.pipe_endpoint_role, "Write end")

    def test_process_io_snapshot(self):
        snap = ProcessIoSnapshot(
            rchar=1000,
            wchar=500,
            syscr=10,
            syscw=5,
            read_bytes=4096,
            write_bytes=8192,
            cancelled_write_bytes=0,
            observed_at_timestamp=100.0,
        )
        self.assertEqual(snap.rchar, 1000)
        self.assertEqual(snap.read_bytes, 4096)


if __name__ == "__main__":
    unittest.main()
