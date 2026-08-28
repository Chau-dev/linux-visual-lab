import sys

from PySide6.QtWidgets import QApplication

from app.core.events import SystemEvent
from app.visualizers.activity_timeline import (
    ActivityTimelineWidget,
)


app = QApplication(
    sys.argv
)

widget = ActivityTimelineWidget()

widget.add_event(
    SystemEvent(
        event_type="file.created",
        data={
            "path":
                "/home/dev/LinuxLab/test.txt"
        }
    )
)

widget.add_event(
    SystemEvent(
        event_type="file.modified",
        data={
            "path":
                "/home/dev/LinuxLab/test.txt"
        }
    )
)

widget.add_event(
    SystemEvent(
        event_type="file.moved",
        data={
            "old_path":
                "/home/dev/LinuxLab/test.txt",
            "new_path":
                "/home/dev/LinuxLab/final.txt",
        }
    )
)

widget.show()

sys.exit(
    app.exec()
)
