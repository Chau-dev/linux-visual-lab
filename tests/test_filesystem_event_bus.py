import time

from app.core.event_bus import EventBus
from app.monitors.filesystem import FileSystemMonitor
from app.core.activity import ActivityTimeline

LAB_PATH = "/home/dev/LinuxLab"


def on_event(event):

    print(
        "EVENT:",
        event.event_type
    )

    print(
        "DATA:",
        event.data
    )


bus = EventBus()
timeline = ActivityTimeline()

bus.subscribe(
    "file.created",
    timeline.record
)

bus.subscribe(
    "file.modified",
    timeline.record
)

bus.subscribe(
    "file.deleted",
    timeline.record
)

bus.subscribe(
    "file.moved",
    timeline.record
)

bus.subscribe(
    "directory.created",
    timeline.record
)

bus.subscribe(
    "directory.deleted",
    timeline.record
)
bus.subscribe(
    "file.created",
    on_event
)

bus.subscribe(
    "file.modified",
    on_event
)

bus.subscribe(
    "file.deleted",
    on_event
)

bus.subscribe(
    "directory.created",
    on_event
)

bus.subscribe(
    "directory.deleted",
    on_event
)

bus.subscribe(
    "file.moved",
    on_event
)


monitor = FileSystemMonitor(
    LAB_PATH,
    bus
)

monitor.start()

print(
    "Watching:",
    LAB_PATH
)

print(
    "Create/change/delete files "
    "inside LinuxLab."
)

print(
    "Press Ctrl+C to stop."
)

try:

    while True:

        time.sleep(1)

except KeyboardInterrupt:

    print(
        "\nStopping..."
    )

    monitor.stop()

    print(
        "\n--- ACTIVITY TIMELINE ---"
    )

    for event in timeline.get_events():

        print(
            event.timestamp.strftime(
                "%H:%M:%S"
            ),
            event.event_type,
            event.data
        )
