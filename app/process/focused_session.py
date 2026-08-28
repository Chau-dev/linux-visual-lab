class FocusedSession:
    """
    Stores the PID of the terminal session currently
    being followed by the GUI.
    """

    def __init__(self):
        self.pid = None

    def set_pid(self, pid: int):
        self.pid = pid

    def clear(self):
        self.pid = None

    def has_session(self) -> bool:
        return self.pid is not None
