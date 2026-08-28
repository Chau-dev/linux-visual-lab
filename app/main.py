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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QFormLayout,
    QGridLayout,
    QSplitter,
    QFrame,
)

from app.core.event_bus import EventBus
from app.core.activity import ActivityTimeline

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


# ============================================================
# Configuration
# ============================================================

LAB_PATH = Path(
    "/home/dev/LinuxLab"
)


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

        self.session_thread = QThread(
            self
        )

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
        # Current location
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

        details_panel = QWidget()

        details_layout = QVBoxLayout(
            details_panel
        )

        details_layout.setContentsMargins(
            5,
            0,
            5,
            0
        )

        # ----------------------------------------------------
        # Selected object title
        # ----------------------------------------------------

        details_title = QLabel(
            "📄 SELECTED OBJECT"
        )

        details_title.setStyleSheet(
            """
            QLabel {
                font-size: 15px;
                font-weight: bold;
                padding: 4px;
            }
            """
        )

        details_layout.addWidget(
            details_title
        )

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        metadata_widget = QWidget()

        metadata_layout = QFormLayout(
            metadata_widget
        )

        metadata_layout.setContentsMargins(
            4,
            4,
            4,
            4
        )

        metadata_layout.setSpacing(
            5
        )

        self.detail_name = QLabel("-")
        self.detail_type = QLabel("-")
        self.detail_path = QLabel("-")
        self.detail_parent = QLabel("-")
        self.detail_name_only = QLabel("-")
        self.detail_size = QLabel("-")
        self.detail_owner = QLabel("-")
        self.detail_group = QLabel("-")
        self.detail_permissions = QLabel("-")
        self.detail_mode = QLabel("-")
        self.detail_modified = QLabel("-")

        self.detail_path.setWordWrap(
            True
        )

        self.detail_parent.setWordWrap(
            True
        )

        metadata_layout.addRow(
            "Name:",
            self.detail_name
        )

        metadata_layout.addRow(
            "Type:",
            self.detail_type
        )

        metadata_layout.addRow(
            "Path:",
            self.detail_path
        )

        metadata_layout.addRow(
            "Parent:",
            self.detail_parent
        )

        metadata_layout.addRow(
            "Name only:",
            self.detail_name_only
        )

        metadata_layout.addRow(
            "Size:",
            self.detail_size
        )

        metadata_layout.addRow(
            "Owner:",
            self.detail_owner
        )

        metadata_layout.addRow(
            "Group:",
            self.detail_group
        )

        metadata_layout.addRow(
            "Permissions:",
            self.detail_permissions
        )

        metadata_layout.addRow(
            "Mode:",
            self.detail_mode
        )

        metadata_layout.addRow(
            "Modified:",
            self.detail_modified
        )

        details_layout.addWidget(
            metadata_widget
        )

        # ----------------------------------------------------
        # Permission title
        # ----------------------------------------------------

        permissions_title = QLabel(
            "🔐 PERMISSION VISUALIZER"
        )

        permissions_title.setStyleSheet(
            """
            QLabel {
                font-size: 15px;
                font-weight: bold;
                padding-top: 12px;
                padding-bottom: 6px;
            }
            """
        )

        details_layout.addWidget(
            permissions_title
        )

        # ----------------------------------------------------
        # Permission grid
        # ----------------------------------------------------

        permission_grid_widget = QWidget()

        self.permission_grid = QGridLayout(
            permission_grid_widget
        )

        self.permission_grid.setContentsMargins(
            4,
            4,
            4,
            4
        )

        self.permission_grid.setHorizontalSpacing(
            12
        )

        headers = [
            "",
            "OWNER",
            "GROUP",
            "OTHER",
        ]

        for column, header in enumerate(
            headers
        ):

            label = QLabel(
                header
            )

            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label.setStyleSheet(
                "font-weight: bold;"
            )

            self.permission_grid.addWidget(
                label,
                0,
                column
            )

        permission_names = [
            "READ",
            "WRITE",
            "EXECUTE",
        ]

        self.permission_cells = {}

        for row, permission_name in enumerate(
            permission_names,
            start=1
        ):

            label = QLabel(
                permission_name
            )

            label.setStyleSheet(
                "font-weight: bold;"
            )

            self.permission_grid.addWidget(
                label,
                row,
                0
            )

            for column, category in enumerate(
                [
                    "owner",
                    "group",
                    "other",
                ],
                start=1
            ):

                value = QLabel(
                    "—"
                )

                value.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                value.setMinimumWidth(
                    60
                )

                self.permission_grid.addWidget(
                    value,
                    row,
                    column
                )

                self.permission_cells[
                    (
                        permission_name,
                        category
                    )
                ] = value

        details_layout.addWidget(
            permission_grid_widget
        )

        # ----------------------------------------------------
        # Permission explanations
        # ----------------------------------------------------

        self.permission_symbolic = QLabel(
            "Symbolic: -"
        )

        self.permission_numeric = QLabel(
            "Numeric: -"
        )

        self.permission_math = QLabel(
            "Permission math: -"
        )

        self.permission_math.setWordWrap(
            True
        )

        details_layout.addWidget(
            self.permission_symbolic
        )

        details_layout.addWidget(
            self.permission_numeric
        )

        details_layout.addWidget(
            self.permission_math
        )

        details_layout.addStretch(
            1
        )

        workspace_splitter.addWidget(
            details_panel
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

        watching_label = QLabel(
            f"Watching: {LAB_PATH}"
        )

        watching_label.setWordWrap(
            True
        )

        watching_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
            }
            """
        )

        activity_layout.addWidget(
            watching_label
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
            LAB_PATH,
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

        self.session_snapshot = {
            session.pid: session
            for session in sessions
        }

        # Update session UI.

        self.session_widget.update_sessions(
            sessions
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

        root_item = QTreeWidgetItem(
            [
                "📁 LinuxLab"
            ]
        )

        root_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            str(LAB_PATH)
        )

        self.tree.addTopLevelItem(
            root_item
        )

        self.add_directory_contents(
            root_item,
            LAB_PATH
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
                    not path.is_dir(),
                    path.name.lower()
                )
            )

        except (
            PermissionError,
            OSError,
        ):

            return

        for path in entries:

            if path.name == ".current_directory":
                continue

            if path.is_symlink():

                icon = "🔗"

            elif path.is_dir():

                icon = "📁"

            elif path.is_file():

                icon = "📄"

            else:

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

            if path.is_dir():

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

        self.update_file_details(
            self.selected_path
        )

    # ========================================================
    # Refresh selected details
    # ========================================================

    def refresh_selected_details(
        self
    ):

        if self.selected_path is None:
            return

        if not self.selected_path.exists():

            self.clear_details()

            self.selected_path = None

            return

        self.update_file_details(
            self.selected_path
        )

    # ========================================================
    # File metadata
    # ========================================================

    def update_file_details(
        self,
        path
    ):

        try:

            info = os.stat(
                path
            )

        except OSError as error:

            self.clear_details()

            self.detail_name.setText(
                "Unavailable"
            )

            self.detail_type.setText(
                str(error)
            )

            return

        path_obj = Path(
            path
        )

        self.detail_name.setText(
            path_obj.name
            or str(path_obj)
        )

        if path_obj.is_symlink():

            file_type = "Symbolic link"

        elif path_obj.is_dir():

            file_type = "Directory"

        elif path_obj.is_file():

            file_type = "Regular file"

        else:

            file_type = "Other"

        self.detail_type.setText(
            file_type
        )

        self.detail_path.setText(
            str(path_obj)
        )

        self.detail_parent.setText(
            str(path_obj.parent)
        )

        self.detail_name_only.setText(
            path_obj.name
        )

        self.detail_size.setText(
            f"{info.st_size:,} bytes"
        )

        try:

            import pwd

            owner = pwd.getpwuid(
                info.st_uid
            ).pw_name

        except Exception:

            owner = str(
                info.st_uid
            )

        self.detail_owner.setText(
            owner
        )

        try:

            import grp

            group = grp.getgrgid(
                info.st_gid
            ).gr_name

        except Exception:

            group = str(
                info.st_gid
            )

        self.detail_group.setText(
            group
        )

        permissions = stat.filemode(
            info.st_mode
        )

        self.detail_permissions.setText(
            permissions
        )

        self.permission_symbolic.setText(
            "Symbolic: "
            + permissions
        )

        permission_mode = (
            info.st_mode & 0o777
        )

        self.detail_mode.setText(
            oct(permission_mode)
        )

        self.update_permission_visualizer(
            permission_mode
        )

        self.update_permission_math(
            permission_mode
        )

        modified = datetime.fromtimestamp(
            info.st_mtime
        )

        self.detail_modified.setText(
            modified.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    # ========================================================
    # Clear metadata
    # ========================================================

    def clear_details(
        self
    ):

        self.detail_name.setText("-")
        self.detail_type.setText("-")
        self.detail_path.setText("-")
        self.detail_parent.setText("-")
        self.detail_name_only.setText("-")
        self.detail_size.setText("-")
        self.detail_owner.setText("-")
        self.detail_group.setText("-")
        self.detail_permissions.setText("-")
        self.detail_mode.setText("-")
        self.detail_modified.setText("-")

        self.permission_symbolic.setText(
            "Symbolic: -"
        )

        self.permission_numeric.setText(
            "Numeric: -"
        )

        self.permission_math.setText(
            "Permission math: -"
        )

        for cell in (
            self.permission_cells.values()
        ):

            cell.setText(
                "—"
            )

    # ========================================================
    # Permission visualizer
    # ========================================================

    def update_permission_visualizer(
        self,
        mode
    ):

        owner = (
            mode >> 6
        ) & 7

        group = (
            mode >> 3
        ) & 7

        other = mode & 7

        values = {
            "owner": owner,
            "group": group,
            "other": other,
        }

        permission_bits = {
            "READ": 4,
            "WRITE": 2,
            "EXECUTE": 1,
        }

        for permission_name, bit in (
            permission_bits.items()
        ):

            for category, value in (
                values.items()
            ):

                cell = self.permission_cells[
                    (
                        permission_name,
                        category
                    )
                ]

                if value & bit:

                    cell.setText(
                        "✓"
                    )

                else:

                    cell.setText(
                        "✗"
                    )

        self.permission_numeric.setText(
            "Numeric: "
            + f"{owner}{group}{other}"
        )

    # ========================================================
    # Permission mathematics
    # ========================================================

    def update_permission_math(
        self,
        mode
    ):

        owner = (
            mode >> 6
        ) & 7

        group = (
            mode >> 3
        ) & 7

        other = mode & 7

        def explain(
            value
        ):

            parts = []

            if value & 4:

                parts.append(
                    "4 (READ)"
                )

            if value & 2:

                parts.append(
                    "2 (WRITE)"
                )

            if value & 1:

                parts.append(
                    "1 (EXECUTE)"
                )

            if not parts:

                parts.append(
                    "0"
                )

            return " + ".join(
                parts
            )

        text = (
            "Permission math:\n"
            f"OWNER = {explain(owner)} = {owner}\n"
            f"GROUP = {explain(group)} = {group}\n"
            f"OTHER = {explain(other)} = {other}"
        )

        self.permission_math.setText(
            text
        )

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
