from pathlib import Path

from app.process.session import TerminalSession


def get_process_tty(
    pid: int
) -> str | None:
    """
    Get the terminal/TTY associated with a process.
    """

    fd_path = Path(
        f"/proc/{pid}/fd/0"
    )

    try:
        target = fd_path.resolve()

    except (
        FileNotFoundError,
        PermissionError,
        OSError,
    ):
        return None

    text = str(target)

    if text.startswith("/dev/"):

        return text

    return None

def get_process_ppid(
    pid: int
) -> int | None:
    """
    Read the parent PID from /proc/<pid>/stat.
    """

    stat_path = Path(
        f"/proc/{pid}/stat"
    )

    try:

        content = stat_path.read_text(
            encoding="utf-8"
        ).strip()

        closing_paren = content.rfind(")")

        if closing_paren == -1:
            return None

        remainder = content[
            closing_paren + 2:
        ]

        fields = remainder.split()

        return int(fields[1])

    except (
        FileNotFoundError,
        PermissionError,
        OSError,
        ValueError,
        IndexError,
    ):
        return None


def find_shell_processes():
    """
    Find running shell processes by inspecting /proc.

    Returns:
        list[TerminalSession]
    """

    shells = []

    proc_root = Path("/proc")

    for entry in proc_root.iterdir():

        if not entry.name.isdigit():
            continue

        pid = int(entry.name)

        comm_path = entry / "comm"

        try:

            command = comm_path.read_text(
                encoding="utf-8"
            ).strip()

        except (
            FileNotFoundError,
            PermissionError,
            OSError,
        ):
            continue

        if command not in {
            "bash",
            "sh",
            "zsh",
            "fish",
        }:
            continue

        cwd_path = entry / "cwd"

        try:

            cwd = cwd_path.resolve()

        except (
            FileNotFoundError,
            PermissionError,
            OSError,
        ):
            cwd = None

        tty = get_process_tty(
            pid
        )

        ppid = get_process_ppid(
            pid
        )

        if ppid is None:
            continue

        shells.append(
            TerminalSession(
                pid=pid,
                ppid=ppid,
                command=command,
                tty=tty,
                cwd=cwd,
            )
        )

    shells.sort(
        key=lambda session: session.pid
    )

    return shells
