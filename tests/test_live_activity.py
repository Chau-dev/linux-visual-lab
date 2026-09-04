import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.activity import ActivityTimeline
from app.core.event_bus import EventBus
from app.monitors.filesystem import FileSystemMonitor
from app.visualizers.activity_timeline import (
    ActivityTimelineWidget,
)

LAB_PATH = Path("/home/dev/LinuxLab")


class LiveActivityWindow(QWidget):

    def __init__(self):
        super().__init__()

        try:
            LAB_PATH.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


        self.setWindowTitle("Linux Visual Lab - Live Activity")
        self.resize(700, 600)

        self.event_bus = EventBus()
        self.timeline = ActivityTimeline(max_events=100)

        layout = QVBoxLayout(self)

        title = QLabel("🔴 LIVE LINUX ACTIVITY")
        title.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: bold;
                padding: 10px;
            }
            """
        )
        layout.addWidget(title)

        location = QLabel(f"Watching: {LAB_PATH}")
        layout.addWidget(location)

        self.activity_widget = ActivityTimelineWidget()
        layout.addWidget(self.activity_widget)

        event_types = [
            "file.created",
            "file.modified",
            "file.deleted",
            "file.moved",
            "directory.created",
            "directory.deleted",
        ]

        for event_type in event_types:
            self.event_bus.subscribe(event_type, self.handle_event)

        self.monitor = FileSystemMonitor(LAB_PATH, self.event_bus)
        self.monitor.start()

    def handle_event(self, event):
        self.timeline.record(event)
        self.activity_widget.add_event(event)

    def closeEvent(self, event):
        self.monitor.stop()
        event.accept()


class TestLiveActivityWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_window_init_and_close(self):
        window = LiveActivityWindow()
        self.assertIsNotNone(window.monitor)
        window.monitor.stop()


def main():
    app = QApplication(sys.argv)
    window = LiveActivityWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
