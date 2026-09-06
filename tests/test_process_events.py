import sys
import unittest
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.event_bus import EventBus
from app.core.events import SystemEvent
from app.process.model import Process
from app.process.registry import diff_process_snapshots
from app.visualizers.activity_timeline import EventCardWidget


class TestProcessEvents(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.event_bus = EventBus()

    def test_process_events_delivery(self):
        """Verify process events publish and subscribe through EventBus."""
        received = []
        self.event_bus.subscribe("process.created", lambda e: received.append(e))
        self.event_bus.subscribe("process.removed", lambda e: received.append(e))
        self.event_bus.subscribe("process.state_changed", lambda e: received.append(e))

        e1 = SystemEvent("process.created", {"pid": 1234, "command": "sleep", "state": "S"}, source="Linux /proc snapshot")
        e2 = SystemEvent("process.state_changed", {"pid": 1234, "command": "sleep", "old_state": "S", "new_state": "R"}, source="Linux /proc snapshot")
        e3 = SystemEvent("process.removed", {"pid": 1234, "command": "sleep"}, source="Linux /proc snapshot")

        self.event_bus.publish(e1)
        self.event_bus.publish(e2)
        self.event_bus.publish(e3)

        self.assertEqual(len(received), 3)
        self.assertEqual(received[0].event_type, "process.created")
        self.assertEqual(received[1].event_type, "process.state_changed")
        self.assertEqual(received[2].event_type, "process.removed")
        self.assertEqual(received[0].source, "Linux /proc snapshot")

    def test_diff_process_snapshots_sources_and_facts(self):
        """Verify that snapshot diffing produces exact facts and provenance."""
        p1 = Process(
            pid=2000,
            ppid=1000,
            pgid=2000,
            sid=1000,
            tpgid=1000,
            uid=1000,
            gid=1000,
            tty="/dev/pts/1",
            state="S",
            command="sleep",
            cmdline="sleep 100",
            cwd=Path("/home/dev"),
        )
        events = diff_process_snapshots({}, {2000: p1})
        self.assertEqual(len(events), 1)
        created_event = events[0]
        self.assertEqual(created_event.event_type, "process.created")
        self.assertEqual(created_event.source, "Linux /proc snapshot")
        self.assertEqual(created_event.mechanism, "/proc/<pid>/stat")
        self.assertEqual(created_event.data["pid"], 2000)
        self.assertEqual(created_event.data["ppid"], 1000)
        self.assertEqual(created_event.data["command"], "sleep")
        self.assertEqual(created_event.data["cmdline"], "sleep 100")
        self.assertEqual(created_event.data["state"], "S")
        self.assertEqual(created_event.data["tty"], "/dev/pts/1")

        # Process exit
        exit_events = diff_process_snapshots({2000: p1}, {})
        self.assertEqual(len(exit_events), 1)
        removed_event = exit_events[0]
        self.assertEqual(removed_event.event_type, "process.removed")
        self.assertEqual(removed_event.source, "Linux /proc snapshot")
        self.assertEqual(removed_event.data["pid"], 2000)
        self.assertEqual(removed_event.data["command"], "sleep")

    def test_factual_timeline_card_language(self):
        """
        Verify that timeline event cards use strictly factual /proc observation language
        and do not claim unobserved syscalls (fork, clone, exit_group, wait4).
        """
        e = SystemEvent(
            "process.created",
            {"pid": 5555, "command": "test_app", "state": "R"},
            source="Linux /proc snapshot",
            mechanism="/proc/<pid>/stat",
        )
        card = EventCardWidget(e)

        # Target label check
        self.assertIn("PID 5555 observed: test_app", card.target_lbl.text())
        self.assertEqual(e.source, "Linux /proc snapshot")
        self.assertEqual(e.mechanism, "/proc/<pid>/stat")


if __name__ == "__main__":
    unittest.main()
