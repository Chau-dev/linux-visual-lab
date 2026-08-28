import os
import sys

from app.process.cwd import get_process_cwd


if len(sys.argv) != 2:
    print("Usage: python -m tests.test_process_cwd <pid>")
    sys.exit(1)


pid = int(sys.argv[1])

print(
    "Python PID:",
    os.getpid()
)

print(
    "Target PID:",
    pid
)

cwd = get_process_cwd(
    pid
)

print(
    "Target process CWD:",
    cwd
)
