import unittest
from datetime import datetime
from pathlib import Path

from app.core.event_bus import EventBus
from app.core.events import SystemEvent
from app.process.model import Process
from app.visualizers.activity_timeline import EventCardWidget


class TestProcessEvents(unittest.TestCase):

    def setUp(self):
        self.event_bus = EventBus()

    def test_process_events_delivery(self):
        """Verify process events publish and subscribe through EventBus."""
        received = []
        self.event_bus.subscribe("process.created", lambda e: received.append(e))
        self.event_bus.subscribe("process.removed", lambda e: received.append(e))
        self.event_bus.subscribe("process.state_changed", lambda e: received.append(e))

        e1 = SystemEvent("process.created", {"pid": 1234, "command": "sleep", "state": "S", "observed_at": datetime.now()})
        e2 = SystemEvent("process.state_changed", {"pid": 1234, "command": "sleep", "old_state": "S", "new_state": "R", "observed_at": datetime.now()})
        e3 = SystemEvent("process.removed", {"pid": 1234, "command": "sleep", "observed_at": datetime.now()})

        self.event_bus.publish(e1)
        self.event_bus.publish(e2)
        self.event_bus.publish(e3)

        self.assertEqual(len(received), 3)
        self.assertEqual(received[0].event_type, "process.created")
        self.assertEqual(received[1].event_type, "process.state_changed")
        self.assertEqual(received[2].event_type, "process.removed")

    def test_factual_timeline_card_language(self):
        """
        Verify that timeline event cards use strictly factual /proc observation language
        and do not claim unobserved syscalls (fork, clone, exit_group, wait4).
        """
        from PySide6.QtWidgets import QApplication
        import sys
        if not QApplication.instance():
            _app = QApplication(sys.argv)

        e = SystemEvent("process.created", {"pid": 5555, "command": "test_app", "state": "R", "observed_at": datetime.now()})
        card = EventCardWidget(e)

        # Target label check
        self.assertIn("PID 5555 observed in /proc", card.target_lbl.text())

        # Insight box check
        insight_text = card._get_educational_insight("process.created", e.data)
        self.assertIn("/proc Observation", insight_text)
        self.assertNotIn("fork()", insight_text)
        self.assertNotIn("clone()", insight_text)
        self.assertNotIn("exit_group()", insight_text)


if __name__ == "__main__":
    unittest.main()
