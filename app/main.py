import sys
import os
import stat

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    QTimer,
    QThread,
    QMetaObject,
)

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QSplitter,
    QFrame,
    QTabWidget,
)

from app.core.event_bus import EventBus
from app.core.activity import ActivityTimeline

from app.models.filesystem_object import FilesystemObject
from app.monitors.filesystem import FileSystemMonitor

from app.process.session_worker import (
    TerminalSessionWorker,
)

from app.process.focused_session import (
    FocusedSession,
)

from app.visualizers.activity_timeline import (
    ActivityTimelineWidget,
)

from app.visualizers.session_panel import (
    TerminalSessionWidget,
)

from app.visualizers.permission_simulator import (
    PermissionSimulatorWidget,
)



# ============================================================
# Configuration & Directory Fallback
# ============================================================

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


LAB_PATH = get_default_lab_path()




# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        # ====================================================
        # Window
        # ====================================================

        self.setWindowTitle(
            "Linux Visual Learning Lab"
        )

        self.resize(
            1600,
            900
        )

        # ====================================================
        # Active Watched Path
        # ====================================================

        self.lab_path = LAB_PATH

        # ====================================================
        # Core state
        # ====================================================

        self.event_bus = EventBus()

        self.activity_timeline = ActivityTimeline(
            max_events=100
        )

        # ====================================================
        # Focused terminal
        # ====================================================

        self.focused_session = FocusedSession()

        # ====================================================
        # Latest terminal-session snapshot
        #
        # Key:
        #     PID
        #
        # Value:
        #     TerminalSession
        #
        # This snapshot is supplied by the background worker.
        # The GUI uses this as its terminal-session state source.
        # ====================================================

        self.session_snapshot = {}

        # ====================================================
        # Selected filesystem object
        # ====================================================

        self.selected_path = None

        # ====================================================
        # Terminal-session worker
        # ====================================================

        self.session_thread = QThread()

        self.session_worker = TerminalSessionWorker(
            interval_ms=500
        )

        self.session_worker.moveToThread(
            self.session_thread
        )

        self.session_thread.started.connect(
            self.session_worker.start
        )

        self.session_worker.event_detected.connect(
            self.handle_session_event
        )

        self.session_worker.sessions_updated.connect(
            self.handle_sessions_updated
        )

        self.session_worker.error.connect(
            self.handle_session_worker_error
        )

        self.session_thread.finished.connect(
            self.session_worker.deleteLater
        )

        # ====================================================
        # Central widget
        # ====================================================

        central = QWidget()

        self.setCentralWidget(
            central
        )

        main_layout = QVBoxLayout(
            central
        )

        main_layout.setContentsMargins(
            10,
            10,
            10,
            10
        )

        main_layout.setSpacing(
            8
        )

        # ====================================================
        # TOP CONTEXT PANEL
        # ====================================================

        context_frame = QFrame()

        context_frame.setFrameShape(
            QFrame.Shape.StyledPanel
        )

        context_layout = QVBoxLayout(
            context_frame
        )

        context_layout.setContentsMargins(
            10,
            8,
            10,
            8
        )

        context_layout.setSpacing(
            4
        )

        # ----------------------------------------------------
        # Location header
        # ----------------------------------------------------

        self.location_label = QLabel(
            "📍 CURRENT LOCATION: unknown"
        )

        self.location_label.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
            }
            """
        )

        context_layout.addWidget(
            self.location_label
        )

        # ----------------------------------------------------
        # Breadcrumb
        # ----------------------------------------------------

        self.breadcrumb_label = QLabel(
            "/"
        )

        self.breadcrumb_label.setWordWrap(
            True
        )

        self.breadcrumb_label.setStyleSheet(
            """
            QLabel {
                font-size: 13px;
            }
            """
        )

        context_layout.addWidget(
            self.breadcrumb_label
        )

        # ----------------------------------------------------
        # Navigation
        # ----------------------------------------------------

        self.navigation_label = QLabel(
            "Parent: /    |    "
            "Home: /    |    "
            "Root: /"
        )

        self.navigation_label.setWordWrap(
            True
        )

        self.navigation_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
            }
            """
        )

        context_layout.addWidget(
            self.navigation_label
        )

        # ----------------------------------------------------
        # Path anatomy
        # ----------------------------------------------------

        self.path_anatomy_label = QLabel(
            "Path anatomy: /"
        )

        self.path_anatomy_label.setWordWrap(
            True
        )

        self.path_anatomy_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
            }
            """
        )

        context_layout.addWidget(
            self.path_anatomy_label
        )

        main_layout.addWidget(
            context_frame
        )

        # ====================================================
        # MAIN WORKSPACE
        # ====================================================

        workspace_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        workspace_splitter.setChildrenCollapsible(
            False
        )

        main_layout.addWidget(
            workspace_splitter,
            1
        )

        # ====================================================
        # LEFT PANEL
        # ====================================================

        left_panel = QWidget()

        left_layout = QVBoxLayout(
            left_panel
        )

        left_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        left_layout.setSpacing(
            6
        )

        # ----------------------------------------------------
        # Terminal title
        # ----------------------------------------------------

        session_title = QLabel(
            "🖥 TERMINAL SESSIONS"
        )

        session_title.setStyleSheet(
            """
            QLabel {
                font-size: 15px;
                font-weight: bold;
                padding: 4px;
            }
            """
        )

        left_layout.addWidget(
            session_title
        )

        session_help = QLabel(
            "Select a terminal to follow its location."
        )

        session_help.setStyleSheet(
            """
            QLabel {
                font-size: 11px;
                padding-left: 4px;
                padding-bottom: 4px;
            }
            """
        )

        left_layout.addWidget(
            session_help
        )

        # ----------------------------------------------------
        # Terminal session widget
        # ----------------------------------------------------

        self.session_widget = (
            TerminalSessionWidget()
        )

        self.session_widget.session_selected.connect(
            self.handle_session_selected
        )

        left_layout.addWidget(
            self.session_widget,
            1
        )

        # ----------------------------------------------------
        # Filesystem title
        # ----------------------------------------------------

        filesystem_title = QLabel(
            "📁 LINUXLAB FILESYSTEM"
        )

        filesystem_title.setStyleSheet(
            """
            QLabel {
                font-size: 15px;
                font-weight: bold;
                padding: 4px;
            }
            """
        )

        left_layout.addWidget(
            filesystem_title
        )

        # ----------------------------------------------------
        # Filesystem tree
        # ----------------------------------------------------

        self.tree = QTreeWidget()

        self.tree.setHeaderLabels(
            [
                "LinuxLab Filesystem"
            ]
        )

        self.tree.setAnimated(
            True
        )

        self.tree.setColumnWidth(
            0,
            420
        )

        self.tree.itemClicked.connect(
            self.show_file_details
        )

        left_layout.addWidget(
            self.tree,
            3
        )

        workspace_splitter.addWidget(
            left_panel
        )

        # ====================================================
        # CENTER PANEL
        # ====================================================

        # ====================================================
        # CENTER PANEL (Interactive Visual Workstation)
        # ====================================================

        workstation_panel = QWidget()

        workstation_layout = QVBoxLayout(
            workstation_panel
        )

        workstation_layout.setContentsMargins(
            5,
            0,
            5,
            0
        )

        workstation_layout.setSpacing(
            6
        )

        workstation_title = QLabel(
            "🔬 INTERACTIVE VISUAL LAB"
        )

        workstation_title.setStyleSheet(
            """
            QLabel {
                font-size: 15px;
                font-weight: bold;
                padding: 4px;
            }
            """
        )

        workstation_layout.addWidget(
            workstation_title
        )

        self.workstation_tabs = QTabWidget()
        self.workstation_tabs.setStyleSheet(
            """
            QTabBar::tab {
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            """
        )

        # Tab 1: Permissions & Access Lab
        self.permission_visualizer = PermissionSimulatorWidget()
        self.workstation_tabs.addTab(
            self.permission_visualizer,
            "🔐 Permissions & Access Lab"
        )

        workstation_layout.addWidget(
            self.workstation_tabs,
            1
        )

        workspace_splitter.addWidget(
            workstation_panel
        )

        # ====================================================
        # RIGHT PANEL
        # ====================================================

        activity_panel = QWidget()

        activity_layout = QVBoxLayout(
            activity_panel
        )

        activity_layout.setContentsMargins(
            5,
            0,
            0,
            0
        )

        activity_title = QLabel(
            "🔴 LIVE LINUX ACTIVITY"
        )

        activity_title.setStyleSheet(
            """
            QLabel {
                font-size: 15px;
                font-weight: bold;
                padding: 4px;
            }
            """
        )

        activity_layout.addWidget(
            activity_title
        )

        self.watching_label = QLabel(
            f"Watching: {self.lab_path}"
        )

        self.watching_label.setWordWrap(
            True
        )

        self.watching_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
            }
            """
        )

        activity_layout.addWidget(
            self.watching_label
        )

        self.activity_widget = (
            ActivityTimelineWidget()
        )

        activity_layout.addWidget(
            self.activity_widget
        )

        workspace_splitter.addWidget(
            activity_panel
        )

        # ====================================================
        # Workspace proportions
        # ====================================================

        workspace_splitter.setSizes(
            [
                520,
                430,
                600,
            ]
        )

        # ====================================================
        # Filesystem
        # ====================================================

        self.build_initial_tree()

        # ====================================================
        # Filesystem monitor
        # ====================================================

        self.monitor = FileSystemMonitor(
            self.lab_path,
            self.event_bus
        )

        self.monitor.signals.created.connect(
            self.handle_created
        )

        self.monitor.signals.deleted.connect(
            self.handle_deleted
        )

        self.monitor.signals.modified.connect(
            self.handle_modified
        )

        self.monitor.signals.moved.connect(
            self.handle_moved
        )

        self.monitor.start()

        # ====================================================
        # Event subscriptions
        # ====================================================

        self.subscribe_to_events()

        # ====================================================
        # Start terminal worker
        # ====================================================

        self.session_thread.start()

    # ========================================================
    # Event Bus subscriptions
    # ========================================================

    def subscribe_to_events(
        self
    ):

        filesystem_events = [
            "file.created",
            "file.modified",
            "file.deleted",
            "file.moved",
            "directory.created",
            "directory.deleted",
            "file.permissions_changed",
        ]

        for event_type in filesystem_events:

            self.event_bus.subscribe(
                event_type,
                self.handle_activity_event
            )

        self.event_bus.subscribe(
            "shell.session_created",
            self.handle_shell_session_event
        )

        self.event_bus.subscribe(
            "shell.session_removed",
            self.handle_shell_session_event
        )

        self.event_bus.subscribe(
            "shell.cwd_changed",
            self.handle_shell_cwd_changed
        )

    # ========================================================
    # Generic activity
    # ========================================================

    def handle_activity_event(
        self,
        event
    ):

        self.activity_timeline.record(
            event
        )

        self.activity_widget.add_event(
            event
        )

    # ========================================================
    # Filesystem event from monitor (GUI thread)
    # ========================================================

    def handle_filesystem_event(
        self,
        event
    ):
        """
        Receives filesystem events bridged safely from Watchdog
        via Qt signals onto the GUI thread.
        """
        self.event_bus.publish(
            event
        )

    # ========================================================
    # Dynamic Lab Directory Selection
    # ========================================================

    def change_lab_directory(
        self,
        new_path: Path
    ):
        """
        Dynamically update the watched directory.
        """
        self.lab_path = Path(new_path).resolve()

        if hasattr(self, "watching_label"):
            self.watching_label.setText(
                f"Watching: {self.lab_path}"
            )

        if hasattr(self, "monitor"):
            self.monitor.set_path(
                self.lab_path
            )

        self.build_initial_tree()
        self.update_focused_location_from_snapshot()

    # ========================================================
    # Worker event
    # ========================================================

    def handle_session_event(
        self,
        event
    ):

        # Runs in the GUI thread because the signal from
        # the worker is delivered through Qt.

        self.event_bus.publish(
            event
        )


    # ========================================================
    # Worker state snapshot
    # ========================================================

    def handle_sessions_updated(
        self,
        sessions
    ):

        # Build one GUI-side snapshot.

        if isinstance(sessions, dict):
            self.session_snapshot = sessions
            session_list = list(sessions.values())
        else:
            self.session_snapshot = {
                session.pid: session
                for session in sessions
            }
            session_list = list(sessions)

        # Update session UI.

        self.session_widget.update_sessions(
            session_list
        )

        # Ensure that the focused PID still exists.

        self.ensure_focused_session_exists()

        # Update the focused location from the SAME
        # session snapshot that the session panel displays.

        self.update_focused_location_from_snapshot()


    # ========================================================
    # Worker error
    # ========================================================

    def handle_session_worker_error(
        self,
        message
    ):

        print(
            "Terminal session worker error:",
            message
        )

    # ========================================================
    # Shell session created/removed
    # ========================================================

    def handle_shell_session_event(
        self,
        event
    ):

        self.activity_timeline.record(
            event
        )

        self.activity_widget.add_event(
            event
        )

    # ========================================================
    # Shell CWD changed
    # ========================================================

    def handle_shell_cwd_changed(
        self,
        event
    ):

        self.activity_timeline.record(
            event
        )

        self.activity_widget.add_event(
            event
        )

        pid = event.data.get(
            "pid"
        )

        focused_pid = (
            self.focused_session.pid
        )

        if pid != focused_pid:
            return

        new_path = event.data.get(
            "new_path"
        )

        if not new_path:
            return

        self.set_focused_location(
            Path(new_path)
        )

    # ========================================================
    # Focused session validity
    # ========================================================

    def ensure_focused_session_exists(
        self
    ):

        # No sessions exist.

        if not self.session_snapshot:

            if self.focused_session.has_session():

                self.focused_session.clear()

                self.session_widget.current_pid = None

                self.session_widget.update_focus_markers()

            self.show_unknown_location()

            return

        focused_pid = (
            self.focused_session.pid
        )

        # Current focused session still exists.

        if (
            focused_pid is not None
            and focused_pid in self.session_snapshot
        ):

            return

        # Choose the first available session.

        first_session = next(
            iter(
                self.session_snapshot.values()
            )
        )

        self.focused_session.set_pid(
            first_session.pid
        )

        self.session_widget.current_pid = (
            first_session.pid
        )

        self.session_widget.update_focus_markers()

    # ========================================================
    # Session selection
    # ========================================================

    def handle_session_selected(
        self,
        pid
    ):

        session = (
            self.session_snapshot.get(
                pid
            )
        )

        if session is None:
            return

        self.focused_session.set_pid(
            pid
        )

        self.set_focused_location(
            session.cwd
        )

    # ========================================================
    # Focused location from current snapshot
    # ========================================================

    def update_focused_location_from_snapshot(
        self
    ):

        pid = (
            self.focused_session.pid
        )

        if pid is None:
            return

        session = (
            self.session_snapshot.get(
                pid
            )
        )

        if session is None:

            self.show_unknown_location()

            return

        self.set_focused_location(
            session.cwd
        )

    # ========================================================
    # Set focused location
    # ========================================================

    def set_focused_location(
        self,
        path
    ):

        if path is None:

            self.show_unknown_location()

            return

        try:

            current_directory = Path(
                path
            ).resolve()

        except OSError:

            self.show_unknown_location()

            return

        self.location_label.setText(
            "📍 CURRENT LOCATION: "
            + str(current_directory)
        )

        self.update_breadcrumb(
            current_directory
        )

        self.update_navigation_info(
            current_directory
        )

        self.update_path_anatomy(
            current_directory
        )

        self.highlight_current_directory(
            current_directory
        )

    # ========================================================
    # Unknown location
    # ========================================================

    def show_unknown_location(
        self
    ):

        self.location_label.setText(
            "📍 CURRENT LOCATION: unknown"
        )

        self.breadcrumb_label.setText(
            "/"
        )

        self.navigation_label.setText(
            "Parent: unknown"
        )

        self.path_anatomy_label.setText(
            "Path anatomy: unknown"
        )

    # ========================================================
    # Filesystem tree
    # ========================================================

    def build_initial_tree(
        self
    ):

        self.tree.clear()

        root_name = self.lab_path.name or str(self.lab_path)

        root_item = QTreeWidgetItem(
            [
                f"📁 {root_name}"
            ]
        )

        root_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            str(self.lab_path)
        )

        self.tree.addTopLevelItem(
            root_item
        )

        self.add_directory_contents(
            root_item,
            self.lab_path
        )

        root_item.setExpanded(
            True
        )

        self.tree.expandAll()

    # ========================================================
    # Recursive directory population
    # ========================================================

    def add_directory_contents(
        self,
        parent_item,
        directory
    ):

        try:

            entries = sorted(
                directory.iterdir(),
                key=lambda path: (
                    not path.is_dir() if not path.is_symlink() else True,
                    path.name.lower()
                )
            )

        except (
            PermissionError,
            OSError,
        ):

            return

        for path in entries:

            try:

                if path.is_symlink():

                    icon = "🔗"

                elif path.is_dir():

                    icon = "📁"

                elif path.is_file():

                    icon = "📄"

                elif path.is_fifo():

                    icon = "🪈"

                elif path.is_socket():

                    icon = "🔌"

                elif path.is_block_device():

                    icon = "💾"

                elif path.is_char_device():

                    icon = "📟"

                else:

                    icon = "❓"

            except (OSError, PermissionError):

                icon = "❓"

            item = QTreeWidgetItem(
                [
                    f"{icon} {path.name}"
                ]
            )

            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                str(path)
            )

            parent_item.addChild(
                item
            )

            if path.is_dir() and not path.is_symlink():

                self.add_directory_contents(
                    item,
                    path
                )

    # ========================================================
    # Breadcrumb
    # ========================================================

    def update_breadcrumb(
        self,
        current_directory
    ):

        parts = current_directory.parts

        if not parts:

            breadcrumb = "/"

        else:

            breadcrumb = "  →  ".join(
                parts
            )

        self.breadcrumb_label.setText(
            breadcrumb
        )

    # ========================================================
    # Navigation
    # ========================================================

    def update_navigation_info(
        self,
        current_directory
    ):

        parent = (
            current_directory.parent
        )

        self.navigation_label.setText(
            "Parent: "
            + str(parent)
            + "    |    "
            + "Home: "
            + str(Path.home())
            + "    |    "
            + "Root: /"
        )

    # ========================================================
    # Path anatomy
    # ========================================================

    def update_path_anatomy(
        self,
        current_directory
    ):

        parts = current_directory.parts

        if not parts:

            self.path_anatomy_label.setText(
                "Path anatomy: /"
            )

            return

        pieces = []

        for index, part in enumerate(
            parts
        ):

            if part == "/":

                pieces.append(
                    "ROOT (/)"
                )

            else:

                pieces.append(
                    f"{index}: {part}"
                )

        self.path_anatomy_label.setText(
            "Path anatomy: "
            + "  |  ".join(
                pieces
            )
        )

    # ========================================================
    # Highlight current directory
    # ========================================================

    def highlight_current_directory(
        self,
        current_directory
    ):

        root = (
            self.tree.invisibleRootItem()
        )

        for index in range(
            root.childCount()
        ):

            item = root.child(
                index
            )

            self.clear_current_highlight(
                item
            )

            self.find_and_highlight(
                item,
                current_directory
            )

    # ========================================================
    # Find and highlight
    # ========================================================

    def find_and_highlight(
        self,
        item,
        current_directory
    ):

        item_path = item.data(
            0,
            Qt.ItemDataRole.UserRole
        )

        if item_path:

            try:

                item_path = Path(
                    item_path
                ).resolve()

                if item_path == current_directory:

                    name = (
                        item_path.name
                        or str(item_path)
                    )

                    if item_path.is_dir():

                        item.setText(
                            0,
                            "🟢 📁 "
                            + name
                            + "  ← YOU ARE HERE"
                        )

                    else:

                        item.setText(
                            0,
                            "🟢 "
                            + name
                            + "  ← YOU ARE HERE"
                        )

                    item.setExpanded(
                        True
                    )

                    return True

            except OSError:

                pass

        for index in range(
            item.childCount()
        ):

            child = item.child(
                index
            )

            if self.find_and_highlight(
                child,
                current_directory
            ):

                item.setExpanded(
                    True
                )

                return True

        return False

    # ========================================================
    # Clear current highlight
    # ========================================================

    def clear_current_highlight(
        self,
        item
    ):

        path = item.data(
            0,
            Qt.ItemDataRole.UserRole
        )

        if path:

            path_obj = Path(
                path
            )

            if path_obj.is_symlink():

                icon = "🔗"

            elif path_obj.is_dir():

                icon = "📁"

            elif path_obj.is_file():

                icon = "📄"

            else:

                icon = "❓"

            name = (
                path_obj.name
                or str(path_obj)
            )

            item.setText(
                0,
                f"{icon} {name}"
            )

        for index in range(
            item.childCount()
        ):

            self.clear_current_highlight(
                item.child(index)
            )

    # ========================================================
    # Show selected filesystem object
    # ========================================================

    def show_file_details(
        self,
        item,
        column
    ):

        path = item.data(
            0,
            Qt.ItemDataRole.UserRole
        )

        if not path:
            return

        self.selected_path = Path(
            path
        )

        self.refresh_selected_details()

    # ========================================================
    # Refresh selected details
    # ========================================================

    def refresh_selected_details(
        self
    ):

        if self.selected_path is None:

            self.clear_details()

            return

        fs_object = FilesystemObject.from_path(
            self.selected_path
        )

        if fs_object is None:

            self.clear_details()

            self.selected_path = None

            return

        self.update_file_details(
            fs_object
        )

    # ========================================================
    # Visualizer dispatch
    # ========================================================

    def update_file_details(
        self,
        fs_object: FilesystemObject
    ):

        self.permission_visualizer.set_context(
            fs_object
        )

    # ========================================================
    # Clear metadata
    # ========================================================

    def clear_details(
        self
    ):

        self.permission_visualizer.clear_context()


    # ========================================================
    # Filesystem created
    # ========================================================

    def handle_created(
        self,
        path,
        is_directory
    ):

        self.refresh_tree()

        self.refresh_selected_details()

    # ========================================================
    # Filesystem deleted
    # ========================================================

    def handle_deleted(
        self,
        path,
        is_directory
    ):

        deleted_path = Path(
            path
        )

        if self.selected_path:

            try:

                if (
                    self.selected_path.resolve()
                    == deleted_path.resolve()
                ):

                    self.selected_path = None

            except OSError:

                pass

        self.refresh_tree()

        self.refresh_selected_details()

    # ========================================================
    # Filesystem modified
    # ========================================================

    def handle_modified(
        self,
        path
    ):

        self.refresh_tree()

        if self.selected_path is None:
            return

        try:

            changed_path = Path(
                path
            ).resolve()

            selected_path = (
                self.selected_path.resolve()
            )

            if changed_path == selected_path:

                self.refresh_selected_details()

        except OSError:

            pass

    # ========================================================
    # Filesystem moved
    # ========================================================

    def handle_moved(
        self,
        old_path,
        new_path
    ):

        old_path_obj = Path(
            old_path
        )

        new_path_obj = Path(
            new_path
        )

        if self.selected_path:

            try:

                if (
                    self.selected_path.resolve()
                    == old_path_obj.resolve()
                ):

                    self.selected_path = (
                        new_path_obj
                    )

            except OSError:

                pass

        self.refresh_tree()

        self.refresh_selected_details()

    # ========================================================
    # Refresh tree
    # ========================================================

    def refresh_tree(
        self
    ):

        self.build_initial_tree()

        self.update_focused_location_from_snapshot()

    # ========================================================
    # Shutdown
    # ========================================================

    def closeEvent(
        self,
        event
    ):

        # ----------------------------------------------------
        # Stop GUI-side state
        # ----------------------------------------------------

        if hasattr(
            self,
            "monitor"
        ):

            self.monitor.stop()

        # ----------------------------------------------------
        # Stop the worker's QTimer IN THE WORKER THREAD.
        #
        # BlockingQueuedConnection waits until stop()
        # has actually executed in the worker thread.
        # ----------------------------------------------------

        if hasattr(
            self,
            "session_worker"
        ):

            if hasattr(
                self,
                "session_thread"
            ):

                if self.session_thread.isRunning():

                    try:

                        QMetaObject.invokeMethod(
                            self.session_worker,
                            "stop",
                            Qt.ConnectionType.BlockingQueuedConnection
                        )

                    except Exception as error:

                        print(
                            "Worker stop error:",
                            error
                        )

        # ----------------------------------------------------
        # Stop worker thread
        # ----------------------------------------------------

        if hasattr(
            self,
            "session_thread"
        ):

            if self.session_thread.isRunning():

                self.session_thread.quit()

                if not self.session_thread.wait(
                    2000
                ):

                    print(
                        "Warning: "
                        "session thread did not stop cleanly."
                    )

        event.accept()


# ============================================================
# Application entry point
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    window = MainWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":

    sys.exit(
        main()
    )
