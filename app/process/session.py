from dataclasses import dataclass
from pathlib import Path


@dataclass
class TerminalSession:
    """
    Represents one shell process and its terminal session.
    """

    pid: int
    command: str
    ppid: int | None = None
    cwd: Path | None = None
    tty: str | None = None

