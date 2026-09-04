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
    Performs terminal-session discovery inside a dedicated QThread.

    The worker never touches GUI widgets.
    It communicates with the GUI using Qt signals.
    """

    event_detected = Signal(object)
    sessions_updated = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        interval_ms: int = 500,
        parent=None,
    ):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self.manager = TerminalSessionManager()
        self.timer: QTimer | None = None
        self._running = False

    @Slot()
    def start(self):
        """
        Start periodic session discovery.
        Runs inside the worker thread upon thread started.
        """
        if self._running:
            return

        self._running = True

        self.timer = QTimer()
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self.refresh)

        # Initial discovery
        self.refresh()
        self.timer.start()

    @Slot()
    def stop(self):
        """
        Stop the worker and release timer in the worker's thread.
        """
        if not self._running:
            self.finished.emit()
            return

        self._running = False

        if self.timer is not None:
            try:
                self.timer.stop()
                self.timer.timeout.disconnect()
            except Exception:
                pass
            self.timer.deleteLater()
            self.timer = None

        self.finished.emit()

    @Slot()
    def refresh(self):
        """
        Run one session discovery cycle.
        """
        if not self._running:
            return

        try:
            events = self.manager.refresh(publish=False)

            for event in events:
                self.event_detected.emit(event)

            sessions = {
                session.pid: session
                for session in self.manager.sessions()
            }
            self.sessions_updated.emit(sessions)

        except Exception as error:
            self.error.emit(str(error))
