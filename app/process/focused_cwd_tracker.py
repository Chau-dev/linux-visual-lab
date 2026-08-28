from pathlib import Path

from app.core.event_bus import EventBus
from app.core.events import SystemEvent
from app.process.cwd import get_process_cwd
from app.process.focused_session import FocusedSession


class FocusedCwdTracker:
    """
    Tracks the current working directory of the
    currently focused terminal session.

    This class does not run its own loop.
    The caller invokes check() periodically.
    """

    def __init__(
        self,
        focused_session: FocusedSession,
        event_bus: EventBus,
    ):
        self.focused_session = focused_session
        self.event_bus = event_bus

        self.previous_cwd: Path | None = None

    def check(self):
        """
        Check the focused shell's current working directory.

        Publishes shell.focused_cwd_changed when the
        focused shell changes directory.
        """

        # No terminal is currently focused.
        if not self.focused_session.has_session():

            self.previous_cwd = None

            return

        pid = self.focused_session.pid

        current_cwd = get_process_cwd(pid)

        # The shell may have exited.
        if current_cwd is None:

            self.previous_cwd = None

            return

        # First observation after selecting a session.
        if self.previous_cwd is None:

            self.previous_cwd = current_cwd

            return

        # Nothing changed.
        if current_cwd == self.previous_cwd:

            return

        old_cwd = self.previous_cwd

        self.previous_cwd = current_cwd

        self.event_bus.publish(
            SystemEvent(
                event_type="shell.focused_cwd_changed",
                data={
                    "pid": pid,
                    "old_path": str(old_cwd),
                    "new_path": str(current_cwd),
                },
            )
        )
