from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.process.session_worker import (
    TerminalSessionWorker,
)


class TerminalSessionThread(QObject):
    """
    Owns a dedicated QThread for TerminalSessionWorker.

    The worker performs /proc polling in its own thread.
    """

    event_ready = Signal(object)
    sessions_updated = Signal(object)
    error = Signal(str)

    stop_requested = Signal()

    def __init__(
        self,
        interval_ms: int = 500,
        parent=None,
    ):
        super().__init__(parent)

        self.thread = QThread()

        self.worker = TerminalSessionWorker(
            interval_ms=interval_ms
        )

        self.worker.moveToThread(
            self.thread
        )

        # ====================================================
        # Thread startup
        # ====================================================

        self.thread.started.connect(
            self.worker.start
        )

        # ====================================================
        # Worker events
        # ====================================================

        self.worker.event_detected.connect(
            self.event_ready
        )

        self.worker.sessions_updated.connect(
            self.sessions_updated
        )

        self.worker.error.connect(
            self.error
        )

        # ====================================================
        # Safe worker shutdown
        # ====================================================

        self.stop_requested.connect(
            self.worker.stop
        )

        self.worker.finished.connect(
            self.thread.quit
        )

        self.thread.finished.connect(
            self.worker.deleteLater
        )

    # ========================================================
    # Start
    # ========================================================

    def start(self):

        if not self.thread.isRunning():

            self.thread.start()

    # ========================================================
    # Stop
    # ========================================================

    def stop(self):
        """
        Request shutdown from the worker thread.
        """

        if not self.thread.isRunning():

            return

        from PySide6.QtCore import QMetaObject, Qt

        try:
            QMetaObject.invokeMethod(
                self.worker,
                "stop",
                Qt.ConnectionType.BlockingQueuedConnection,
            )
        except Exception:
            pass

        self.thread.quit()

        self.thread.wait()

    # ========================================================
    # Destructor safety
    # ========================================================

    def __del__(self):

        try:

            self.stop()

        except Exception:

            pass
