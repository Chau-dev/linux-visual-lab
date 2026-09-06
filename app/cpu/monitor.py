from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QMetaObject, QObject, QThread, QTimer, Qt, Signal, Slot

from app.cpu.discovery import read_cpu_stat
from app.cpu.model import CpuStatSnapshot, CpuUtilization
from app.cpu.registry import CpuRegistry


class CpuWorker(QObject):
    """
    Performs periodic Linux /proc/stat CPU sampling in a dedicated QThread.

    Observation Contract:
      - The monitor samples /proc/stat cumulative time counters.
      - Delta calculations and utilization percentages are derived across successive samples.
      - Direct telemetry flow: high-frequency CPU samples are emitted via cpu_updated
        and are not pushed to the Activity Timeline to prevent log spam.
      - The worker never touches GUI widgets directly and communicates solely via Qt signals.
    """

    cpu_updated = Signal(object, object)  # (CpuUtilization | None, CpuStatSnapshot)
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
        self.registry = CpuRegistry()
        self.timer: QTimer | None = None
        self._running = False

    @Slot()
    def start(self):
        """Start periodic /proc/stat CPU sampling."""
        if self._running:
            return

        self._running = True

        self.timer = QTimer()
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self.refresh)

        # Initial sample to establish baseline
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
        """Execute one /proc/stat sampling and delta computation cycle."""
        if not self._running:
            # Allow single-shot manual poll if triggered explicitly
            pass

        try:
            current_snap = read_cpu_stat(self.proc_root)
            if current_snap is None:
                self.error.emit("Required /proc/stat CPU counters missing or unreadable")
                return

            utilization = self.registry.update(current_snap)
            self.cpu_updated.emit(utilization, current_snap)

        except Exception as err:
            self.error.emit(str(err))

    # Alias for manual/testing triggers
    poll_once = refresh


class CpuMonitor(QObject):
    """
    Controller for CpuWorker running in a dedicated background QThread.

    Exposes:
      - start()
      - stop()
      - is_running()
      - registry (CpuRegistry)
      - Signals: cpu_updated(CpuUtilization | None, CpuStatSnapshot), error(str)
    """

    cpu_updated = Signal(object, object)
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
        self.worker = CpuWorker(interval_ms=interval_ms, proc_root=proc_root)
        self.worker.moveToThread(self.thread)

        # Thread lifecycle
        self.thread.started.connect(self.worker.start)
        self.worker.cpu_updated.connect(self.cpu_updated)
        self.worker.error.connect(self.error)

        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)

    @property
    def registry(self) -> CpuRegistry:
        return self.worker.registry

    def start(self):
        """Start background CPU monitor thread."""
        if not self.thread.isRunning():
            self.thread.start()

    def stop(self):
        """Safely stop worker in its thread and wait for clean shutdown."""
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
