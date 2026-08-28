from app.core.event_bus import EventBus
from app.core.events import SystemEvent


def on_file_created(event):
    print(
        "Received:",
        event.event_type,
        event.data
    )


bus = EventBus()

bus.subscribe(
    "file.created",
    on_file_created
)

event = SystemEvent(
    event_type="file.created",
    data={
        "path": "/home/dev/LinuxLab/test.txt"
    }
)

bus.publish(event)
