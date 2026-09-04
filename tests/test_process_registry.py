import unittest
from datetime import datetime
from pathlib import Path

from app.process.model import Process
from app.process.registry import ProcessRegistry, diff_process_snapshots


class TestProcessRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = ProcessRegistry()
        self.p1 = Process(
            pid=100,
            ppid=1,
            pgid=100,
            sid=100,
            tpgid=100,
            uid=1000,
            gid=1000,
            tty="/dev/pts/0",
            state="S",
            command="bash",
            cmdline="bash",
            cwd=Path("/home/dev"),
        )
        self.p2 = Process(
            pid=200,
            ppid=100,
            pgid=100,
            sid=100,
            tpgid=100,
            uid=1000,
            gid=1000,
            tty="/dev/pts/0",
            state="S",
            command="sleep",
            cmdline="sleep 600",
            cwd=Path("/home/dev"),
        )

    def test_registry_storage(self):
        """Verify thread-safe ProcessRegistry operations."""
        self.assertEqual(self.registry.count(), 0)
        self.registry.set_snapshot({100: self.p1, 200: self.p2})
        self.assertEqual(self.registry.count(), 2)
        self.assertTrue(self.registry.contains(100))
        self.assertTrue(self.registry.contains(200))
        self.assertFalse(self.registry.contains(300))
        self.assertEqual(self.registry.get(100), self.p1)

        snapshot = self.registry.get_snapshot()
        self.assertEqual(len(snapshot), 2)
        self.registry.clear()
        self.assertEqual(self.registry.count(), 0)

    def test_diff_process_created(self):
        """Verify process.created event when new PID is observed."""
        previous = {100: self.p1}
        current = {100: self.p1, 200: self.p2}
        now = datetime.now()

        events = diff_process_snapshots(previous, current, observed_at=now)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "process.created")
        self.assertEqual(events[0].data["pid"], 200)
        self.assertEqual(events[0].data["ppid"], 100)
        self.assertEqual(events[0].data["command"], "sleep")
        self.assertEqual(events[0].data["observed_at"], now)

    def test_diff_process_removed(self):
        """Verify process.removed event when PID disappears."""
        previous = {100: self.p1, 200: self.p2}
        current = {100: self.p1}
        now = datetime.now()

        events = diff_process_snapshots(previous, current, observed_at=now)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "process.removed")
        self.assertEqual(events[0].data["pid"], 200)
        self.assertEqual(events[0].data["command"], "sleep")
        self.assertEqual(events[0].data["observed_at"], now)

    def test_diff_process_state_changed(self):
        """Verify process.state_changed event on state transition."""
        p2_running = Process(
            pid=200,
            ppid=100,
            pgid=100,
            sid=100,
            tpgid=100,
            uid=1000,
            gid=1000,
            tty="/dev/pts/0",
            state="R",
            command="sleep",
            cmdline="sleep 600",
            cwd=Path("/home/dev"),
        )
        previous = {100: self.p1, 200: self.p2}
        current = {100: self.p1, 200: p2_running}
        now = datetime.now()

        events = diff_process_snapshots(previous, current, observed_at=now)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "process.state_changed")
        self.assertEqual(events[0].data["pid"], 200)
        self.assertEqual(events[0].data["old_state"], "S")
        self.assertEqual(events[0].data["new_state"], "R")

    def test_diff_process_cwd_changed(self):
        """Verify process.cwd_changed event when process directory changes."""
        p1_moved = Process(
            pid=100,
            ppid=1,
            pgid=100,
            sid=100,
            tpgid=100,
            uid=1000,
            gid=1000,
            tty="/dev/pts/0",
            state="S",
            command="bash",
            cmdline="bash",
            cwd=Path("/tmp"),
        )
        previous = {100: self.p1}
        current = {100: p1_moved}
        now = datetime.now()

        events = diff_process_snapshots(previous, current, observed_at=now)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "process.cwd_changed")
        self.assertEqual(events[0].data["pid"], 100)
        self.assertEqual(events[0].data["old_cwd"], "/home/dev")
        self.assertEqual(events[0].data["new_cwd"], "/tmp")

    def test_diff_identical_snapshots(self):
        """Verify no events emitted when snapshots are identical."""
        snapshot = {100: self.p1, 200: self.p2}
        events = diff_process_snapshots(snapshot, snapshot)
        self.assertEqual(len(events), 0)


if __name__ == "__main__":
    unittest.main()
