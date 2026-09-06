import unittest
from datetime import datetime

from app.io.model import (
    FdType,
    FileDescriptor,
    PipeEndpoint,
    ProcessIoSnapshot,
)
from app.io.registry import IoRegistry


class TestIoRegistry(unittest.TestCase):

    def test_fd_appearance_and_disappearance(self):
        registry = IoRegistry()
        pid = 1000

        fd0 = FileDescriptor(fd=0, target="/dev/pts/1", fd_type=FdType.PTY_TTY, access_mode="O_RDWR")
        fd1 = FileDescriptor(fd=1, target="/dev/pts/1", fd_type=FdType.PTY_TTY, access_mode="O_RDWR")

        # Initial snapshot with fd 0 and fd 1
        state, events = registry.update(
            pid=pid,
            descriptors=[fd0, fd1],
            error_reason=None,
            io_snapshot=None,
        )

        self.assertEqual(len(state.descriptors), 2)
        # 2 appeared events
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_type, "io.fd_appeared")
        self.assertEqual(events[0].data["fd"], 0)
        self.assertEqual(events[1].event_type, "io.fd_appeared")
        self.assertEqual(events[1].data["fd"], 1)

        # Second snapshot: fd 1 closed, fd 3 opened
        fd3 = FileDescriptor(fd=3, target="/home/dev/file.txt", fd_type=FdType.REGULAR_FILE, access_mode="O_RDONLY")
        state2, events2 = registry.update(
            pid=pid,
            descriptors=[fd0, fd3],
            error_reason=None,
            io_snapshot=None,
        )

        self.assertEqual(len(state2.descriptors), 2)
        # 1 appeared (fd 3) + 1 disappeared (fd 1)
        event_types = [e.event_type for e in events2]
        self.assertIn("io.fd_appeared", event_types)
        self.assertIn("io.fd_disappeared", event_types)

        appeared_fd = next(e for e in events2 if e.event_type == "io.fd_appeared")
        self.assertEqual(appeared_fd.data["fd"], 3)

        disappeared_fd = next(e for e in events2 if e.event_type == "io.fd_disappeared")
        self.assertEqual(disappeared_fd.data["fd"], 1)

    def test_shared_pipe_event_safeguard(self):
        registry = IoRegistry()
        pid = 1000

        fd0 = FileDescriptor(fd=0, target="/dev/pts/1", fd_type=FdType.PTY_TTY)
        fd1 = FileDescriptor(fd=1, target="pipe:[777]", fd_type=FdType.PIPE, target_inode=777, access_mode="O_WRONLY")

        # Case 1: Pipe has ONLY ONE endpoint accessible (peer not found)
        # Must NOT emit io.pipe_shared!
        single_ep = PipeEndpoint(inode=777, pid=1000, fd=1, access_mode="O_WRONLY", endpoint_role="Write end", process_command="cat")
        resolved_single = {777: [single_ep]}

        _, events = registry.update(
            pid=pid,
            descriptors=[fd0, fd1],
            error_reason=None,
            io_snapshot=None,
            resolved_pipes=resolved_single,
        )

        pipe_events = [e for e in events if e.event_type == "io.pipe_shared"]
        self.assertEqual(len(pipe_events), 0, "Must not emit io.pipe_shared when only one endpoint is observed")

        # Case 2: Peer endpoint is found! (2 endpoints observed)
        # Must emit io.pipe_shared!
        peer_ep = PipeEndpoint(inode=777, pid=2000, fd=0, access_mode="O_RDONLY", endpoint_role="Read end", process_command="grep")
        resolved_pair = {777: [single_ep, peer_ep]}

        _, events2 = registry.update(
            pid=pid,
            descriptors=[fd0, fd1],
            error_reason=None,
            io_snapshot=None,
            resolved_pipes=resolved_pair,
        )

        pipe_events2 = [e for e in events2 if e.event_type == "io.pipe_shared"]
        self.assertEqual(len(pipe_events2), 1, "Must emit io.pipe_shared when at least two endpoints are observed")
        self.assertEqual(pipe_events2[0].data["pipe_inode"], 777)
        self.assertEqual(pipe_events2[0].data["endpoints_count"], 2)

    def test_derived_rates_calculation(self):
        registry = IoRegistry()
        pid = 1000

        snap1 = ProcessIoSnapshot(
            rchar=1000,
            wchar=2000,
            syscr=10,
            syscw=20,
            read_bytes=4096,
            write_bytes=8192,
            cancelled_write_bytes=0,
            observed_at_timestamp=100.0,
        )

        state1, _ = registry.update(pid=pid, descriptors=[], error_reason=None, io_snapshot=snap1)
        self.assertIsNone(state1.derived_rates, "Initial snapshot should have no derived rate (needs baseline)")

        snap2 = ProcessIoSnapshot(
            rchar=2000,        # +1000 in 2.0s -> 500 B/s
            wchar=6000,        # +4000 in 2.0s -> 2000 B/s
            syscr=30,          # +20 in 2.0s -> 10 syscalls/s
            syscw=40,          # +20 in 2.0s -> 10 syscalls/s
            read_bytes=8192,   # +4096 in 2.0s -> 2048 B/s
            write_bytes=16384, # +8192 in 2.0s -> 4096 B/s
            cancelled_write_bytes=0,
            observed_at_timestamp=102.0,
        )

        state2, _ = registry.update(pid=pid, descriptors=[], error_reason=None, io_snapshot=snap2)
        self.assertIsNotNone(state2.derived_rates)
        self.assertAlmostEqual(state2.derived_rates.rchar_per_sec, 500.0)
        self.assertAlmostEqual(state2.derived_rates.wchar_per_sec, 2000.0)
        self.assertAlmostEqual(state2.derived_rates.syscr_per_sec, 10.0)
        self.assertAlmostEqual(state2.derived_rates.syscw_per_sec, 10.0)
        self.assertAlmostEqual(state2.derived_rates.read_bytes_per_sec, 2048.0)
        self.assertAlmostEqual(state2.derived_rates.write_bytes_per_sec, 4096.0)


if __name__ == "__main__":
    unittest.main()
