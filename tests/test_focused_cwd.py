import sys

from app.process.focused_session import (
    FocusedSession,
)

from app.process.focused_cwd import (
    FocusedSessionCwd,
)


if len(sys.argv) != 2:
    print(
        "Usage: python -m tests.test_focused_cwd <pid>"
    )
    sys.exit(1)


pid = int(sys.argv[1])

focused = FocusedSession()

focused.set_pid(
    pid
)

cwd_reader = FocusedSessionCwd(
    focused
)

cwd = cwd_reader.get()

print(
    "Focused PID:",
    pid
)

print(
    "Focused CWD:",
    cwd
)
