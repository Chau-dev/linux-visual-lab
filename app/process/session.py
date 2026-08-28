from dataclasses import dataclass
from pathlib import Path


@dataclass
class TerminalSession:
    """
    Represents one shell process and its terminal session.
    """

    pid: int
    ppid: int
    command: str
    cwd: Path | None
    tty: str | None
    cwd: Path | None
