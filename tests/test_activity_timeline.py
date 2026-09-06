import sys
import unittest
from PySide6.QtWidgets import QApplication

from app.core.activity import ActivityTimeline
from app.core.events import SystemEvent
from app.visualizers.activity_timeline import ActivityTimelineWidget, EventCardWidget


class TestActivityTimeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_core_storage(self):
        timeline = ActivityTimeline(max_events=10)
        event1 = SystemEvent(event_type="file.created", data={"path": "/tmp/test1.txt"}, source="Filesystem observer", mechanism="inotify")
        event2 = SystemEvent(event_type="file.deleted", data={"path": "/tmp/test2.txt"}, source="Filesystem observer", mechanism="inotify")

        timeline.record(event1)
        timeline.record(event2)

        events = timeline.get_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], event1)
        self.assertEqual(events[1], event2)
        self.assertEqual(events[0].source, "Filesystem observer")
        self.assertEqual(events[0].mechanism, "inotify")

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
        e1 = SystemEvent(event_type="file.created", data={"path": "/tmp/test.txt"}, source="Filesystem observer", mechanism="inotify")
        e2 = SystemEvent(event_type="shell.session_created", data={"pid": 1234, "command": "bash"}, source="Shell session tracker", mechanism="/proc scan")
        e3 = SystemEvent(event_type="process.created", data={"pid": 5678, "command": "sleep"}, source="Linux /proc snapshot", mechanism="/proc/<pid>/stat")

        widget.add_event(e1)
        widget.add_event(e2)
        widget.add_event(e3)

        self.assertEqual(widget.event_count(), 3)

        # Filter by Filesystem (index 1)
        widget.filter_combo.setCurrentIndex(1)
        self.assertEqual(widget.visible_count(), 1)

        # Filter by Process (index 2)
        widget.filter_combo.setCurrentIndex(2)
        self.assertEqual(widget.visible_count(), 1)

        # Filter by Shell (index 3)
        widget.filter_combo.setCurrentIndex(3)
        self.assertEqual(widget.visible_count(), 1)

        # Clear filter (index 0)
        widget.filter_combo.setCurrentIndex(0)
        self.assertEqual(widget.visible_count(), 3)

    def test_widget_search_filtering(self):
        widget = ActivityTimelineWidget(max_events=10)
        e1 = SystemEvent(event_type="process.created", data={"pid": 1024, "command": "grep"}, source="Linux /proc snapshot")
        e2 = SystemEvent(event_type="file.created", data={"path": "/home/dev/LinuxLab/sample.py"}, source="Filesystem observer")

        widget.add_event(e1)
        widget.add_event(e2)

        # Search by PID
        widget.search_edit.setText("1024")
        self.assertEqual(widget.visible_count(), 1)

        # Search by keyword
        widget.search_edit.setText("sample.py")
        self.assertEqual(widget.visible_count(), 1)

        # Search by source
        widget.search_edit.setText("Filesystem")
        self.assertEqual(widget.visible_count(), 1)

        # Clear search
        widget.search_edit.setText("")
        self.assertEqual(widget.visible_count(), 2)

    def test_event_card_structure(self):
        e = SystemEvent(
            event_type="process.created",
            data={
                "pid": 4242,
                "ppid": 1000,
                "command": "python",
                "cmdline": "python app.py",
                "state": "R",
                "tty": "/dev/pts/2",
                "cwd": "/home/dev",
            },
            source="Linux /proc snapshot",
            mechanism="/proc/<pid>/stat",
        )
        card = EventCardWidget(e)

        self.assertIn("PID 4242", card.target_lbl.text())
        facts_summary = card._format_facts_summary(e.event_type, e.data)
        self.assertIn("PID: 4242", facts_summary)
        self.assertIn("PPID: 1000", facts_summary)
        self.assertIn("CMD: python", facts_summary)
        self.assertIn("STATE: R", facts_summary)
        self.assertIn("ARGS: python app.py", facts_summary)
        self.assertIn("TTY: /dev/pts/2", facts_summary)


if __name__ == "__main__":
    unittest.main()
