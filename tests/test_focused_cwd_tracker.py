import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.event_bus import EventBus
from app.process.focused_cwd_tracker import (
    FocusedCwdTracker,
)
from app.process.focused_session import (
    FocusedSession,
)


class TestFocusedCwdTracker(unittest.TestCase):

    def test_check_emits_event_on_cwd_change(self):
        bus = EventBus()
        events = []
        bus.subscribe("shell.focused_cwd_changed", lambda e: events.append(e))

        focused = FocusedSession()
        focused.set_pid(1234)
        tracker = FocusedCwdTracker(focused, bus)

        # Initial check establishes baseline
        with patch("app.process.focused_cwd_tracker.get_process_cwd", return_value=Path("/tmp")):
            tracker.check()

        self.assertEqual(len(events), 0)

        # Second check with changed CWD emits event
        with patch("app.process.focused_cwd_tracker.get_process_cwd", return_value=Path("/home/dev")):
            tracker.check()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "shell.focused_cwd_changed")
        self.assertEqual(events[0].data["old_path"], "/tmp")
        self.assertEqual(events[0].data["new_path"], "/home/dev")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        pid = int(sys.argv[1])
        bus = EventBus()
        bus.subscribe("shell.focused_cwd_changed", lambda e: print("EVENT:", e.event_type, e.data))
        focused = FocusedSession()
        focused.set_pid(pid)
        tracker = FocusedCwdTracker(focused, bus)
        print("Tracking focused PID:", pid)
        print("Press Ctrl+C to stop.")
        try:
            while True:
                tracker.check()
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopping.")
    else:
        unittest.main()
