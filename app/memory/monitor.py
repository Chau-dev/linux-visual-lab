from __future__ import annotations

from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, QMetaObject, Qt

from app.core.events import SystemEvent
from app.memory.model import MemorySnapshot, SystemLoadSnapshot
from app.memory.discovery import read_memory_snapshot, read_system_load
from app.memory.registry import MemoryRegistry, diff_memory_snapshots


class MemoryWorker(QObject):
    """
    Performs periodic Linux /proc/meminfo, /proc/loadavg, and /proc/uptime sampling in a dedicated QThread.

    Observation Contract:
      - The monitor reports the values observed at each sampling point.
      - It does not claim to capture transient changes that occur entirely between samples.
      - A memory snapshot is considered a point-in-time observation; the subsystem must not infer
        the cause of a metric change from /proc/meminfo alone.
      - The worker never touches GUI widgets and communicates solely via Qt signals.
    """

    memory_updated = Signal(object, object)
    event_detected = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        interval_ms: int = 1000,
        proc_root: Path = Path("/proc"),
        parent=None,
    ):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self.proc_root = proc_root
        self.registry = MemoryRegistry()
        self.timer: QTimer | None = None
        self._running = False
        self._has_initial_snapshot = False

    @Slot()
    def start(self):
        """Start periodic /proc memory sampling."""
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
        """Execute one /proc memory sampling and state diff cycle."""
        if not self._running and self._has_initial_snapshot:
            return

        try:
            observed_at = datetime.now()
            current_mem = read_memory_snapshot(self.proc_root)
            current_load = read_system_load(self.proc_root)

            if current_mem is None:
                self.error.emit("Required /proc/meminfo fields missing or unreadable")
                return

            previous_mem = self.registry.get_memory()

            self.registry.set_memory(current_mem)
            if current_load is not None:
                self.registry.set_load(current_load)

            if self._has_initial_snapshot:
                events = diff_memory_snapshots(previous_mem, current_mem, observed_at=observed_at)
                for event in events:
                    self.event_detected.emit(event)
            else:
                self._has_initial_snapshot = True

            self.memory_updated.emit(current_mem, current_load)

        except Exception as err:
            self.error.emit(str(err))

    # Alias for manual/testing triggers
    poll_once = refresh


class MemoryMonitor(QObject):
    """
    Clean controller for MemoryWorker running in a dedicated QThread.

    Exposes:
      - start()
      - stop()
      - is_running()
      - registry (MemoryRegistry)
      - Signals: memory_updated(MemorySnapshot, SystemLoadSnapshot), event_detected(SystemEvent), error(str)
    """

    memory_updated = Signal(object, object)
    event_detected = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        interval_ms: int = 1000,
        proc_root: Path = Path("/proc"),
        parent=None,
    ):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self.proc_root = proc_root

        self.thread = QThread()
        self.worker = MemoryWorker(interval_ms=interval_ms, proc_root=proc_root)
        self.worker.moveToThread(self.thread)

        # Thread lifecycle
        self.thread.started.connect(self.worker.start)
        self.worker.memory_updated.connect(self.memory_updated)
        self.worker.event_detected.connect(self.event_detected)
        self.worker.error.connect(self.error)

        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)

    @property
    def registry(self) -> MemoryRegistry:
        return self.worker.registry

    def start(self):
        """Start background memory monitor thread."""
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
