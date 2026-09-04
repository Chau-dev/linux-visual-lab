import math
import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QRect, QSize
from PySide6.QtGui import QPainter, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QFrame,
    QScrollArea,
    QSpinBox,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from app.core.models import FilesystemObject, AccessEvaluationResult
from app.visualizers.base import BaseVisualizer


class FilesystemTreeDelegate(QStyledItemDelegate):
    """
    Custom item delegate for FilesystemTreeWidget:
    - Renders the pointing finger emoji 👈 with a larger, prominent font size (18pt).
    - Animates a smooth horizontal pointing/nudging motion directed towards the active directory name.
    - Seamlessly preserves native selection, alternating backgrounds, and standard text metrics.
    """

    def __init__(self, tree: QTreeWidget):
        super().__init__(tree)
        self.tree = tree
        self._anim_phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _on_tick(self):
        self._anim_phase = (self._anim_phase + 0.12) % (2 * math.pi)
        if self.tree.isVisible() and getattr(self.tree, "_current_highlight_path", None) is not None:
            self.tree.viewport().update()

    def stop(self):
        if hasattr(self, "_timer") and self._timer.isActive():
            self._timer.stop()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), 26))
        return size

    def initStyleOption(self, option: QStyleOptionViewItem, index):
        super().initStyleOption(option, index)
        raw_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if "👈" in raw_text:
            option.text = raw_text.replace("👈", "").strip()

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        raw_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        has_pointer = "👈" in raw_text

        super().paint(painter, option, index)

        if has_pointer:
            painter.save()
            base_text = raw_text.replace("👈", "").strip()
            text_width = option.fontMetrics.horizontalAdvance(base_text)
            # Smooth pointing nudge towards the left (folder name)
            nudge = -7.0 * (0.5 + 0.5 * math.sin(self._anim_phase))

            emoji_font = QFont(option.font)
            emoji_font.setPointSize(18)
            painter.setFont(emoji_font)

            emoji_x = option.rect.left() + 8 + text_width + 12 + nudge
            emoji_rect = QRect(int(emoji_x), option.rect.top() - 2, 40, option.rect.height() + 4)
            painter.drawText(emoji_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "👈")
            painter.restore()


class FilesystemTreeWidget(QTreeWidget):
    """
    Displays the directory hierarchy of the watched Linux directory.
    Visualizes folder expansion/opening states and maintains the dynamic location highlight.
    """

    object_selected = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setHeaderLabels(["LinuxLab Filesystem"])
        self.setAnimated(True)
        self.setColumnWidth(0, 380)

        self.tree_delegate = FilesystemTreeDelegate(self)
        self.setItemDelegate(self.tree_delegate)

        self.itemClicked.connect(self._handle_item_clicked)
        self.itemExpanded.connect(self._handle_item_expanded)
        self.itemCollapsed.connect(self._handle_item_collapsed)

        self._current_highlight_path: Path | None = None
        self._watched_root: Path | None = None

    def _handle_item_clicked(self, item: QTreeWidgetItem, column: int):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if path_str:
            self.object_selected.emit(Path(path_str))

    def _handle_item_expanded(self, item: QTreeWidgetItem):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        p = Path(path_str)
        if p.is_dir() and not p.is_symlink():
            if self._current_highlight_path and p.resolve() == self._current_highlight_path.resolve():
                name = p.name or str(p)
                item.setText(0, f"🟢 📂 {name}  👈")
            else:
                name = p.name or str(p)
                item.setText(0, f"📂 {name}")

    def _handle_item_collapsed(self, item: QTreeWidgetItem):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        p = Path(path_str)
        if p.is_dir() and not p.is_symlink():
            if self._current_highlight_path and p.resolve() == self._current_highlight_path.resolve():
                name = p.name or str(p)
                item.setText(0, f"🟢 📁 {name}  👈")
            else:
                name = p.name or str(p)
                item.setText(0, f"📁 {name}")

    def build_tree(self, root_path: Path):
        """Build tree recursively from real filesystem entries."""
        self._watched_root = Path(root_path).resolve()
        self.clear()

        root_name = self._watched_root.name or str(self._watched_root)
        root_item = QTreeWidgetItem([f"📂 {root_name}"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(self._watched_root))

        self.addTopLevelItem(root_item)
        self._add_directory_contents(root_item, self._watched_root)
        root_item.setExpanded(True)

        if self._current_highlight_path:
            target = self._current_highlight_path
            self._current_highlight_path = None
            self.highlight_current_directory(target)

    def _add_directory_contents(self, parent_item: QTreeWidgetItem, directory: Path):
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda p: (
                    not p.is_dir() if not p.is_symlink() else True,
                    p.name.lower(),
                ),
            )
        except (PermissionError, OSError):
            return

        for path in entries:
            icon = "❓"
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
            except (OSError, PermissionError):
                icon = "❓"

            item = QTreeWidgetItem([f"{icon} {path.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            parent_item.addChild(item)

            if path.is_dir() and not path.is_symlink():
                self._add_directory_contents(item, path)

    def highlight_current_directory(self, current_directory: Path | None):
        """Highlight the focused shell's current working directory and reveal its folder contents."""
        target_resolved = current_directory.resolve() if current_directory else None
        current_resolved = self._current_highlight_path.resolve() if self._current_highlight_path else None
        if target_resolved == current_resolved and self._current_highlight_path is not None:
            return

        self._current_highlight_path = current_directory
        root = self.invisibleRootItem()

        for index in range(root.childCount()):
            item = root.child(index)
            self._clear_item_highlight(item)
            if target_resolved:
                self._find_and_highlight(item, target_resolved)

    def _find_and_highlight(self, item: QTreeWidgetItem, current_directory: Path) -> bool:
        item_path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if item_path_str:
            try:
                item_path = Path(item_path_str).resolve()
                if item_path == current_directory:
                    name = item_path.name or str(item_path)
                    icon = "📂" if item.isExpanded() else "📁"
                    item.setText(0, f"🟢 {icon} {name}  👈")
                    item.setExpanded(True)
                    return True
            except OSError:
                pass

        for index in range(item.childCount()):
            child = item.child(index)
            if self._find_and_highlight(child, current_directory):
                item.setExpanded(True)
                return True
        return False

    def _clear_item_highlight(self, item: QTreeWidgetItem):
        path_str = item.data(0, Qt.ItemDataRole.UserRole)
        if path_str:
            p = Path(path_str)
            if p.is_dir() and not p.is_symlink():
                icon = "📂" if item.isExpanded() else "📁"
            elif p.is_symlink():
                icon = "🔗"
            else:
                icon = "📄"
            name = p.name or str(p)
            item.setText(0, f"{icon} {name}")
            item.setData(0, Qt.ItemDataRole.BackgroundRole, None)

        for index in range(item.childCount()):
            self._clear_item_highlight(item.child(index))

    def select_path(self, target_path: Path) -> bool:
        """Find and select the item corresponding to target_path."""
        root = self.invisibleRootItem()
        try:
            target_resolved = target_path.resolve()
        except OSError:
            return False

        def _find_and_select(item: QTreeWidgetItem) -> bool:
            path_str = item.data(0, Qt.ItemDataRole.UserRole)
            if path_str:
                try:
                    if Path(path_str).resolve() == target_resolved:
                        self.setCurrentItem(item)
                        return True
                except OSError:
                    pass
            for idx in range(item.childCount()):
                if _find_and_select(item.child(idx)):
                    return True
            return False

        for idx in range(root.childCount()):
            if _find_and_select(root.child(idx)):
                return True
        return False

    def closeEvent(self, event):
        if hasattr(self, "tree_delegate"):
            self.tree_delegate.stop()
        super().closeEvent(event)


class SelectedObjectInspectorWidget(BaseVisualizer):
    """
    Selected Object Inspector:
    Reads real POSIX state using os.lstat() -> FilesystemObject and explains:
      - Metadata, Inode, Size, Timestamps
      - Real Linux Ownership (UID / GID)
      - POSIX 3x3 Permissions Matrix (Owner/Group/Other x Read/Write/Execute)
      - Octal Arithmetic Decomposition (e.g., 644 -> 4+2, 4+0, 4+0)
      - Symbolic Mode and Special bits (SUID, SGID, Sticky)
      - Linux Kernel 3-step DAC evaluation explanation
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.content_layout.setSpacing(10)

        # ----------------------------------------------------
        # 1. Header Card
        # ----------------------------------------------------
        self.header_frame = QFrame()
        self.header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QVBoxLayout(self.header_frame)
        header_layout.setSpacing(4)

        self.name_label = QLabel("No object selected")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        header_layout.addWidget(self.name_label)

        self.type_badge = QLabel("Select an item in the filesystem tree to inspect its Linux metadata.")
        self.type_badge.setStyleSheet("color: #aaa; font-size: 12px;")
        self.type_badge.setWordWrap(True)
        header_layout.addWidget(self.type_badge)

        self.content_layout.addWidget(self.header_frame)

        # ----------------------------------------------------
        # 2. POSIX Metadata Card
        # ----------------------------------------------------
        self.meta_group = QGroupBox("📋 POSIX Inode & Identity")
        meta_form = QFormLayout(self.meta_group)
        meta_form.setSpacing(6)

        self.lbl_path = QLabel("-")
        self.lbl_path.setWordWrap(True)
        self.lbl_size = QLabel("-")
        self.lbl_inode = QLabel("-")
        self.lbl_links = QLabel("-")
        self.lbl_modified = QLabel("-")
        self.lbl_owner = QLabel("-")

        meta_form.addRow("<b>Absolute Path:</b>", self.lbl_path)
        meta_form.addRow("<b>File Size:</b>", self.lbl_size)
        meta_form.addRow("<b>Inode / Links:</b>", self.lbl_inode)
        meta_form.addRow("<b>Ownership:</b>", self.lbl_owner)
        meta_form.addRow("<b>Last Modified:</b>", self.lbl_modified)

        self.content_layout.addWidget(self.meta_group)

        # ----------------------------------------------------
        # 3. Permissions Breakdown & Octal Arithmetic
        # ----------------------------------------------------
        self.perm_group = QGroupBox("🔐 POSIX Permissions & Octal Arithmetic")
        perm_layout = QVBoxLayout(self.perm_group)
        perm_layout.setSpacing(8)

        # Symbolic + Octal banner
        self.mode_banner = QLabel("Mode: ---- | Octal: ----")
        self.mode_banner.setStyleSheet(
            """
            QLabel {
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                background-color: rgba(52, 152, 219, 0.15);
                color: #5dade2;
                border: 1px solid #2980b9;
                border-radius: 4px;
                padding: 6px 10px;
            }
            """
        )
        perm_layout.addWidget(self.mode_banner)

        # 3x3 Matrix
        matrix_frame = QFrame()
        matrix_layout = QGridLayout(matrix_frame)
        matrix_layout.setSpacing(4)

        # Headers
        matrix_layout.addWidget(QLabel("<b>CLASS</b>"), 0, 0)
        matrix_layout.addWidget(QLabel("<b>READ (4)</b>"), 0, 1, Qt.AlignmentFlag.AlignCenter)
        matrix_layout.addWidget(QLabel("<b>WRITE (2)</b>"), 0, 2, Qt.AlignmentFlag.AlignCenter)
        matrix_layout.addWidget(QLabel("<b>EXECUTE (1)</b>"), 0, 3, Qt.AlignmentFlag.AlignCenter)
        matrix_layout.addWidget(QLabel("<b>OCTAL SUM</b>"), 0, 4, Qt.AlignmentFlag.AlignCenter)

        # Rows: Owner, Group, Other
        self.cell_owner = [QLabel("<b>OWNER (u)</b>"), QLabel("-"), QLabel("-"), QLabel("-"), QLabel("-")]
        self.cell_group = [QLabel("<b>GROUP (g)</b>"), QLabel("-"), QLabel("-"), QLabel("-"), QLabel("-")]
        self.cell_other = [QLabel("<b>OTHER (o)</b>"), QLabel("-"), QLabel("-"), QLabel("-"), QLabel("-")]

        for row_idx, row_cells in enumerate([self.cell_owner, self.cell_group, self.cell_other], start=1):
            for col_idx, cell in enumerate(row_cells):
                if col_idx > 0:
                    cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cell.setStyleSheet("font-family: monospace; font-size: 12px; padding: 2px 6px;")
                matrix_layout.addWidget(cell, row_idx, col_idx)

        perm_layout.addWidget(matrix_frame)

        # Octal Math Explanation Box
        self.octal_math_label = QLabel("Bitwise Mode Decomposition: -")
        self.octal_math_label.setWordWrap(True)
        self.octal_math_label.setStyleSheet(
            """
            QLabel {
                background-color: rgba(255, 255, 255, 0.04);
                color: #e0e0e0;
                font-size: 11px;
                font-family: monospace;
                padding: 6px 8px;
                border-radius: 3px;
            }
            """
        )
        perm_layout.addWidget(self.octal_math_label)

        self.content_layout.addWidget(self.perm_group)

        # ----------------------------------------------------
        # 4. DAC Kernel Access Evaluator
        # ----------------------------------------------------
        self.dac_group = QGroupBox("🔬 Linux DAC Access Evaluation (POSIX / generic_permission)")
        dac_layout = QVBoxLayout(self.dac_group)
        dac_layout.setSpacing(6)

        dac_help = QLabel(
            "Mechanical evaluation of the Linux Kernel 3-step DAC algorithm (fs/namei.c) for a process subject:"
        )
        dac_help.setWordWrap(True)
        dac_help.setStyleSheet("color: #aaa; font-size: 11px;")
        dac_layout.addWidget(dac_help)

        inputs_layout = QHBoxLayout()
        inputs_layout.addWidget(QLabel("Process UID:"))
        self.uid_spin = QSpinBox()
        self.uid_spin.setRange(0, 65535)
        self.uid_spin.setValue(1000)
        self.uid_spin.valueChanged.connect(self._recalculate_dac)
        inputs_layout.addWidget(self.uid_spin)

        inputs_layout.addWidget(QLabel("Process GID:"))
        self.gid_spin = QSpinBox()
        self.gid_spin.setRange(0, 65535)
        self.gid_spin.setValue(1000)
        self.gid_spin.valueChanged.connect(self._recalculate_dac)
        inputs_layout.addWidget(self.gid_spin)

        dac_layout.addLayout(inputs_layout)

        self.dac_result_label = QLabel("Select an object to evaluate kernel DAC rules.")
        self.dac_result_label.setWordWrap(True)
        self.dac_result_label.setStyleSheet(
            """
            QLabel {
                background-color: rgba(46, 204, 113, 0.1);
                border-left: 3px solid #2ecc71;
                color: #eee;
                font-size: 11px;
                padding: 6px 8px;
                border-radius: 3px;
            }
            """
        )
        dac_layout.addWidget(self.dac_result_label)

        self.content_layout.addWidget(self.dac_group)
        self.content_layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def clear_context(self):
        super().clear_context()
        self.name_label.setText("No object selected")
        self.type_badge.setText("Select an item in the filesystem tree to inspect its Linux metadata.")
        self.lbl_path.setText("-")
        self.lbl_size.setText("-")
        self.lbl_inode.setText("-")
        self.lbl_owner.setText("-")
        self.lbl_modified.setText("-")
        self.mode_banner.setText("Mode: ---- | Octal: ----")
        self.octal_math_label.setText("Octal Arithmetic: -")
        self.dac_result_label.setText("Select an object to test kernel DAC.")

        for row in [self.cell_owner, self.cell_group, self.cell_other]:
            for cell in row[1:]:
                cell.setText("-")

    def render_context(self, fs_object: FilesystemObject):
        self.name_label.setText(f"📄 {fs_object.name}" if fs_object.is_file else f"📁 {fs_object.name}")
        self.type_badge.setText(f"Type: {fs_object.file_type} | Symbolic: {fs_object.symbolic_mode}")

        from app.ui.identity import format_identity_badge_html

        self.lbl_path.setText(str(fs_object.path))
        self.lbl_size.setText(f"{fs_object.size_bytes:,} bytes ({fs_object.allocated_blocks_512b} blocks)")
        self.lbl_inode.setText(f"Inode: {format_identity_badge_html(fs_object.inode_number)}  Links: {fs_object.hard_link_count}  Device: {format_identity_badge_html(fs_object.device_id)}")
        self.lbl_owner.setText(f"User: {fs_object.owner_name} ({format_identity_badge_html(fs_object.uid, 'UID')})  |  Group: {fs_object.group_name} ({format_identity_badge_html(fs_object.gid, 'GID')})")
        self.lbl_modified.setText(fs_object.mtime.strftime("%Y-%m-%d %H:%M:%S"))

        self.mode_banner.setText(f"Symbolic: {fs_object.symbolic_mode}  |  Octal: {fs_object.octal_mode}")

        # Render matrix
        def _fmt_bit(val: bool, num: int) -> str:
            return f"<span style='color: #2ecc71; font-weight: bold;'>✓ ({num})</span>" if val else "<span style='color: #e74c3c;'>✗ (0)</span>"

        # Owner row
        o_val = (4 if fs_object.owner_r else 0) + (2 if fs_object.owner_w else 0) + (1 if fs_object.owner_x else 0)
        self.cell_owner[1].setText(_fmt_bit(fs_object.owner_r, 4))
        self.cell_owner[2].setText(_fmt_bit(fs_object.owner_w, 2))
        self.cell_owner[3].setText(_fmt_bit(fs_object.owner_x, 1))
        self.cell_owner[4].setText(f"<b>{o_val}</b>")

        # Group row
        g_val = (4 if fs_object.group_r else 0) + (2 if fs_object.group_w else 0) + (1 if fs_object.group_x else 0)
        self.cell_group[1].setText(_fmt_bit(fs_object.group_r, 4))
        self.cell_group[2].setText(_fmt_bit(fs_object.group_w, 2))
        self.cell_group[3].setText(_fmt_bit(fs_object.group_x, 1))
        self.cell_group[4].setText(f"<b>{g_val}</b>")

        # Other row
        w_val = (4 if fs_object.other_r else 0) + (2 if fs_object.other_w else 0) + (1 if fs_object.other_x else 0)
        self.cell_other[1].setText(_fmt_bit(fs_object.other_r, 4))
        self.cell_other[2].setText(_fmt_bit(fs_object.other_w, 2))
        self.cell_other[3].setText(_fmt_bit(fs_object.other_x, 1))
        self.cell_other[4].setText(f"<b>{w_val}</b>")

        # Bitwise Mode Arithmetic (POSIX.1)
        o_math = f"Owner (st_mode & 0700): {o_val} = ({'4 (S_IRUSR)' if fs_object.owner_r else '0'} + {'2 (S_IWUSR)' if fs_object.owner_w else '0'} + {'1 (S_IXUSR)' if fs_object.owner_x else '0'})"
        g_math = f"Group (st_mode & 0070): {g_val} = ({'4 (S_IRGRP)' if fs_object.group_r else '0'} + {'2 (S_IWGRP)' if fs_object.group_w else '0'} + {'1 (S_IXGRP)' if fs_object.group_x else '0'})"
        w_math = f"Other (st_mode & 0007): {w_val} = ({'4 (S_IROTH)' if fs_object.other_r else '0'} + {'2 (S_IWOTH)' if fs_object.other_w else '0'} + {'1 (S_IXOTH)' if fs_object.other_x else '0'})"

        special_str = ""
        if fs_object.suid or fs_object.sgid or fs_object.sticky:
            special_bits = []
            if fs_object.suid:
                special_bits.append("04000 (S_ISUID)")
            if fs_object.sgid:
                special_bits.append("02000 (S_ISGID)")
            if fs_object.sticky:
                special_bits.append("01000 (S_ISVTX)")
            special_str = f"\nSpecial Mode Bits: {', '.join(special_bits)}"

        self.octal_math_label.setText(f"{o_math}\n{g_math}\n{w_math}{special_str}")

        self._recalculate_dac()

    def _recalculate_dac(self):
        if self.current_context is None:
            return

        uid = self.uid_spin.value()
        gid = self.gid_spin.value()
        result: AccessEvaluationResult = self.current_context.evaluate_access(uid, gid)

        r_icon = "✓" if result.can_read else "✗"
        w_icon = "✓" if result.can_write else "✗"
        x_icon = "✓" if result.can_execute else "✗"

        text = (
            f"<b>{result.decision_reason}</b><br><br>"
            f"<b>Access Verdict for Process (UID {uid}, GID {gid}):</b><br>"
            f"• <b>Read:</b> {r_icon} ({result.read_reason})<br>"
            f"• <b>Write:</b> {w_icon} ({result.write_reason})<br>"
            f"• <b>Execute:</b> {x_icon} ({result.execute_reason})"
        )
        self.dac_result_label.setText(text)
