from app.process.session import TerminalSession


class TerminalSessionRegistry:
    """
    Keeps track of currently known terminal sessions.

    Sessions are keyed by PID.
    """

    def __init__(self):
        self._sessions: dict[int, TerminalSession] = {}

    def add(
        self,
        session: TerminalSession
    ):
        self._sessions[session.pid] = session

    def remove(
        self,
        pid: int
    ):
        self._sessions.pop(
            pid,
            None
        )

    def get(
        self,
        pid: int
    ) -> TerminalSession | None:
        return self._sessions.get(pid)

    def all(
        self
    ) -> list[TerminalSession]:
        return list(
            self._sessions.values()
        )

    def contains(
        self,
        pid: int
    ) -> bool:
        return pid in self._sessions

    def clear(
        self
    ):
        self._sessions.clear()
