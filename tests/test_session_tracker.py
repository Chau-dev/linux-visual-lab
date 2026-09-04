import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.event_bus import EventBus
from app.process.session_tracker import TerminalSessionTracker


class TestTerminalSessionTracker(unittest.TestCase):

    def test_tracker_emits_on_cwd_change(self):
        bus = EventBus()
        events = []
        bus.subscribe("shell.cwd_changed", lambda e: events.append(e))

        with patch("app.process.session_tracker.get_process_cwd", return_value=Path("/tmp")):
            tracker = TerminalSessionTracker(1234, bus)

        # CWD changes
        with patch("app.process.session_tracker.get_process_cwd", return_value=Path("/home/dev")):
            tracker.check()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "shell.cwd_changed")
        self.assertEqual(events[0].data["pid"], 1234)
        self.assertEqual(events[0].data["old_path"], "/tmp")
        self.assertEqual(events[0].data["new_path"], "/home/dev")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].isdigit():
        shell_pid = int(sys.argv[1])
        bus = EventBus()
        bus.subscribe("shell.cwd_changed", lambda e: print("\nCWD CHANGED:", e.data))
        tracker = TerminalSessionTracker(shell_pid, bus)
        print("Tracking shell PID:", shell_pid)
        print("Press Ctrl+C to stop.")
        try:
            while True:
                tracker.check()
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopping.")
    else:
        unittest.main()
