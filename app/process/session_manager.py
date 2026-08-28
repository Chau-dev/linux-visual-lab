from app.core.event_bus import EventBus
from app.core.events import SystemEvent

from app.process.discovery import find_shell_processes
from app.process.registry import TerminalSessionRegistry


class TerminalSessionManager:
    """
    Discovers and tracks shell processes.

    The manager itself is independent of Qt.

    refresh() performs one discovery/diff cycle and returns
    the events generated during that cycle.

    If an EventBus is supplied, events are also published
    immediately. This behavior is useful for standalone tests.

    For the Qt background worker, EventBus is intentionally
    omitted so that GUI callbacks are never executed from
    the worker thread.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
    ):
        self.event_bus = event_bus

        self.registry = (
            TerminalSessionRegistry()
        )

    def refresh(self):
        """
        Perform one discovery/diff cycle.

        Returns:
            list[SystemEvent]
        """

        events = []

        discovered = find_shell_processes()

        discovered_by_pid = {
            session.pid: session
            for session in discovered
        }

        # ====================================================
        # New and changed sessions
        # ====================================================

        for session in discovered:

            previous = self.registry.get(
                session.pid
            )

            # ------------------------------------------------
            # New session
            # ------------------------------------------------

            if previous is None:

                self.registry.add(
                    session
                )

                event = SystemEvent(
                    event_type="shell.session_created",
                    data={
                        "pid": session.pid,
                        "ppid": session.ppid,
                        "command": session.command,
                        "tty": session.tty,
                        "cwd": (
                            str(session.cwd)
                            if session.cwd
                            else None
                        ),
                    },
                )

                events.append(
                    event
                )

                self._publish_if_configured(
                    event
                )

                continue

            # ------------------------------------------------
            # Existing session: CWD changed
            # ------------------------------------------------

            if previous.cwd != session.cwd:

                old_cwd = (
                    str(previous.cwd)
                    if previous.cwd
                    else None
                )

                new_cwd = (
                    str(session.cwd)
                    if session.cwd
                    else None
                )

                self.registry.add(
                    session
                )

                event = SystemEvent(
                    event_type="shell.cwd_changed",
                    data={
                        "pid": session.pid,
                        "tty": session.tty,
                        "old_path": old_cwd,
                        "new_path": new_cwd,
                    },
                )

                events.append(
                    event
                )

                self._publish_if_configured(
                    event
                )

            else:

                # Keep the latest state.
                self.registry.add(
                    session
                )

        # ====================================================
        # Removed sessions
        # ====================================================

        tracked_sessions = (
            self.registry.all()
        )

        for session in tracked_sessions:

            if session.pid not in discovered_by_pid:

                self.registry.remove(
                    session.pid
                )

                event = SystemEvent(
                    event_type="shell.session_removed",
                    data={
                        "pid": session.pid,
                        "ppid": session.ppid,
                        "command": session.command,
                        "tty": session.tty,
                        "cwd": (
                            str(session.cwd)
                            if session.cwd
                            else None
                        ),
                    },
                )

                events.append(
                    event
                )

                self._publish_if_configured(
                    event
                )

        return events

    # ========================================================
    # EventBus helper
    # ========================================================

    def _publish_if_configured(
        self,
        event: SystemEvent,
    ):

        if self.event_bus is not None:

            self.event_bus.publish(
                event
            )

    # ========================================================
    # Current sessions
    # ========================================================

    def sessions(self):

        return self.registry.all()
