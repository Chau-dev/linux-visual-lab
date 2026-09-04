import sys
import unittest

from PySide6.QtWidgets import QApplication

from app.core.events import SystemEvent
from app.visualizers.activity_timeline import (
    ActivityTimelineWidget,
    EventCardWidget,
)


class TestActivityTimelineWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_add_event_and_insights(self):
        widget = ActivityTimelineWidget()

        # Add File Created Event
        widget.add_event(
            SystemEvent(
                event_type="file.created",
                data={"path": "/home/dev/LinuxLab/test.txt"},
            )
        )
        self.assertEqual(widget.count(), 1)

        # Add Shell CWD Event
        widget.add_event(
            SystemEvent(
                event_type="shell.cwd_changed",
                data={
                    "pid": 1234,
                    "old_path": "/home/dev/LinuxLab",
                    "new_path": "/home/dev/LinuxLab/docs",
                },
            )
        )
        self.assertEqual(widget.count(), 2)

        # Check newest card (Shell CWD)
        _, top_card = widget._all_events[0]
        self.assertIn("SHELL NAV", top_card.badge_lbl.text())
        self.assertIn("1234", str(top_card.system_event.data.get("pid")))

    def test_filtering_and_search(self):
        widget = ActivityTimelineWidget()

        widget.add_event(
            SystemEvent(
                event_type="file.created",
                data={"path": "/home/dev/LinuxLab/notes.txt"},
            )
        )
        widget.add_event(
            SystemEvent(
                event_type="shell.cwd_changed",
                data={"pid": 4321, "new_path": "/tmp"},
            )
        )

        self.assertEqual(widget.count(), 2)

        # Filter by Filesystem Only (Index 1)
        widget.filter_combo.setCurrentIndex(1)
        self.assertFalse(widget._all_events[1][0].isHidden())  # file.created visible
        self.assertTrue(widget._all_events[0][0].isHidden())   # shell.cwd hidden

        # Reset filter to All (Index 0) and search for 'notes'
        widget.filter_combo.setCurrentIndex(0)
        widget.search_edit.setText("notes")
        self.assertFalse(widget._all_events[1][0].isHidden())
        self.assertTrue(widget._all_events[0][0].isHidden())

    def test_clear_events(self):
        widget = ActivityTimelineWidget()
        widget.add_event(
            SystemEvent(
                event_type="file.created",
                data={"path": "/home/dev/LinuxLab/test.txt"},
            )
        )
        self.assertEqual(widget.count(), 1)
        widget.clear_events()
        self.assertEqual(widget.count(), 0)
        self.assertEqual(widget.list_widget.count(), 0)


if __name__ == "__main__":
    unittest.main()
