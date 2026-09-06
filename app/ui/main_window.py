from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QFrame,
    QTabWidget,
)

from app.core.event_bus import EventBus
from app.core.activity import ActivityTimeline
from app.core.events import SystemEvent
from app.core.models import FilesystemObject
from app.process.session import TerminalSession
from app.process.model import Process
from app.process.focused_session import FocusedSession
from app.process.session_thread import TerminalSessionThread
from app.process.monitor import ProcessMonitor
from app.monitors.filesystem import FileSystemMonitor
from app.memory.monitor import MemoryMonitor
from app.cpu.monitor import CpuMonitor
from app.visualizers.session_panel import TerminalSessionWidget
from app.visualizers.filesystem_view import FilesystemTreeWidget, SelectedObjectInspectorWidget
from app.visualizers.process_view import ProcessLabWidget
from app.visualizers.memory_view import MemoryLabWidget
from app.visualizers.cpu_view import CpuLabWidget
from app.visualizers.activity_timeline import ActivityTimelineWidget
from app.ui.panels import ContextPanel


def get_default_lab_path() -> Path:
    """
    Determine a valid, accessible directory for the Linux Lab.
    Falls back gracefully if /home/dev/LinuxLab is unavailable.
    """
    candidates = [
        Path("/home/dev/LinuxLab"),
        Path.home() / "LinuxLab",
        Path.cwd() / "LinuxLab",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if candidate.exists():
                return candidate.resolve()
        except OSError:
            continue
    return Path.home().resolve()


class MainWindow(QMainWindow):
    """
    Orchestrator Window for Linux Visual Learning Lab.

    Thin coordinator that wires together:
      - Core (EventBus, ActivityTimeline, FocusedSession)
      - Observers & State Managers (FileSystemMonitor, TerminalSessionThread, ProcessMonitor)
      - Visualizers (ContextPanel, TerminalSessionWidget, FilesystemTreeWidget, SelectedObjectInspectorWidget, ProcessLabWidget, Timeline)
    """

    def __init__(self, lab_path: Path | None = None, process_interval_ms: int = 500):
        super().__init__()

        self.setWindowTitle("Linux Visual Learning Lab")
        self.resize(1600, 920)

        self.lab_path = lab_path or get_default_lab_path()
        self.process_interval_ms = process_interval_ms

        # Lifecycle stages
        self.create_core()
        self.create_monitors()
        self.create_visualizers()
        self.connect_events()
        self.create_layout()
        self.start_workers()

    # ========================================================
    # 1. Create Core State
    # ========================================================
    def create_core(self):
        self.event_bus = EventBus()
        self.activity_timeline = ActivityTimeline(max_events=100)
        self.focused_session = FocusedSession()
        self.session_snapshot: dict[int, TerminalSession] = {}
        self.selected_path: Path | None = None

    # ========================================================
    # 2. Create Observers & Controllers
    # ========================================================
    def create_monitors(self):
        self.session_thread = TerminalSessionThread(interval_ms=500)
        self.process_monitor = ProcessMonitor(interval_ms=self.process_interval_ms)
        self.fs_monitor = FileSystemMonitor(self.lab_path, event_bus=self.event_bus)
        self.memory_monitor = MemoryMonitor(interval_ms=1000)
        self.cpu_monitor = CpuMonitor(interval_ms=500)

    # ========================================================
    # 3. Create Visualizers
    # ========================================================
    def create_visualizers(self):
        # Top banner
        self.context_panel = ContextPanel()

        # Left panel components
        self.session_widget = TerminalSessionWidget()
        self.tree_widget = FilesystemTreeWidget()

        # Center panel components
        self.inspector_widget = SelectedObjectInspectorWidget()
        self.process_lab = ProcessLabWidget()
        self.memory_lab = MemoryLabWidget()
        self.cpu_lab = CpuLabWidget()

        # Right panel component
        self.timeline_widget = ActivityTimelineWidget()

    # ========================================================
    # 4. Connect Events & Signals
    # ========================================================
    def connect_events(self):
        # Forward thread signals
        self.session_thread.event_detected.connect(self.event_bus.publish)
        self.session_thread.sessions_updated.connect(self.handle_sessions_updated)
        self.session_thread.error.connect(self.handle_session_error)

        # Forward process monitor signals
        self.process_monitor.event_detected.connect(self.event_bus.publish)
        self.process_monitor.processes_updated.connect(self.handle_processes_updated)
        self.process_monitor.error.connect(self.handle_process_error)

        # Forward memory monitor signals
        self.memory_monitor.memory_updated.connect(self.memory_lab.update_memory)
        self.memory_monitor.event_detected.connect(self.event_bus.publish)
        self.memory_monitor.error.connect(self.handle_memory_error)

        # Forward CPU monitor signals
        self.cpu_monitor.cpu_updated.connect(self.cpu_lab.update_cpu)
        self.cpu_monitor.error.connect(self.handle_cpu_error)

        # Filesystem Monitor signals (GUI thread)
        self.fs_monitor.signals.created.connect(self.handle_fs_change)
        self.fs_monitor.signals.deleted.connect(self.handle_fs_deleted)
        self.fs_monitor.signals.modified.connect(self.handle_fs_change)
        self.fs_monitor.signals.moved.connect(self.handle_fs_moved)
        self.fs_monitor.signals.permissions_changed.connect(self.handle_fs_permissions_changed)

        # Tree selection -> Inspector update
        self.tree_widget.object_selected.connect(self.handle_tree_selection)

        # Session selection -> Focused session update
        self.session_widget.session_selected.connect(self.handle_session_selected)

        # EventBus subscriptions -> Activity Timeline
        system_events = [
            "file.created",
            "file.modified",
            "file.deleted",
            "file.moved",
            "file.permissions_changed",
            "directory.created",
            "directory.deleted",
            "shell.session_created",
            "shell.session_removed",
            "shell.cwd_changed",
            "shell.focused_cwd_changed",
            "process.created",
            "process.removed",
            "process.state_changed",
            "process.cwd_changed",
            "memory.swap_usage_changed",
        ]
        for event_type in system_events:
            self.event_bus.subscribe(event_type, self.handle_bus_event)

        # Specific handler for shell CWD change
        self.event_bus.subscribe("shell.cwd_changed", self.handle_shell_cwd_changed)

    # ========================================================
    # 5. Create Layout & Arrange
    # ========================================================
    def create_layout(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Top context banner
        main_layout.addWidget(self.context_panel)

        # 2. Main 3-column workspace
        workspace = QSplitter(Qt.Orientation.Horizontal)
        workspace.setChildrenCollapsible(False)
        main_layout.addWidget(workspace, 1)

        # Left Panel (Sessions + FS Tree)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        session_title = QLabel("🖥 TERMINAL SESSIONS")
        session_title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px;")
        left_layout.addWidget(session_title)
        left_layout.addWidget(self.session_widget, 2)

        tree_title = QLabel("📁 LINUXLAB FILESYSTEM")
        tree_title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px;")
        left_layout.addWidget(tree_title)
        left_layout.addWidget(self.tree_widget, 3)

        workspace.addWidget(left_panel)

        # Center Panel (Tabbed Labs)
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(4, 0, 4, 0)
        center_layout.setSpacing(6)

        self.center_tabs = QTabWidget()
        self.center_tabs.addTab(self.inspector_widget, "🔬 POSIX Filesystem Lab")
        self.center_tabs.addTab(self.process_lab, "⚡ Linux Process Lab")
        self.center_tabs.addTab(self.memory_lab, "🧠 Linux Memory Lab")
        self.center_tabs.addTab(self.cpu_lab, "🔥 Linux CPU Lab")

        center_layout.addWidget(self.center_tabs, 1)
        workspace.addWidget(center_panel)

        # Right Panel (Live Activity Timeline)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        right_title = QLabel("🔴 LIVE LINUX ACTIVITY")
        right_title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px;")
        right_layout.addWidget(right_title)

        watching_lbl = QLabel(f"Watching: {self.lab_path}")
        watching_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        right_layout.addWidget(watching_lbl)
        right_layout.addWidget(self.timeline_widget, 1)

        workspace.addWidget(right_panel)

        # Proportions: 270px left, 850px center (labs), 360px right (activity)
        workspace.setSizes([270, 850, 360])
        workspace.setStretchFactor(0, 1)
        workspace.setStretchFactor(1, 4)
        workspace.setStretchFactor(2, 2)

    # ========================================================
    # 6. Start Observers
    # ========================================================
    def start_workers(self):
        self.tree_widget.build_tree(self.lab_path)
        self.fs_monitor.start()
        self.session_thread.start()
        self.process_monitor.start()
        self.memory_monitor.start()
        self.cpu_monitor.start()

    # ========================================================
    # Event & State Handlers
    # ========================================================
    def handle_bus_event(self, event: SystemEvent):
        """Record all system events into thread-safe timeline and UI widget."""
        self.activity_timeline.record(event)
        self.timeline_widget.add_event(event)

    def handle_sessions_updated(self, sessions: dict[int, TerminalSession]):
        """Update sessions from background thread snapshot."""
        self.session_snapshot = sessions
        session_list = list(sessions.values())
        self.session_widget.update_sessions(session_list)

        self._ensure_focused_session()
        self._update_focused_location()

    def handle_processes_updated(self, processes: dict[int, Process]):
        """Update live process table/tree and inspector with active terminal branch auto-expanded."""
        self.process_lab.update_processes(processes, focused_pid=self.focused_session.pid)

    def _ensure_focused_session(self):
        """Ensure focused PID is valid; select first if not set or exited."""
        if not self.session_snapshot:
            if self.focused_session.has_session():
                self.focused_session.clear()
                self.session_widget.current_pid = None
                self.session_widget.update_focus_markers()
                self.process_lab.set_focused_pid(None)
            self.context_panel.show_unknown()
            self.tree_widget.highlight_current_directory(None)
            return

        focused_pid = self.focused_session.pid
        if focused_pid is not None and focused_pid in self.session_snapshot:
            return

        first_session = next(iter(self.session_snapshot.values()))
        self.focused_session.set_pid(first_session.pid)
        self.session_widget.current_pid = first_session.pid
        self.session_widget.update_focus_markers()
        self.process_lab.set_focused_pid(first_session.pid)

    def _update_focused_location(self):
        pid = self.focused_session.pid
        if pid is None:
            self.context_panel.show_unknown()
            self.tree_widget.highlight_current_directory(None)
            self.process_lab.set_focused_pid(None)
            return

        session = self.session_snapshot.get(pid)
        if session is None or session.cwd is None:
            self.context_panel.show_unknown()
            self.tree_widget.highlight_current_directory(None)
            return

        self.context_panel.set_location(session.cwd)
        self.tree_widget.highlight_current_directory(session.cwd)
        self.process_lab.set_focused_pid(pid)

    def handle_session_selected(self, pid: int):
        session = self.session_snapshot.get(pid)
        if session is None:
            return

        self.focused_session.set_pid(pid)
        self.context_panel.set_location(session.cwd)
        self.tree_widget.highlight_current_directory(session.cwd)
        self.process_lab.set_focused_pid(pid)

    def handle_shell_cwd_changed(self, event: SystemEvent):
        pid = event.data.get("pid")
        if pid == self.focused_session.pid:
            new_path = event.data.get("new_path")
            if new_path:
                cwd = Path(new_path)
                self.context_panel.set_location(cwd)
                self.tree_widget.highlight_current_directory(cwd)

    def handle_tree_selection(self, path: Path):
        self.selected_path = path
        self._refresh_inspector()

    def _refresh_inspector(self):
        if self.selected_path is None:
            self.inspector_widget.clear_context()
            return

        fs_obj = FilesystemObject.from_path(self.selected_path)
        if fs_obj is None:
            self.inspector_widget.clear_context()
            self.selected_path = None
            return

        self.inspector_widget.set_context(fs_obj)

    def handle_fs_change(self, path_str: str, *args):
        self.tree_widget.build_tree(self.lab_path)
        self._update_focused_location()
        if self.selected_path:
            self.tree_widget.select_path(self.selected_path)
            self._refresh_inspector()

    def handle_fs_deleted(self, path_str: str, is_dir: bool):
        if self.selected_path:
            try:
                if Path(path_str).resolve() == self.selected_path.resolve():
                    self.selected_path = None
                    self.inspector_widget.clear_context()
            except OSError:
                pass
        self.tree_widget.build_tree(self.lab_path)
        self._update_focused_location()
        if self.selected_path:
            self.tree_widget.select_path(self.selected_path)
            self._refresh_inspector()

    def handle_fs_moved(self, old_path: str, new_path: str):
        if self.selected_path:
            try:
                if Path(old_path).resolve() == self.selected_path.resolve():
                    self.selected_path = Path(new_path)
            except OSError:
                pass
        self.tree_widget.build_tree(self.lab_path)
        self._update_focused_location()
        if self.selected_path:
            self.tree_widget.select_path(self.selected_path)
            self._refresh_inspector()

    def handle_fs_permissions_changed(self, path_str: str, old_mode: str, new_mode: str):
        self.tree_widget.build_tree(self.lab_path)
        self._update_focused_location()
        if self.selected_path:
            self.tree_widget.select_path(self.selected_path)
            self._refresh_inspector()

    def handle_session_error(self, err_msg: str):
        print(f"[SessionWorker Error] {err_msg}")

    def handle_process_error(self, err_msg: str):
        print(f"[ProcessWorker Error] {err_msg}")

    def handle_memory_error(self, err_msg: str):
        print(f"[MemoryWorker Error] {err_msg}")

    def handle_cpu_error(self, err_msg: str):
        print(f"[CpuWorker Error] {err_msg}")

    # ========================================================
    # 7. Safe Application Shutdown
    # ========================================================
    def closeEvent(self, event):
        if hasattr(self, "tree_widget") and hasattr(self.tree_widget, "tree_delegate"):
            self.tree_widget.tree_delegate.stop()

        if hasattr(self, "fs_monitor"):
            self.fs_monitor.stop()

        if hasattr(self, "session_thread"):
            self.session_thread.stop()

        if hasattr(self, "process_monitor"):
            self.process_monitor.stop()

        if hasattr(self, "memory_monitor"):
            self.memory_monitor.stop()

        if hasattr(self, "cpu_monitor"):
            self.cpu_monitor.stop()

        event.accept()
