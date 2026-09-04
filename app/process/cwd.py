from pathlib import Path


def get_process_cwd(pid: int) -> Path | None:
    """
    Get the current working directory of a Linux process.

    Linux exposes a process's working directory through:

        /proc/<pid>/cwd
    """

    proc_cwd = Path(
        f"/proc/{pid}/cwd"
    )

    try:
        return proc_cwd.resolve(strict=True)

    except (
        FileNotFoundError,
        PermissionError,
        OSError,
    ):
        return None

