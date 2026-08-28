import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
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


LAB_PATH = "/home/dev/LinuxLab"


class LiveActivityWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Linux Visual Lab - Live Activity"
        )

        self.resize(
            700,
            600
        )

        # --------------------------------------------
        # Event Bus
        # --------------------------------------------

        self.event_bus = EventBus()

        # --------------------------------------------
        # Activity history
        # --------------------------------------------

        self.timeline = ActivityTimeline(
            max_events=100
        )

        # --------------------------------------------
        # GUI
        # --------------------------------------------

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "🔴 LIVE LINUX ACTIVITY"
        )

        title.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: bold;
                padding: 10px;
            }
            """
        )

        layout.addWidget(
            title
        )

        location = QLabel(
            f"Watching: {LAB_PATH}"
        )

        layout.addWidget(
            location
        )

        self.activity_widget = (
            ActivityTimelineWidget()
        )

        layout.addWidget(
            self.activity_widget
        )

        # --------------------------------------------
        # Event Bus subscriptions
        # --------------------------------------------

        event_types = [
            "file.created",
            "file.modified",
            "file.deleted",
            "file.moved",
            "directory.created",
            "directory.deleted",
        ]

        for event_type in event_types:

            self.event_bus.subscribe(
                event_type,
                self.handle_event
            )

        # --------------------------------------------
        # Filesystem monitor
        # --------------------------------------------

        self.monitor = FileSystemMonitor(
            LAB_PATH,
            self.event_bus
        )

        self.monitor.start()

    # --------------------------------------------
    # Event handler
    # --------------------------------------------

    def handle_event(
        self,
        event
    ):

        # Store event
        self.timeline.record(
            event
        )

        # Display event
        self.activity_widget.add_event(
            event
        )

    # --------------------------------------------
    # Cleanup
    # --------------------------------------------

    def closeEvent(
        self,
        event
    ):

        self.monitor.stop()

        event.accept()


def main():

    app = QApplication(
        sys.argv
    )

    window = LiveActivityWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":

    sys.exit(
        main()
    )
