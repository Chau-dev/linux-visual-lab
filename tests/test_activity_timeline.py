import sys
import unittest
from PySide6.QtWidgets import QApplication

from app.core.activity import ActivityTimeline
from app.core.events import SystemEvent
from app.visualizers.activity_timeline import ActivityTimelineWidget


class TestActivityTimeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_core_storage(self):
        timeline = ActivityTimeline(max_events=10)
        event1 = SystemEvent(event_type="file.created", data={"path": "/tmp/test1.txt"})
        event2 = SystemEvent(event_type="file.deleted", data={"path": "/tmp/test2.txt"})

        timeline.record(event1)
        timeline.record(event2)

        events = timeline.get_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], event1)
        self.assertEqual(events[1], event2)

    def test_capacity(self):
        timeline = ActivityTimeline(max_events=3)
        for i in range(5):
            timeline.record(SystemEvent(event_type="test", data={"index": i}))

        events = timeline.get_events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].data["index"], 2)
        self.assertEqual(events[2].data["index"], 4)

    def test_widget_add_and_filter(self):
        widget = ActivityTimelineWidget(max_events=10)
        e1 = SystemEvent(event_type="file.created", data={"path": "/tmp/test.txt"})
        e2 = SystemEvent(event_type="shell.session_created", data={"pid": 1234})

        widget.add_event(e1)
        widget.add_event(e2)

        self.assertEqual(widget.event_count(), 2)

        # Filter by file
        widget.filter_combo.setCurrentText("📁 Filesystem Only")
        self.assertEqual(widget.visible_count(), 1)
        self.assertEqual(widget.event_count(), 2)

        # Clear filter
        widget.filter_combo.setCurrentText("🔍 All Events")
        self.assertEqual(widget.visible_count(), 2)
        self.assertEqual(widget.event_count(), 2)


if __name__ == "__main__":
    unittest.main()
