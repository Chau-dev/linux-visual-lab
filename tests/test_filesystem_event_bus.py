import time
import unittest

from app.core.event_bus import EventBus
from app.monitors.filesystem import FileSystemMonitor
from app.core.activity import ActivityTimeline

LAB_PATH = "/home/dev/LinuxLab"


class TestFilesystemEventBusIntegration(unittest.TestCase):

    def test_event_bus_and_activity_recording(self):
        bus = EventBus()
        timeline = ActivityTimeline()

        bus.subscribe("file.created", timeline.record)
        bus.subscribe("file.modified", timeline.record)
        bus.subscribe("file.deleted", timeline.record)

        from app.core.events import SystemEvent

        bus.publish(SystemEvent(event_type="file.created", data={"path": "/tmp/a.txt"}))
        self.assertEqual(len(timeline.get_events()), 1)


if __name__ == "__main__":
    def on_event(event):
        print("EVENT:", event.event_type)
        print("DATA:", event.data)

    bus = EventBus()
    timeline = ActivityTimeline()

    for event_type in ["file.created", "file.modified", "file.deleted", "file.moved", "directory.created", "directory.deleted"]:
        bus.subscribe(event_type, timeline.record)
        bus.subscribe(event_type, on_event)

    monitor = FileSystemMonitor(LAB_PATH, bus)
    monitor.start()

    print("Watching:", LAB_PATH)
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        monitor.stop()
