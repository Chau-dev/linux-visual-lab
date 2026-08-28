from PySide6.QtCore import (
    QObject,
    QTimer,
    Signal,
    Slot,
)

from app.process.session_manager import (
    TerminalSessionManager,
)


class TerminalSessionWorker(QObject):
    """
    Background worker for terminal-session discovery.

    IMPORTANT:
    - This object lives in the session QThread.
    - Its QTimer is created and controlled inside that thread.
    - The GUI communicates with it through Qt signals.
    """

    event_detected = Signal(object)

    sessions_updated = Signal(object)

    error = Signal(str)

    stop_requested = Signal()

    def __init__(
        self,
        interval_ms: int = 500,
    ):
        super().__init__()

        self.interval_ms = interval_ms

        self.manager = (
            TerminalSessionManager()
        )

        self.timer = None

        # The connection is handled by Qt after this
        # QObject has been moved to its worker thread.
        self.stop_requested.connect(
            self.stop
        )

    # ========================================================
    # Start
    # ========================================================

    @Slot()
    def start(self):
        """
        Start the worker inside its assigned QThread.
        """

        if self.timer is not None:
            return

        self.timer = QTimer(
            self
        )

        self.timer.setInterval(
            self.interval_ms
        )

        self.timer.timeout.connect(
            self.refresh
        )

        # Perform an initial discovery immediately.
        self.refresh()

        self.timer.start()

    # ========================================================
    # Stop
    # ========================================================

    @Slot()
    def stop(self):
        """
        Stop the worker.

        This method must execute in the worker thread.
        """

        if self.timer is None:
            return

        self.timer.stop()

        self.timer.deleteLater()

        self.timer = None

    # ========================================================
    # Refresh
    # ========================================================

    @Slot()
    def refresh(self):
        """
        Perform one terminal-session discovery cycle.
        """

        try:

            events = (
                self.manager.refresh()
            )

            self.sessions_updated.emit(
                self.manager.sessions()
            )

            for event in events:

                self.event_detected.emit(
                    event
                )

        except Exception as error:

            self.error.emit(
                str(error)
            )

    # ========================================================
    # Current sessions
    # ========================================================

    def sessions(self):

        return self.manager.sessions()
