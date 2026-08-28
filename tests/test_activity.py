from app.core.activity import ActivityTimeline
from app.core.events import SystemEvent


timeline = ActivityTimeline()


timeline.record(
    SystemEvent(
        event_type="file.created",
        data={
            "path": "/home/dev/LinuxLab/test.txt"
        }
    )
)


timeline.record(
    SystemEvent(
        event_type="file.deleted",
        data={
            "path": "/home/dev/LinuxLab/test.txt"
        }
    )
)


for event in timeline.get_events():

    print(
        event.event_type,
        event.data
    )
