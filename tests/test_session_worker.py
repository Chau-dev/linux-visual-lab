import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.core.event_bus import EventBus
from app.process.session_worker import TerminalSessionWorker


def on_event(event):

    print(
        "EVENT:",
        event.event_type
    )

    print(
        "DATA:",
        event.data
    )


app = QApplication(
    sys.argv
)

bus = EventBus()

bus.subscribe(
    "shell.session_created",
    on_event
)

bus.subscribe(
    "shell.session_removed",
    on_event
)

bus.subscribe(
    "shell.cwd_changed",
    on_event
)


worker = TerminalSessionWorker(
    bus,
    interval_ms=500
)

worker.start()


def stop():
    worker.stop()
    app.quit()


QTimer.singleShot(
    30000,
    stop
)


sys.exit(
    app.exec()
)
