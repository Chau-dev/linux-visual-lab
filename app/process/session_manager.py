from app.core.event_bus import EventBus
from app.core.events import SystemEvent
from app.process.discovery import find_shell_processes
from app.process.registry import TerminalSessionRegistry


class TerminalSessionManager:
    """
    Discovers and tracks Linux shell processes.

    The manager maintains state and can either:
      - publish events directly, or
      - return generated events to a caller.

    The second mode is used by the Qt worker so that
    EventBus callbacks remain on the GUI thread.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
    ):
        self.event_bus = event_bus

        self.registry = TerminalSessionRegistry()

    # ========================================================
    # Refresh
    # ========================================================

    def refresh(
        self,
        publish: bool = True,
    ):
        """
        Perform one discovery/diff cycle.

        Returns:
            list[SystemEvent]

        If publish=True and an EventBus was supplied,
        events are also published immediately.

        The Qt background worker uses publish=False.
        """

        events = []

        discovered = find_shell_processes()

        discovered_by_pid = {
            session.pid: session
            for session in discovered
        }

        # ====================================================
        # New and existing sessions
        # ====================================================

        for session in discovered:

            previous = self.registry.get(
                session.pid
            )

            # ----------------------------------------------
            # New shell
            # ----------------------------------------------

            if previous is None:

                self.registry.add(
                    session
                )

                events.append(
                    SystemEvent(
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
                        source="Shell session tracker",
                        mechanism="/proc scan",
                    )
                )

                continue

            # ----------------------------------------------
            # Existing shell
            # ----------------------------------------------

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

                events.append(
                    SystemEvent(
                        event_type="shell.cwd_changed",
                        data={
                            "pid": session.pid,
                            "tty": session.tty,
                            "old_path": old_cwd,
                            "new_path": new_cwd,
                        },
                        source="Shell session tracker",
                        mechanism="/proc/<pid>/cwd",
                    )
                )

            else:

                # Keep latest process information.
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

                events.append(
                    SystemEvent(
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
                        source="Shell session tracker",
                        mechanism="/proc scan",
                    )
                )

        # ====================================================
        # Optional immediate publication
        # ====================================================

        if publish and self.event_bus is not None:

            for event in events:

                self.event_bus.publish(
                    event
                )

        return events

    # ========================================================
    # Current sessions
    # ========================================================

    def sessions(self):
        """
        Return currently tracked sessions.
        """

        return self.registry.all()
