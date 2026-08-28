import time

from app.core.event_bus import EventBus
from app.process.session_manager import (
    TerminalSessionManager,
)


def on_event(event):

    print(
        "\nEVENT:",
        event.event_type
    )

    print(
        "DATA:",
        event.data
    )


bus = EventBus()

bus.subscribe(
    "shell.session_created",
    on_event
)

bus.subscribe(
    "shell.session_removed",
    on_event
)

bus.subscribe(
    "shell.cwd_changed",
    on_event
)


manager = TerminalSessionManager(
    bus
)


print(
    "Initial discovery..."
)

manager.refresh()

print(
    "\nCurrent sessions:"
)

for session in manager.sessions():

    print(
        f"PID={session.pid} "
        f"TTY={session.tty} "
        f"CWD={session.cwd}"
    )


print(
    "\nNow change directory in a tracked terminal."
)

print(
    "Refreshing every 0.5 seconds."
)

print(
    "Press Ctrl+C to stop."
)


try:

    while True:

        manager.refresh()

        time.sleep(0.5)

except KeyboardInterrupt:

    print(
        "\nStopping."
    )
