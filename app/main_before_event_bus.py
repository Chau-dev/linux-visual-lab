import sys
import os
import stat

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QLabel,
    QWidget,
)

from app.monitors.filesystem import FileSystemMonitor
from app.session.current_directory import get_current_directory


# ============================================================
# Configuration
# ============================================================

LAB_PATH = Path("/home/dev/LinuxLab")


# ============================================================
# Main Window
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Linux Visual Learning Lab"
        )

        self.resize(1250, 800)

        # ====================================================
        # Main container
        # ====================================================

        central = QWidget()

        main_layout = QVBoxLayout(
            central
        )

        self.setCentralWidget(
            central
        )

        # ====================================================
        # Current location
        # ====================================================

        self.location_label = QLabel(
            "📍 CURRENT LOCATION: unknown"
        )

        self.location_label.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
                padding: 8px;
            }
            """
        )

        main_layout.addWidget(
            self.location_label
        )

        # ====================================================
        # Breadcrumb
        # ====================================================

        self.breadcrumb_label = QLabel(
            "/"
        )

        self.breadcrumb_label.setWordWrap(
            True
        )

        self.breadcrumb_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                padding: 4px 10px;
            }
            """
        )

        main_layout.addWidget(
            self.breadcrumb_label
        )

        # ====================================================
        # Navigation information
        # ====================================================

        self.navigation_label = QLabel(
            "Parent: /"
        )

        self.navigation_label.setWordWrap(
            True
        )

        self.navigation_label.setStyleSheet(
            """
            QLabel {
                font-size: 13px;
                padding: 4px 10px;
            }
            """
        )

        main_layout.addWidget(
            self.navigation_label
        )

        # ====================================================
        # Path anatomy
        # ====================================================

        self.path_anatomy_label = QLabel(
            "Path anatomy: /"
        )

        self.path_anatomy_label.setWordWrap(
            True
        )

        self.path_anatomy_label.setStyleSheet(
            """
            QLabel {
                font-size: 13px;
                padding: 4px 10px;
            }
            """
        )

        main_layout.addWidget(
            self.path_anatomy_label
        )

        # ====================================================
        # Main content
        # ====================================================

        content_layout = QHBoxLayout()

        # ====================================================
        # Filesystem tree
        # ====================================================

        self.tree = QTreeWidget()

        self.tree.setHeaderLabels(
            ["LinuxLab Filesystem"]
        )

        self.tree.setAnimated(
            True
        )

        self.tree.setColumnWidth(
            0,
            500
        )

        self.tree.itemClicked.connect(
            self.show_file_details
        )

        content_layout.addWidget(
            self.tree,
            2
        )

        # ====================================================
        # Details panel
        # ====================================================

        details_widget = QWidget()

        details_layout = QFormLayout(
            details_widget
        )

        # ====================================================
        # Basic metadata
        # ====================================================

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

        details_layout.addRow(
            "Name:",
            self.detail_name
        )

        details_layout.addRow(
            "Type:",
            self.detail_type
        )

        details_layout.addRow(
            "Path:",
            self.detail_path
        )

        details_layout.addRow(
            "Parent:",
            self.detail_parent
        )

        details_layout.addRow(
            "Name only:",
            self.detail_name_only
        )

        details_layout.addRow(
            "Size:",
            self.detail_size
        )

        details_layout.addRow(
            "Owner:",
            self.detail_owner
        )

        details_layout.addRow(
            "Group:",
            self.detail_group
        )

        details_layout.addRow(
            "Permissions:",
            self.detail_permissions
        )

        details_layout.addRow(
            "Mode:",
            self.detail_mode
        )

        details_layout.addRow(
            "Modified:",
            self.detail_modified
        )

        # ====================================================
        # Permission visualizer
        # ====================================================

        permissions_title = QLabel(
            "PERMISSION VISUALIZER"
        )

        permissions_title.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding-top: 15px;
                padding-bottom: 5px;
            }
            """
        )

        details_layout.addRow(
            permissions_title
        )

        permission_grid_widget = QWidget()

        self.permission_grid = QGridLayout(
            permission_grid_widget
        )

        self.permission_grid.setContentsMargins(
            0,
            0,
            0,
            0
        )

        headers = [
            "",
            "OWNER",
            "GROUP",
            "OTHER",
        ]

        for column, header in enumerate(headers):

            label = QLabel(header)

            label.setStyleSheet(
                "font-weight: bold;"
            )

            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
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
                ["owner", "group", "other"],
                start=1
            ):

                value = QLabel("—")

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
                    (permission_name, category)
                ] = value

        details_layout.addRow(
            permission_grid_widget
        )

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

        details_layout.addRow(
            self.permission_symbolic
        )

        details_layout.addRow(
            self.permission_numeric
        )

        details_layout.addRow(
            self.permission_math
        )

        content_layout.addWidget(
            details_widget,
            1
        )

        main_layout.addLayout(
            content_layout
        )

        # ====================================================
        # Initial filesystem tree
        # ====================================================

        self.build_initial_tree()

        # ====================================================
        # Filesystem monitor
        # ====================================================

        self.monitor = FileSystemMonitor(
            LAB_PATH
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
        # Current directory timer
        # Temporary prototype
        # ====================================================

        self.location_timer = QTimer(
            self
        )

        self.location_timer.timeout.connect(
            self.update_current_location
        )

        self.location_timer.start(
            500
        )

        self.update_current_location()

    # ========================================================
    # Filesystem tree
    # ========================================================

    def build_initial_tree(self):

        self.tree.clear()

        root_item = QTreeWidgetItem(
            ["📁 LinuxLab"]
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

            # Hide temporary communication file.

            if path.name == ".current_directory":

                continue

            # Determine icon.

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
    # Current location
    # ========================================================

    def update_current_location(
        self
    ):

        current_directory = (
            get_current_directory()
        )

        if current_directory is None:

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

            return

        try:

            current_directory = Path(
                current_directory
            ).resolve()

        except OSError:

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
    # Navigation info
    # ========================================================

    def update_navigation_info(
        self,
        current_directory
    ):

        parent = current_directory.parent

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

        for index, part in enumerate(parts):

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
            + "  |  ".join(pieces)
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
    # Find current directory
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

            path_obj = Path(path)

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
    # File / directory details
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

        path_obj = Path(path)

        # Name

        self.detail_name.setText(
            path_obj.name
            or str(path_obj)
        )

        # Type

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

        # Path

        self.detail_path.setText(
            str(path_obj)
        )

        # Parent

        self.detail_parent.setText(
            str(path_obj.parent)
        )

        # Name only

        self.detail_name_only.setText(
            path_obj.name
        )

        # Size

        self.detail_size.setText(
            f"{info.st_size:,} bytes"
        )

        # Owner

        try:

            import pwd

            owner = (
                pwd.getpwuid(
                    info.st_uid
                ).pw_name
            )

        except Exception:

            owner = str(
                info.st_uid
            )

        self.detail_owner.setText(
            owner
        )

        # Group

        try:

            import grp

            group = (
                grp.getgrgid(
                    info.st_gid
                ).gr_name
            )

        except Exception:

            group = str(
                info.st_gid
            )

        self.detail_group.setText(
            group
        )

        # Symbolic permissions

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

        # Numeric permissions

        permission_mode = (
            info.st_mode & 0o777
        )

        self.detail_mode.setText(
            oct(permission_mode)
        )

        # Permission visualizer

        self.update_permission_visualizer(
            permission_mode
        )

        # Permission mathematics

        self.update_permission_math(
            permission_mode
        )

        # Modified time

        modified = datetime.fromtimestamp(
            info.st_mtime
        )

        self.detail_modified.setText(
            modified.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    # ========================================================
    # Clear details
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

                    cell.setText("✓")

                else:

                    cell.setText("✗")

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

        def explain(value):

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
    # Filesystem events
    # ========================================================

    def handle_created(
        self,
        path,
        is_directory
    ):

        self.refresh_tree()

    def handle_deleted(
        self,
        path,
        is_directory
    ):

        self.refresh_tree()

    def handle_modified(
        self,
        path
    ):

        self.refresh_tree()

    def handle_moved(
        self,
        old_path,
        new_path
    ):

        self.refresh_tree()

    # ========================================================
    # Refresh
    # ========================================================

    def refresh_tree(
        self
    ):

        self.build_initial_tree()

        self.update_current_location()

    # ========================================================
    # Shutdown
    # ========================================================

    def closeEvent(
        self,
        event
    ):

        self.monitor.stop()

        self.location_timer.stop()

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
