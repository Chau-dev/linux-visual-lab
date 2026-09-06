from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import QMetaObject, QObject, QThread, QTimer, Qt, Signal, Slot

from app.core.events import SystemEvent
from app.io.discovery import (
    read_process_fds,
    read_process_io,
    read_diskstats,
    read_kernel_locks,
    find_pipe_peer_endpoints,
)
from app.io.model import (
    PipeEndpoint,
    DiskDeviceStat,
    KernelFileLock,
)
from app.io.registry import IoRegistry, ProcessIoState


class IoWorker(QObject):
    """
    Performs focused Linux /proc/<pid>/fd and system I/O sampling in a dedicated background QThread.

    Safeguards:
      - Observes the target PID solely by default.
      - Resolves peer pipe endpoints on demand with bounded search in background thread.
      - Emits Qt signals to communicate with the UI thread without blocking.
    """

    io_updated = Signal(object)  # Emits ProcessIoState
    diskstats_updated = Signal(list)  # Emits list[DiskDeviceStat]
    locks_updated = Signal(list)  # Emits list[KernelFileLock]
    event_detected = Signal(object)  # Emits SystemEvent
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        target_pid: int | None = None,
        interval_ms: int = 500,
        proc_root: Path = Path("/proc"),
        parent=None,
    ):
        super().__init__(parent)
        self.target_pid = target_pid
        self.interval_ms = interval_ms
        self.proc_root = proc_root
        self.registry = IoRegistry()
        self.timer: QTimer | None = None
        self._running = False

    @Slot(int)
    def set_target_pid(self, pid: int | None):
        """Switch tracked target process dynamically."""
        self.target_pid = pid
        self.registry.set_target_pid(pid)
        if self._running:
            self.refresh()

    @Slot()
    def start(self):
        """Start periodic I/O sampling."""
        if self._running:
            return

        self._running = True

        self.timer = QTimer()
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self.refresh)

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
        """Execute one sampling cycle."""
        try:
            # 1. Sample Process FDs and I/O for target PID if specified
            if self.target_pid is not None:
                descriptors, err_reason = read_process_fds(self.target_pid, self.proc_root)
                io_snap = read_process_io(self.target_pid, self.proc_root)

                # Resolve pipe peer endpoints on demand for any pipe FDs
                resolved_pipes: dict[int, list[PipeEndpoint]] = {}
                if descriptors:
                    for fd_obj in descriptors:
                        if fd_obj.is_pipe and fd_obj.target_inode is not None:
                            pipe_ino = fd_obj.target_inode
                            if pipe_ino not in resolved_pipes:
                                # Self endpoint
                                self_ep = PipeEndpoint(
                                    inode=pipe_ino,
                                    pid=self.target_pid,
                                    fd=fd_obj.fd,
                                    access_mode=fd_obj.access_mode,
                                    endpoint_role=fd_obj.pipe_endpoint_role,
                                    process_command=f"PID {self.target_pid}",
                                )
                                peers = find_pipe_peer_endpoints(
                                    pipe_inode=pipe_ino,
                                    exclude_pid=self.target_pid,
                                    proc_root=self.proc_root,
                                )
                                # Combine self + peers
                                all_endpoints = [self_ep] + peers
                                resolved_pipes[pipe_ino] = all_endpoints

                state, events = self.registry.update(
                    pid=self.target_pid,
                    descriptors=descriptors,
                    error_reason=err_reason,
                    io_snapshot=io_snap,
                    resolved_pipes=resolved_pipes,
                )

                for ev in events:
                    self.event_detected.emit(ev)

                self.io_updated.emit(state)

            # 2. Sample Secondary System Telemetry (/proc/diskstats and /proc/locks)
            diskstats = read_diskstats(self.proc_root)
            self.diskstats_updated.emit(diskstats)

            locks = read_kernel_locks(self.proc_root)
            self.locks_updated.emit(locks)

        except Exception as err:
            self.error.emit(str(err))

    # Alias for manual/testing triggers
    poll_once = refresh


class IoMonitor(QObject):
    """
    Thread controller for the Linux File Descriptors & System I/O subsystem.
    Manages the lifecycle of IoWorker inside a dedicated QThread.
    """

    io_updated = Signal(object)
    diskstats_updated = Signal(list)
    locks_updated = Signal(list)
    event_detected = Signal(object)
    error = Signal(str)

    # Internal cross-thread command signals
    request_set_target_pid = Signal(object)
    request_stop = Signal()

    def __init__(
        self,
        target_pid: int | None = None,
        interval_ms: int = 500,
        proc_root: Path = Path("/proc"),
        parent=None,
    ):
        super().__init__(parent)
        self.target_pid = target_pid
        self.interval_ms = interval_ms
        self.proc_root = proc_root

        self._thread: QThread | None = None
        self._worker: IoWorker | None = None

    def start(self):
        """Creates the background QThread and moves IoWorker into it."""
        if self._thread is not None and self._thread.isRunning():
            return

        self._thread = QThread()
        self._worker = IoWorker(
            target_pid=self.target_pid,
            interval_ms=self.interval_ms,
            proc_root=self.proc_root,
        )
        self._worker.moveToThread(self._thread)

        # Connect internal worker signals to public monitor signals
        self._worker.io_updated.connect(self.io_updated)
        self._worker.diskstats_updated.connect(self.diskstats_updated)
        self._worker.locks_updated.connect(self.locks_updated)
        self._worker.event_detected.connect(self.event_detected)
        self._worker.error.connect(self.error)

        # Cross-thread command connections
        self.request_set_target_pid.connect(
            self._worker.set_target_pid, Qt.ConnectionType.QueuedConnection
        )
        self.request_stop.connect(
            self._worker.stop, Qt.ConnectionType.QueuedConnection
        )

        # Thread lifecycle
        self._thread.started.connect(self._worker.start)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def set_target_pid(self, pid: int | None):
        """Thread-safe update of target PID."""
        self.target_pid = pid
        if self._worker is not None:
            self.request_set_target_pid.emit(pid)

    def stop(self):
        """Stops the worker and terminates the background thread cleanly."""
        if self._worker is not None:
            self.request_stop.emit()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
            self._thread = None
            self._worker = None

    def poll_once(self):
        """Direct single-cycle poll (useful for testing)."""
        if self._worker is not None:
            self._worker.poll_once()
        else:
            worker = IoWorker(
                target_pid=self.target_pid,
                interval_ms=self.interval_ms,
                proc_root=self.proc_root,
            )
            worker.io_updated.connect(self.io_updated)
            worker.diskstats_updated.connect(self.diskstats_updated)
            worker.locks_updated.connect(self.locks_updated)
            worker.event_detected.connect(self.event_detected)
            worker.error.connect(self.error)
            worker.poll_once()
