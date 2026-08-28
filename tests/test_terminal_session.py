from pathlib import Path

from app.process.session import TerminalSession


session = TerminalSession(
    pid=8798,
    command="bash",
    cwd=Path(
        "/home/dev/LinuxLab"
    ),
)


print("PID:", session.pid)
print("Command:", session.command)
print("CWD:", session.cwd)
