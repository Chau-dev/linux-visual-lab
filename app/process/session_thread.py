from PySide6.QtCore import QObject, QThread, Signal, Slot, QMetaObject, Qt

from app.process.session_worker import TerminalSessionWorker


class TerminalSessionThread(QObject):
    """
    Clean controller for TerminalSessionWorker running inside a dedicated QThread.

    Exposes controller methods:
        - start()
        - stop()

    And Qt signals:
        - event_detected(SystemEvent)
        - sessions_updated(dict[int, TerminalSession])
        - error(str)
    """

    event_detected = Signal(object)
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
        self.worker = TerminalSessionWorker(interval_ms=interval_ms)
        self.worker.moveToThread(self.thread)

        # Thread startup triggers worker start
        self.thread.started.connect(self.worker.start)
        self.stop_requested.connect(self.worker.stop)

        # Forward worker signals to controller signals
        self.worker.event_detected.connect(self.event_detected)
        self.worker.sessions_updated.connect(self.sessions_updated)
        self.worker.error.connect(self.error)

        # Clean lifecycle
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)

    def start(self):
        """
        Start the background polling thread.
        """
        if not self.thread.isRunning():
            self.thread.start()

    def stop(self):
        """
        Safely stop the worker in its own thread and wait for completion.
        """
        if not self.thread.isRunning():
            return

        try:
            QMetaObject.invokeMethod(
                self.worker,
                "stop",
                Qt.ConnectionType.BlockingQueuedConnection,
            )
        except Exception:
            pass

        self.thread.quit()
        self.thread.wait(2000)

    def is_running(self) -> bool:
        """
        Return whether the background thread is running.
        """
        return self.thread.isRunning()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
