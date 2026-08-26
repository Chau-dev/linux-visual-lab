from pathlib import Path


CURRENT_DIRECTORY_FILE = Path(
    "/home/dev/LinuxLab/.current_directory"
)


def set_current_directory(path):

    path = Path(path).expanduser().resolve()

    CURRENT_DIRECTORY_FILE.write_text(
        str(path),
        encoding="utf-8"
    )


def get_current_directory():

    if not CURRENT_DIRECTORY_FILE.exists():
        return None

    try:
        path = Path(
            CURRENT_DIRECTORY_FILE.read_text(
                encoding="utf-8"
            ).strip()
        )

        if path.exists():
            return path

    except OSError:
        pass

    return None
