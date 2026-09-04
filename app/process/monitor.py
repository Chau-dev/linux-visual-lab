from __future__ import annotations

from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, QMetaObject, Qt

from app.core.events import SystemEvent
from app.process.model import Process
from app.process.discovery import discover_all_processes
from app.process.registry import ProcessRegistry, diff_process_snapshots


class ProcessWorker(QObject):
    """
    Performs Linux /proc sampling and state-diffing inside a dedicated QThread.

    The worker never touches GUI widgets and communicates solely via Qt signals.
    """

    event_detected = Signal(object)
    processes_updated = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        interval_ms: int = 500,
        proc_root: Path = Path("/proc"),
        parent=None,
    ):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self.proc_root = proc_root
        self.registry = ProcessRegistry()
        self.timer: QTimer | None = None
        self._running = False
        self._has_initial_snapshot = False

    @Slot()
    def start(self):
        """Start periodic /proc sampling."""
        if self._running:
            return

        self._running = True

        self.timer = QTimer()
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self.refresh)

        # Initial baseline sample
        self.refresh()
        self.timer.start()

    @Slot()
    def stop(self):
        """Stop sampling and cleanup timer inside worker thread."""
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
        """Execute one /proc sampling and state diff cycle."""
        if not self._running and self._has_initial_snapshot:
            return

        try:
            observed_at = datetime.now()
            current_snapshot = discover_all_processes(self.proc_root)
            previous_snapshot = self.registry.get_snapshot()

            self.registry.set_snapshot(current_snapshot)

            if self._has_initial_snapshot:
                events = diff_process_snapshots(previous_snapshot, current_snapshot, observed_at=observed_at)
                for event in events:
                    self.event_detected.emit(event)
            else:
                self._has_initial_snapshot = True

            self.processes_updated.emit(current_snapshot)

        except Exception as err:
            self.error.emit(str(err))


class ProcessMonitor(QObject):
    """
    Clean controller for ProcessWorker running in a dedicated QThread.

    Exposes:
      - start()
      - stop()
      - is_running()
      - registry (ProcessRegistry)
      - Signals: event_detected(SystemEvent), processes_updated(dict[int, Process]), error(str)
    """

    event_detected = Signal(object)
    processes_updated = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        interval_ms: int = 500,
        proc_root: Path = Path("/proc"),
        parent=None,
    ):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self.proc_root = proc_root

        self.thread = QThread()
        self.worker = ProcessWorker(interval_ms=interval_ms, proc_root=proc_root)
        self.worker.moveToThread(self.thread)

        # Thread lifecycle
        self.thread.started.connect(self.worker.start)
        self.worker.event_detected.connect(self.event_detected)
        self.worker.processes_updated.connect(self.processes_updated)
        self.worker.error.connect(self.error)

        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)

    @property
    def registry(self) -> ProcessRegistry:
        return self.worker.registry

    def start(self):
        """Start the background process monitor thread."""
        if not self.thread.isRunning():
            self.thread.start()

    def stop(self):
        """Safely stop the worker in its thread and wait for clean shutdown."""
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
        return self.thread.isRunning()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
