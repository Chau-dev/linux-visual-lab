from pathlib import Path

from app.process.cwd import get_process_cwd
from app.process.focused_session import FocusedSession


class FocusedSessionCwd:
    """
    Reads the current working directory of the
    currently focused terminal session.
    """

    def __init__(
        self,
        focused_session: FocusedSession
    ):
        self.focused_session = focused_session

    def get(self) -> Path | None:
        """
        Return the CWD of the focused shell.
        """

        if not self.focused_session.has_session():
            return None

        return get_process_cwd(
            self.focused_session.pid
        )
