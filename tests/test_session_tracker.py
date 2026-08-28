import os
import sys
import time

from app.core.event_bus import EventBus
from app.process.session_tracker import TerminalSessionTracker


if len(sys.argv) != 2:
    print(
        "Usage: python -m tests.test_session_tracker <shell_pid>"
    )
    sys.exit(1)


shell_pid = int(sys.argv[1])


def on_cwd_changed(event):

    print(
        "\nCWD CHANGED"
    )

    print(
        "PID:",
        event.data["pid"]
    )

    print(
        "OLD:",
        event.data["old_path"]
    )

    print(
        "NEW:",
        event.data["new_path"]
    )


bus = EventBus()

bus.subscribe(
    "shell.cwd_changed",
    on_cwd_changed
)


tracker = TerminalSessionTracker(
    shell_pid,
    bus
)


print(
    "Tracking shell PID:",
    shell_pid
)

print(
    "Watching /proc/<PID>/cwd"
)

print(
    "Change directory in the target terminal."
)

print(
    "Press Ctrl+C to stop."
)


try:

    while True:

        tracker.check()

        time.sleep(0.5)

except KeyboardInterrupt:

    print(
        "\nStopping."
    )
