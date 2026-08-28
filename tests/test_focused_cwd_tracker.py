import sys
import time

from app.core.event_bus import EventBus
from app.process.focused_cwd_tracker import (
    FocusedCwdTracker,
)
from app.process.focused_session import (
    FocusedSession,
)


if len(sys.argv) != 2:

    print(
        "Usage: "
        "python -m tests.test_focused_cwd_tracker "
        "<bash_pid>"
    )

    sys.exit(1)


pid = int(
    sys.argv[1]
)


def on_event(event):

    print()
    print(
        "EVENT:",
        event.event_type
    )

    print(
        "DATA:",
        event.data
    )


bus = EventBus()

bus.subscribe(
    "shell.focused_cwd_changed",
    on_event
)


focused = FocusedSession()

focused.set_pid(
    pid
)


tracker = FocusedCwdTracker(
    focused,
    bus
)


print(
    "Tracking focused PID:",
    pid
)

print(
    "Change directory in that terminal."
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
