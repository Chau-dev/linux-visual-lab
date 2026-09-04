import unittest

from app.core.event_bus import EventBus
from app.core.events import SystemEvent


class TestEventBus(unittest.TestCase):

    def test_publish_and_subscribe(self):
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe("file.created", handler)

        event1 = SystemEvent(event_type="file.created", data={"path": "/tmp/a.txt"})
        event2 = SystemEvent(event_type="file.deleted", data={"path": "/tmp/b.txt"})

        bus.publish(event1)
        bus.publish(event2)

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].data["path"], "/tmp/a.txt")

    def test_multiple_subscribers(self):
        bus = EventBus()
        calls = []

        bus.subscribe("custom.event", lambda e: calls.append("handler1"))
        bus.subscribe("custom.event", lambda e: calls.append("handler2"))

        bus.publish(SystemEvent(event_type="custom.event"))
        self.assertEqual(calls, ["handler1", "handler2"])


if __name__ == "__main__":
    unittest.main()
