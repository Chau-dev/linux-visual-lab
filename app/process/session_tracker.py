from pathlib import Path

from app.core.events import SystemEvent
from app.core.event_bus import EventBus
from app.process.cwd import get_process_cwd


class TerminalSessionTracker:
    """
    Tracks the current working directory of one Linux shell process.

    The target shell is identified by its PID.
    """

    def __init__(
        self,
        pid: int,
        event_bus: EventBus,
    ):
        self.pid = pid
        self.event_bus = event_bus

        self.previous_cwd = (
            get_process_cwd(self.pid)
        )

    def check(self):
        """
        Check the shell's current working directory.

        If it changed, publish a shell.cwd_changed event.
        """

        current_cwd = (
            get_process_cwd(self.pid)
        )

        # The process may have exited.
        if current_cwd is None:
            return

        # First observation.
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
                event_type="shell.cwd_changed",
                data={
                    "pid": self.pid,
                    "old_path": str(old_cwd),
                    "new_path": str(current_cwd),
                },
            )
        )
