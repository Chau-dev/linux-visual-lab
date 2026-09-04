import unittest
from datetime import datetime

from app.core.activity import ActivityTimeline
from app.core.events import SystemEvent


class TestActivityTimeline(unittest.TestCase):

    def test_record_and_get_events(self):
        timeline = ActivityTimeline(max_events=10)
        event1 = SystemEvent(event_type="file.created", data={"path": "/tmp/test1.txt"})
        event2 = SystemEvent(event_type="file.deleted", data={"path": "/tmp/test2.txt"})

        timeline.record(event1)
        timeline.record(event2)

        events = timeline.get_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], event1)
        self.assertEqual(events[1], event2)

    def test_max_events_capacity(self):
        timeline = ActivityTimeline(max_events=3)
        for i in range(5):
            timeline.record(SystemEvent(event_type="test", data={"index": i}))

        events = timeline.get_events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].data["index"], 2)
        self.assertEqual(events[1].data["index"], 3)
        self.assertEqual(events[2].data["index"], 4)

    def test_clear_events(self):
        timeline = ActivityTimeline(max_events=10)
        timeline.record(SystemEvent(event_type="test"))
        self.assertEqual(len(timeline.get_events()), 1)
        timeline.clear()
        self.assertEqual(len(timeline.get_events()), 0)


if __name__ == "__main__":
    unittest.main()
