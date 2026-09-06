import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileModifiedEvent, DirCreatedEvent

from app.core.activity import ActivityTimeline
from app.core.event_bus import EventBus
from app.core.events import SystemEvent
from app.monitors.filesystem import LinuxLabFileHandler, FileSystemSignals
from app.process.model import Process
from app.process.registry import diff_process_snapshots
from app.process.session import TerminalSession
from app.process.session_manager import TerminalSessionManager


class TestLiveActivityTruth(unittest.TestCase):
    """
    Truth Contract & Hardening Test Suite for Live Linux Activity v2:
    - Live Activity = Observed Linux facts, not attempted command history.
    - Missing an unobserved event is acceptable; reporting without evidence is forbidden.
    - No synthetic events (e.g. command.missed) are ever fabricated.
    - Every event carries explicit provenance (source, mechanism, observed_at) and factual data.
    """

    def setUp(self):
        self.event_bus = EventBus()
        self.timeline = ActivityTimeline(max_events=100)
        self.recorded_events: list[SystemEvent] = []

        # Subscribe to all testable domains
        for domain in [
            "process.created",
            "process.removed",
            "process.state_changed",
            "process.cwd_changed",
            "file.created",
            "file.modified",
            "file.deleted",
            "file.moved",
            "file.permissions_changed",
            "directory.created",
            "directory.deleted",
            "shell.session_created",
            "shell.session_removed",
            "shell.cwd_changed",
            "memory.swap_usage_changed",
        ]:
            self.event_bus.subscribe(domain, self._on_event)

    def _on_event(self, event: SystemEvent):
        self.recorded_events.append(event)
        self.timeline.record(event)

    def test_event_has_source(self):
        """Every SystemEvent emitted must identify its observation source."""
        p = Process(
            pid=1000,
            ppid=1,
            pgid=1000,
            sid=1000,
            tpgid=1000,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="init",
            cmdline="init",
            cwd=Path("/"),
        )
        events = diff_process_snapshots({}, {1000: p})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source, "Linux /proc snapshot")
        self.assertIsNotNone(events[0].mechanism)

    def test_event_has_observed_at(self):
        """Every SystemEvent must carry a precise observed_at timestamp."""
        t_before = datetime.now()
        event = SystemEvent(
            event_type="test.event",
            data={"key": "val"},
            source="Test Observer",
        )
        t_after = datetime.now()

        self.assertIsInstance(event.observed_at, datetime)
        self.assertTrue(t_before <= event.observed_at <= t_after)
        self.assertIn(".", event.formatted_time)

    def test_unobserved_action_produces_no_event(self):
        """
        CRITICAL TRUTH TEST:
        If a short-lived command finishes between sampling ticks and leaves no
        filesystem or process trace, the system must produce NO events.
        It must never invent 'command.missed' or fake history.
        """
        prev_proc_snapshot: dict[int, Process] = {}
        curr_proc_snapshot: dict[int, Process] = {}

        events = diff_process_snapshots(prev_proc_snapshot, curr_proc_snapshot)
        for e in events:
            self.event_bus.publish(e)

        self.assertEqual(len(events), 0)
        self.assertEqual(len(self.recorded_events), 0)
        self.assertEqual(len(self.timeline.get_events()), 0)

    def test_timeline_does_not_invent_events(self):
        """Ensure timeline only records what is explicitly published by observers."""
        self.assertEqual(len(self.timeline.get_events()), 0)
        # Even if an unobserved command was attempted, timeline remains empty
        events_in_timeline = self.timeline.get_events()
        for evt in events_in_timeline:
            self.assertNotIn("missed", evt.event_type)
            self.assertNotIn("not_captured", evt.event_type)

    def test_process_event_contains_only_observed_facts(self):
        """
        Process events must contain exact kernel attributes from /proc without hallucinated fields.
        """
        p_sleep = Process(
            pid=27142,
            ppid=10228,
            pgid=27142,
            sid=10228,
            tpgid=10228,
            uid=1000,
            gid=1000,
            tty="/dev/pts/1",
            state="S",
            command="sleep",
            cmdline="sleep 600",
            cwd=Path("/home/dev/LinuxLab"),
        )
        events = diff_process_snapshots({}, {27142: p_sleep})
        self.assertEqual(len(events), 1)
        evt = events[0]

        expected_keys = {"pid", "ppid", "command", "cmdline", "state", "tty", "cwd", "pgid", "sid", "tpgid", "observed_at", "process"}
        self.assertTrue(expected_keys.issubset(set(evt.data.keys())))
        self.assertEqual(evt.data["pid"], 27142)
        self.assertEqual(evt.data["ppid"], 10228)
        self.assertEqual(evt.data["command"], "sleep")
        self.assertEqual(evt.data["state"], "S")
        self.assertEqual(evt.data["tty"], "/dev/pts/1")
        self.assertEqual(evt.data["cwd"], "/home/dev/LinuxLab")

    def test_filesystem_event_contains_actual_metadata(self):
        """
        Filesystem events must contain actual file path, directory flag, and octal modes.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "test.txt"
            test_file.write_text("sample")

            signals = FileSystemSignals()
            stat_cache = {}
            st = os.lstat(test_file)
            stat_cache[str(test_file)] = (st.st_mode, st.st_uid, st.st_gid)

            signals.event_detected.connect(self.event_bus.publish)
            handler = LinuxLabFileHandler(signals, stat_cache)

            # Change mode from 0644 to 0600
            os.chmod(test_file, 0o600)
            handler.on_modified(FileModifiedEvent(str(test_file)))

            self.assertEqual(len(self.recorded_events), 1)
            evt = self.recorded_events[0]
            self.assertEqual(evt.event_type, "file.permissions_changed")
            self.assertEqual(evt.source, "Filesystem observer")
            self.assertEqual(evt.mechanism, "stat()")
            self.assertEqual(evt.data["path"], str(test_file))
            self.assertEqual(evt.data["new_mode"], "0600")

    def test_filesystem_observed_when_process_unpolled(self):
        """
        If a command like `chmod 600 file` or `touch file` is too quick for /proc polling,
        the filesystem observer still reliably records the fact.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_file = Path(tmp_dir) / "data.txt"
            test_file.write_text("initial")

            signals = FileSystemSignals()
            stat_cache = {}
            st = os.lstat(test_file)
            stat_cache[str(test_file)] = (st.st_mode, st.st_uid, st.st_gid)

            signals.event_detected.connect(self.event_bus.publish)
            handler = LinuxLabFileHandler(signals, stat_cache)

            os.chmod(test_file, 0o600)
            handler.on_modified(FileModifiedEvent(str(test_file)))

            self.assertEqual(len(self.recorded_events), 1)
            evt = self.recorded_events[0]
            self.assertEqual(evt.event_type, "file.permissions_changed")
            self.assertEqual(evt.source, "Filesystem observer")
            self.assertEqual(evt.mechanism, "stat()")

    def test_process_lifecycle_factual_stream(self):
        """
        Verify real observed process creation, state transition, and removal.
        """
        p_sleep = Process(
            pid=27142,
            ppid=10228,
            pgid=27142,
            sid=10228,
            tpgid=10228,
            uid=1000,
            gid=1000,
            tty="/dev/pts/1",
            state="S",
            command="sleep",
            cmdline="sleep 600",
            cwd=Path("/home/dev/LinuxLab"),
        )

        # 1. Process observed
        events1 = diff_process_snapshots({}, {27142: p_sleep})
        for e in events1:
            self.event_bus.publish(e)

        self.assertEqual(len(self.recorded_events), 1)
        self.assertEqual(self.recorded_events[0].event_type, "process.created")
        self.assertEqual(self.recorded_events[0].source, "Linux /proc snapshot")
        self.assertEqual(self.recorded_events[0].data["pid"], 27142)
        self.assertEqual(self.recorded_events[0].data["command"], "sleep")

        # 2. State transition (S -> R)
        p_sleep_running = Process(
            pid=27142,
            ppid=10228,
            pgid=27142,
            sid=10228,
            tpgid=10228,
            uid=1000,
            gid=1000,
            tty="/dev/pts/1",
            state="R",
            command="sleep",
            cmdline="sleep 600",
            cwd=Path("/home/dev/LinuxLab"),
        )
        events2 = diff_process_snapshots({27142: p_sleep}, {27142: p_sleep_running})
        for e in events2:
            self.event_bus.publish(e)

        self.assertEqual(len(self.recorded_events), 2)
        self.assertEqual(self.recorded_events[1].event_type, "process.state_changed")
        self.assertEqual(self.recorded_events[1].data["old_state"], "S")
        self.assertEqual(self.recorded_events[1].data["new_state"], "R")

        # 3. Process exits
        events3 = diff_process_snapshots({27142: p_sleep_running}, {})
        for e in events3:
            self.event_bus.publish(e)

        self.assertEqual(len(self.recorded_events), 3)
        self.assertEqual(self.recorded_events[2].event_type, "process.removed")
        self.assertEqual(self.recorded_events[2].data["pid"], 27142)

    def test_composite_action_stream(self):
        """
        When a command performs filesystem changes and is also captured by /proc:
        Stream contains both process and filesystem events in true chronological order.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_dir = Path(tmp_dir) / "test_dir"
            signals = FileSystemSignals()
            stat_cache = {}
            signals.event_detected.connect(self.event_bus.publish)
            fs_handler = LinuxLabFileHandler(signals, stat_cache)

            # 1. Process observed
            proc = Process(
                pid=30100,
                ppid=10228,
                pgid=30100,
                sid=10228,
                tpgid=10228,
                uid=1000,
                gid=1000,
                tty="/dev/pts/1",
                state="R",
                command="mkdir",
                cmdline="mkdir test_dir",
                cwd=Path(tmp_dir),
            )
            for e in diff_process_snapshots({}, {30100: proc}):
                self.event_bus.publish(e)

            # 2. Directory created
            target_dir.mkdir()
            fs_handler.on_created(DirCreatedEvent(str(target_dir)))

            # 3. Process exits
            for e in diff_process_snapshots({30100: proc}, {}):
                self.event_bus.publish(e)

            self.assertEqual(len(self.recorded_events), 3)
            self.assertEqual(self.recorded_events[0].event_type, "process.created")
            self.assertEqual(self.recorded_events[1].event_type, "directory.created")
            self.assertEqual(self.recorded_events[2].event_type, "process.removed")

    def test_memory_swap_event_truth_and_no_cause_speculation(self):
        """
        Memory events must only assert factual metric observations (e.g. swap usage change).
        They must never speculate on root cause (e.g. 'Linux swapped out pages').
        """
        from app.memory.model import MemorySnapshot
        from app.memory.registry import diff_memory_snapshots

        prev = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=4000,
            mem_available_kb=10000,
            buffers_kb=1000,
            cached_kb=3000,
            swap_total_kb=4000,
            swap_free_kb=3000,
        )
        curr = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=3800,
            mem_available_kb=9800,
            buffers_kb=1000,
            cached_kb=3200,
            swap_total_kb=4000,
            swap_free_kb=2000,
        )

        events = diff_memory_snapshots(prev, curr)
        for e in events:
            self.event_bus.publish(e)

        self.assertEqual(len(self.recorded_events), 1)
        evt = self.recorded_events[0]
        self.assertEqual(evt.event_type, "memory.swap_usage_changed")
        self.assertEqual(evt.source, "Linux /proc/meminfo snapshot")
        self.assertEqual(evt.mechanism, "/proc/meminfo")
        self.assertEqual(evt.data["old_swap_used_kb"], 1000)
        self.assertEqual(evt.data["new_swap_used_kb"], 2000)
        self.assertEqual(evt.data["delta_swap_used_kb"], 1000)

        # Timeline card text formatting check
        from app.visualizers.activity_timeline import EventCardWidget
        card = EventCardWidget(evt)
        # Ensure target text is factual observation, not speculative cause
        self.assertIn("Swap reported usage changed", card.target_lbl.text())
        self.assertIn("1,000 kB ➔ 2,000 kB", card.target_lbl.text())
        self.assertNotIn("Linux swapped out", card.target_lbl.text())


if __name__ == "__main__":
    unittest.main()
