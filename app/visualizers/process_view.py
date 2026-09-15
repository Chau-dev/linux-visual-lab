from __future__ import annotations

import os
import re
import shiboken6
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.process.model import Process
from app.process.tree import build_process_tree, ProcessTreeNode
from app.ui.identity import get_identity_style, format_identity_badge_html
from app.visualizers.base import BaseVisualizer


class ProcessTreeWidget(QTreeWidget):
    """
    Visualizes the Linux process hierarchy and process attributes directly from /proc.
    Applies deterministic same-value color tokens across PID, PPID, PGID, SID, TPGID.
    Automatically expands the branch containing the focused terminal session.
    """

    process_selected = Signal(object)  # Emits Process instance on selection
    process_double_clicked = Signal(object)  # Emits Process instance on double-click

    COL_COMMAND = 0
    COL_PID = 1
    COL_PPID = 2
    COL_PGID = 3
    COL_SID = 4
    COL_TPGID = 5
    COL_STATE = 6
    COL_TTY = 7
    COL_USER = 8
    COL_CPU = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("process_tree")

        self.setHeaderLabels([
            "COMMAND",
            "PID",
            "PPID",
            "PGID",
            "SID",
            "TPGID",
            "STAT",
            "TTY",
            "USER",
            "CPU %",
        ])
        self.setAnimated(True)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTreeWidget#process_tree QHeaderView::section {
                padding: 4px 2px;
                font-size: 11px;
                font-weight: bold;
            }
            QTreeWidget#process_tree::item {
                padding: 2px 2px;
                font-size: 12px;
            }
        """)

        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self.COL_COMMAND, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_PID, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_PPID, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_PGID, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_SID, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_TPGID, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_STATE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_TTY, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_USER, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_CPU, QHeaderView.ResizeMode.Interactive)

        header.resizeSection(self.COL_PID, 52)
        header.resizeSection(self.COL_PPID, 52)
        header.resizeSection(self.COL_PGID, 52)
        header.resizeSection(self.COL_SID, 52)
        header.resizeSection(self.COL_TPGID, 56)
        header.resizeSection(self.COL_STATE, 40)
        header.resizeSection(self.COL_TTY, 52)
        header.resizeSection(self.COL_USER, 54)
        header.resizeSection(self.COL_CPU, 56)

        self.itemClicked.connect(self._handle_item_clicked)
        self.itemDoubleClicked.connect(self._handle_item_double_clicked)

        self._current_processes: dict[int, Process] = {}
        self._tree_items: dict[int, QTreeWidgetItem] = {}
        self._selected_pid: int | None = None
        self._focused_pid: int | None = None
        self._filter_query: str = ""
        self._filter_preset: str = "all"

    def set_focused_pid(self, pid: int | None):
        """Set the active focused shell PID and auto-expand its branch."""
        self._focused_pid = pid
        if pid:
            self.expand_to_pid(pid)

    def _handle_item_clicked(self, item: QTreeWidgetItem, column: int):
        pid = item.data(self.COL_PID, Qt.ItemDataRole.UserRole)
        if pid and pid in self._current_processes:
            self._selected_pid = pid
            self.process_selected.emit(self._current_processes[pid])

    def _handle_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        pid = item.data(self.COL_PID, Qt.ItemDataRole.UserRole)
        if pid and pid in self._current_processes:
            self._selected_pid = pid
            self.process_double_clicked.emit(self._current_processes[pid])

    def update_processes(self, processes: dict[int, Process], focused_pid: int | None = None):
        """
        Incrementally update the tree hierarchy with the latest /proc process snapshot.
        Preserves user expand/collapse states (including Expand All and Collapse All),
        updates attributes in-place, and preserves scroll position.
        """
        self._current_processes = dict(processes)
        focused_pid_changed = (focused_pid is not None and focused_pid != self._focused_pid)
        if focused_pid is not None:
            self._focused_pid = focused_pid

        current_pids = set(processes.keys())
        existing_pids = set(self._tree_items.keys())

        v_scroll = self.verticalScrollBar().value()

        # If first run: build initial hierarchy
        if not self._tree_items:
            roots = build_process_tree(processes)
            for root_node in roots:
                item = self._create_tree_subtree(root_node)
                self.addTopLevelItem(item)

            if self._focused_pid:
                self.expand_to_pid(self._focused_pid)
            elif self.topLevelItemCount() > 0 and self._selected_pid is None:
                first_pid = roots[0].process.pid if roots else None
                if first_pid:
                    self.select_pid(first_pid)

            if self._filter_query or self._filter_preset != "all":
                self.apply_filter(self._filter_query, self._filter_preset)
            return

        # 1. Remove exited processes (children first to avoid Qt deleting
        #    child C++ objects when their parent item is removed)
        pids_to_remove = existing_pids - current_pids
        def _item_depth(pid):
            """Return the tree depth so we remove leaves before parents."""
            depth = 0
            item = self._tree_items.get(pid)
            if item is not None and shiboken6.isValid(item):
                p = item.parent()
                while p is not None:
                    depth += 1
                    p = p.parent()
            return depth
        sorted_pids_to_remove = sorted(pids_to_remove, key=_item_depth, reverse=True)
        for pid in sorted_pids_to_remove:
            item = self._tree_items.pop(pid, None)
            if item is not None and shiboken6.isValid(item):
                parent = item.parent()
                if parent is not None:
                    parent.removeChild(item)
                else:
                    index = self.indexOfTopLevelItem(item)
                    if index >= 0:
                        self.takeTopLevelItem(index)

        # 2. Add newly observed processes
        added_pids = current_pids - existing_pids
        if added_pids:
            sorted_added = sorted(added_pids, key=lambda p_id: processes[p_id].ppid)
            for pid in sorted_added:
                p = processes[pid]
                item = self._create_single_item(p)
                self._tree_items[pid] = item

                parent_item = self._tree_items.get(p.ppid)
                if parent_item is not None:
                    parent_item.addChild(item)
                    if p.ppid == self._focused_pid:
                        parent_item.setExpanded(True)
                else:
                    self.addTopLevelItem(item)

        # 3. Update existing processes in-place
        for pid in (current_pids & existing_pids):
            item = self._tree_items[pid]
            p = processes[pid]
            self._update_item_data(item, p)

        # 4. If focused shell was changed by the user, expand down to it
        if focused_pid_changed and self._focused_pid:
            self.expand_to_pid(self._focused_pid)

        # 5. Maintain selection
        if self._selected_pid and self._selected_pid in self._tree_items:
            item = self._tree_items[self._selected_pid]
            if self.currentItem() != item:
                self.setCurrentItem(item)

        if self._filter_query or self._filter_preset != "all":
            self.apply_filter(self._filter_query, self._filter_preset)

        self.verticalScrollBar().setValue(v_scroll)

    def _create_single_item(self, p: Process) -> QTreeWidgetItem:
        tty_str = p.tty.replace("/dev/", "") if p.tty else "?"
        prefix = "🐚 " if (self._focused_pid and p.pid == self._focused_pid) else "⚡ "
        item = QTreeWidgetItem([
            f"{prefix}{p.command}",
            str(p.pid),
            str(p.ppid),
            str(p.pgid),
            str(p.sid),
            str(p.tpgid),
            p.state,
            tty_str,
            p.user_name,
            p.formatted_cpu_percent,
        ])
        item.setData(self.COL_PID, Qt.ItemDataRole.UserRole, p.pid)
        self._apply_item_styles(item, p)
        return item

    def _update_item_data(self, item: QTreeWidgetItem, p: Process):
        tty_str = p.tty.replace("/dev/", "") if p.tty else "?"
        prefix = "🐚 " if (self._focused_pid and p.pid == self._focused_pid) else "⚡ "

        item.setText(self.COL_COMMAND, f"{prefix}{p.command}")
        item.setText(self.COL_PID, str(p.pid))
        item.setText(self.COL_PPID, str(p.ppid))
        item.setText(self.COL_PGID, str(p.pgid))
        item.setText(self.COL_SID, str(p.sid))
        item.setText(self.COL_TPGID, str(p.tpgid))
        item.setText(self.COL_STATE, p.state)
        item.setText(self.COL_TTY, tty_str)
        item.setText(self.COL_USER, p.user_name)
        item.setText(self.COL_CPU, p.formatted_cpu_percent)

        self._apply_item_styles(item, p)

    def _apply_item_styles(self, item: QTreeWidgetItem, p: Process):
        for col_idx, val in [
            (self.COL_PID, p.pid),
            (self.COL_PPID, p.ppid),
            (self.COL_PGID, p.pgid),
            (self.COL_SID, p.sid),
            (self.COL_TPGID, p.tpgid),
        ]:
            bg, fg, _ = get_identity_style(val)
            item.setTextAlignment(col_idx, Qt.AlignmentFlag.AlignCenter)
            item.setBackground(col_idx, QBrush(QColor(bg)))
            item.setForeground(col_idx, QBrush(QColor(fg)))

        item.setTextAlignment(self.COL_STATE, Qt.AlignmentFlag.AlignCenter)
        if p.state == "R":
            item.setForeground(self.COL_STATE, QBrush(QColor("#2ecc71")))
        elif p.state == "Z":
            item.setForeground(self.COL_STATE, QBrush(QColor("#e74c3c")))
        elif p.state in ("T", "t"):
            item.setForeground(self.COL_STATE, QBrush(QColor("#f39c12")))
        else:
            item.setForeground(self.COL_STATE, QBrush(QColor("#e2e8f0")))

        item.setTextAlignment(self.COL_CPU, Qt.AlignmentFlag.AlignRight)
        if p.derived_cpu_percent is not None and p.derived_cpu_percent > 0.0:
            if p.derived_cpu_percent >= 80.0:
                item.setForeground(self.COL_CPU, QBrush(QColor("#ef4444")))
            elif p.derived_cpu_percent >= 25.0:
                item.setForeground(self.COL_CPU, QBrush(QColor("#f59e0b")))
            else:
                item.setForeground(self.COL_CPU, QBrush(QColor("#38bdf8")))
        else:
            item.setForeground(self.COL_CPU, QBrush(QColor("#94a3b8")))

    def _create_tree_subtree(self, node: ProcessTreeNode) -> QTreeWidgetItem:
        p = node.process
        item = self._create_single_item(p)
        self._tree_items[p.pid] = item

        if node.depth == 0:
            item.setExpanded(True)

        for child in node.children:
            child_item = self._create_tree_subtree(child)
            item.addChild(child_item)

        return item

    def expand_to_pid(self, target_pid: int) -> bool:
        """Expand the ancestor chain leading down to target_pid, and expand target_pid itself."""
        root = self.invisibleRootItem()

        def _expand_branch(item: QTreeWidgetItem) -> bool:
            pid = item.data(self.COL_PID, Qt.ItemDataRole.UserRole)
            if pid == target_pid:
                item.setExpanded(True)
                return True
            for i in range(item.childCount()):
                if _expand_branch(item.child(i)):
                    item.setExpanded(True)
                    return True
            return False

        for i in range(root.childCount()):
            if _expand_branch(root.child(i)):
                return True
        return False

    def apply_filter(self, query: str | None = None, preset: str | None = None):
        """
        Filter tree items by multiple terms simultaneously and/or category preset.
        Supports quick presets:
          - 'all': All processes
          - 'shell_tree': Active terminal shell + ancestor path and all its spawned child processes
          - 'user': Current user UID processes
          - 'active': Non-idle / active processes
          - 'session_leaders': Session leader processes
        """
        if query is not None:
            self._filter_query = query.strip()
        if preset is not None:
            self._filter_preset = preset.strip()

        raw_query = self._filter_query.lower()
        preset = self._filter_preset

        # Compute shell tree allowed PIDs if preset == "shell_tree"
        shell_tree_pids = set()
        if preset == "shell_tree" and self._focused_pid and self._focused_pid in self._current_processes:
            shell_tree_pids.add(self._focused_pid)
            # Ancestors
            curr = self._current_processes.get(self._focused_pid)
            while curr and curr.ppid in self._current_processes and curr.ppid != curr.pid and curr.ppid != 0:
                shell_tree_pids.add(curr.ppid)
                curr = self._current_processes.get(curr.ppid)
            # Descendants
            desc_pids = {self._focused_pid}
            while True:
                new_desc = {
                    p.pid
                    for p in self._current_processes.values()
                    if p.ppid in desc_pids and p.pid not in desc_pids
                }
                if not new_desc:
                    break
                desc_pids |= new_desc
            shell_tree_pids |= desc_pids

        # Parse terms
        if raw_query:
            if "," in raw_query or "|" in raw_query:
                terms = [t.strip() for t in re.split(r"[,|]", raw_query) if t.strip()]
            else:
                tokens = [t.strip() for t in raw_query.split() if t.strip()]
                terms = list(dict.fromkeys([raw_query] + tokens))
        else:
            terms = []

        def _matches_preset(p: Process) -> bool:
            if preset == "all":
                return True
            elif preset == "shell_tree":
                return p.pid in shell_tree_pids
            elif preset == "user":
                return p.uid == os.getuid()
            elif preset == "active":
                return p.state == "R" or (p.derived_cpu_percent is not None and p.derived_cpu_percent > 0.0)
            elif preset == "session_leaders":
                return p.is_session_leader
            return True

        def _matches_query(p: Process) -> bool:
            if not terms:
                return True
            p_pid_str = str(p.pid)
            p_ppid_str = str(p.ppid)
            p_pgid_str = str(p.pgid)
            p_sid_str = str(p.sid)
            p_tpgid_str = str(p.tpgid)
            p_cmd = p.command.lower()
            p_cmdline = p.cmdline.lower()
            p_user = p.user_name.lower()
            p_state = p.state.lower()
            p_tty = (p.tty.lower() if p.tty else "")
            p_stdin = (p.stdin_target.lower() if p.stdin_target else "")

            for term in terms:
                if (
                    term in p_cmd
                    or term in p_cmdline
                    or term == p_pid_str
                    or term in p_pid_str
                    or term == p_ppid_str
                    or term == p_pgid_str
                    or term == p_sid_str
                    or term == p_tpgid_str
                    or term in p_user
                    or term == p_state
                    or (p_tty and term in p_tty)
                    or (p_stdin and term in p_stdin)
                ):
                    return True
            return False

        root = self.invisibleRootItem()

        def _filter_node(item: QTreeWidgetItem) -> bool:
            pid = item.data(self.COL_PID, Qt.ItemDataRole.UserRole)
            p = self._current_processes.get(pid) if pid else None

            self_matches = (_matches_preset(p) and _matches_query(p)) if p else False

            child_matches = False
            for i in range(item.childCount()):
                if _filter_node(item.child(i)):
                    child_matches = True

            visible = self_matches or child_matches
            item.setHidden(not visible)
            if child_matches or (self_matches and (terms or preset != "all")):
                item.setExpanded(True)
            return visible

        for i in range(root.childCount()):
            _filter_node(root.child(i))

    def select_pid(self, pid: int) -> bool:
        """Programmatically select a process row by PID, auto-center in view, and emit inspection signal."""
        item = self._tree_items.get(pid)
        if item is not None:
            self.setCurrentItem(item)
            self.scrollToItem(item, QTreeWidget.ScrollHint.PositionAtCenter)
            if self._selected_pid == pid:
                return True
            self._selected_pid = pid
            if pid in self._current_processes:
                self.process_selected.emit(self._current_processes[pid])
            return True
        return False


class ProcessInspectorWidget(BaseVisualizer):
    """
    Selected Process Inspector:
    Displays factual Linux process metadata directly from /proc:
      - Process identity & kernel state
      - Kernel Task Name (comm) vs Full Command Line (cmdline)
      - Deterministic same-value ID alignment (PID, PPID, PGID, SID, TPGID)
      - Factual Linux session/process-group leader status
      - Credentials (UID / GID)
      - Controlling Terminal (tty_nr from stat) vs Standard Input (fd 0)
      - Working Directory (CWD)
      - Quick jump to Linux File Descriptors & I/O Lab
    """

    inspect_io_requested = Signal(int)  # Emits PID when user clicks Inspect in I/O Lab

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_process: Process | None = None
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

        self.name_label = QLabel("No process selected")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #fff;")
        header_layout.addWidget(self.name_label)

        self.state_badge = QLabel("Select a process in the table/tree to inspect its Linux kernel state.")
        self.state_badge.setStyleSheet("color: #aaa; font-size: 12px;")
        self.state_badge.setWordWrap(True)
        header_layout.addWidget(self.state_badge)

        self.content_layout.addWidget(self.header_frame)

        # ----------------------------------------------------
        # 2. Linux Identifier Alignment & Job Control
        # ----------------------------------------------------
        self.id_group = QGroupBox("🔐 Linux Process Grouping & Lineage")
        id_form = QFormLayout(self.id_group)
        id_form.setSpacing(6)

        self.lbl_pid = QLabel("-")
        self.lbl_ppid = QLabel("-")
        self.lbl_pgid = QLabel("-")
        self.lbl_sid = QLabel("-")
        self.lbl_tpgid = QLabel("-")
        self.lbl_roles = QLabel("-")
        self.lbl_roles.setWordWrap(True)

        id_form.addRow("<b>Process ID (PID):</b>", self.lbl_pid)
        id_form.addRow("<b>Parent PID (PPID):</b>", self.lbl_ppid)
        id_form.addRow("<b>Process Group (PGID):</b>", self.lbl_pgid)
        id_form.addRow("<b>Session ID (SID):</b>", self.lbl_sid)
        id_form.addRow("<b>TTY Foreground (TPGID):</b>", self.lbl_tpgid)
        id_form.addRow("<b>Job Control Roles:</b>", self.lbl_roles)

        self.content_layout.addWidget(self.id_group)

        # ----------------------------------------------------
        # 3. Credentials Card
        # ----------------------------------------------------
        self.cred_group = QGroupBox("👤 Linux User & Group Credentials")
        cred_form = QFormLayout(self.cred_group)
        cred_form.setSpacing(6)

        self.lbl_user = QLabel("-")
        self.lbl_group = QLabel("-")

        cred_form.addRow("<b>Process Owner (UID):</b>", self.lbl_user)
        cred_form.addRow("<b>Process Group (GID):</b>", self.lbl_group)

        self.content_layout.addWidget(self.cred_group)

        # ----------------------------------------------------
        # 4. Execution & Environment Card
        # ----------------------------------------------------
        self.env_group = QGroupBox("🖥️ Execution & Location")
        env_form = QFormLayout(self.env_group)
        env_form.setSpacing(6)

        self.lbl_comm = QLabel("-")
        self.lbl_tty = QLabel("-")
        self.lbl_stdin = QLabel("-")
        self.lbl_cwd = QLabel("-")
        self.lbl_cwd.setWordWrap(True)
        self.lbl_cmdline = QLabel("-")
        self.lbl_cmdline.setWordWrap(True)
        self.lbl_cmdline.setStyleSheet("font-family: monospace; font-size: 11px; color: #67e8f9;")

        env_form.addRow("<b>Task Name (comm):</b>", self.lbl_comm)
        env_form.addRow("<b>Controlling TTY (tty_nr):</b>", self.lbl_tty)
        env_form.addRow("<b>Standard Input (fd 0):</b>", self.lbl_stdin)
        env_form.addRow("<b>Working Dir (CWD):</b>", self.lbl_cwd)
        env_form.addRow("<b>Full Command Line:</b>", self.lbl_cmdline)

        self.content_layout.addWidget(self.env_group)

        # ----------------------------------------------------
        # 5. File Descriptors & Streams Card
        # ----------------------------------------------------
        self.fd_group = QGroupBox("🗂️ File Descriptors & Streams (/proc/<pid>/fd)")
        fd_form = QFormLayout(self.fd_group)
        fd_form.setSpacing(6)

        self.lbl_fd_stdin = QLabel("-")
        self.lbl_fd_hint = QLabel(
            "💡 Inspect all open descriptors, offset cursors, pipe endpoints, and I/O bandwidth in the I/O Lab."
        )
        self.lbl_fd_hint.setWordWrap(True)
        self.lbl_fd_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")

        self.inspect_io_btn = QPushButton("🗂️ Inspect File Descriptors in I/O Lab ➔")
        self.inspect_io_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 10px;
                border-radius: 4px;
                border: 1px solid #38bdf8;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        self.inspect_io_btn.setEnabled(False)
        self.inspect_io_btn.clicked.connect(self._on_inspect_io_clicked)

        fd_form.addRow("<b>Standard Input (fd 0):</b>", self.lbl_fd_stdin)
        fd_form.addRow(self.lbl_fd_hint)
        fd_form.addRow(self.inspect_io_btn)

        self.content_layout.addWidget(self.fd_group)

        # ----------------------------------------------------
        # 6. CPU Scheduling & Ticks Card
        # ----------------------------------------------------
        self.cpu_group = QGroupBox("⏱️ CPU Scheduling & Ticks (/proc/<pid>/stat)")
        cpu_form = QFormLayout(self.cpu_group)
        cpu_form.setSpacing(6)

        self.lbl_cpu_pct = QLabel("-")
        self.lbl_utime = QLabel("-")
        self.lbl_stime = QLabel("-")
        self.lbl_starttime = QLabel("-")

        cpu_form.addRow("<b>Derived CPU %:</b>", self.lbl_cpu_pct)
        cpu_form.addRow("<b>User Ticks (utime):</b>", self.lbl_utime)
        cpu_form.addRow("<b>Kernel Ticks (stime):</b>", self.lbl_stime)
        cpu_form.addRow("<b>Start Time (starttime):</b>", self.lbl_starttime)

        self.content_layout.addWidget(self.cpu_group)
        self.content_layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _on_inspect_io_clicked(self):
        if self._current_process is not None:
            self.inspect_io_requested.emit(self._current_process.pid)

    def clear_context(self):
        super().clear_context()
        self._current_process = None
        self.inspect_io_btn.setEnabled(False)
        self.name_label.setText("No process selected")
        self.state_badge.setText("Select a process in the table/tree to inspect its Linux kernel state.")
        self.lbl_pid.setText("-")
        self.lbl_ppid.setText("-")
        self.lbl_pgid.setText("-")
        self.lbl_sid.setText("-")
        self.lbl_tpgid.setText("-")
        self.lbl_roles.setText("-")
        self.lbl_user.setText("-")
        self.lbl_group.setText("-")
        self.lbl_comm.setText("-")
        self.lbl_tty.setText("-")
        self.lbl_stdin.setText("-")
        self.lbl_fd_stdin.setText("-")
        self.lbl_cwd.setText("-")
        self.lbl_cmdline.setText("-")
        self.lbl_cpu_pct.setText("-")
        self.lbl_utime.setText("-")
        self.lbl_stime.setText("-")
        self.lbl_starttime.setText("-")

    def render_context(self, process: Process):
        self._current_process = process
        self.inspect_io_btn.setEnabled(True)
        self.name_label.setText(f"⚡ {process.command}  (PID {process.pid})")
        self.state_badge.setText(f"Linux Kernel State: <b>{process.state_description}</b>")

        # Identity badges
        self.lbl_pid.setText(format_identity_badge_html(process.pid, "PID"))
        self.lbl_ppid.setText(format_identity_badge_html(process.ppid, "PPID"))
        self.lbl_pgid.setText(format_identity_badge_html(process.pgid, "PGID"))
        self.lbl_sid.setText(format_identity_badge_html(process.sid, "SID"))
        self.lbl_tpgid.setText(format_identity_badge_html(process.tpgid, "TPGID"))

        # Role tags directly derived from Linux state
        roles = []
        if process.is_session_leader:
            roles.append("<span style='color: #60a5fa;'>🏛️ Session Leader (PID == SID)</span>")
        if process.is_process_group_leader:
            roles.append("<span style='color: #f59e0b;'>👑 Process Group Leader (PID == PGID)</span>")
        if process.is_foreground:
            roles.append("<span style='color: #2ecc71;'>🟢 Foreground Process Group on TTY (PGID == TPGID)</span>")
        elif process.tpgid > 0:
            roles.append("<span style='color: #94a3b8;'>⚪ Background Process Group</span>")

        if not roles:
            roles.append("<span style='color: #94a3b8;'>Standard Child Process</span>")

        self.lbl_roles.setText("<br>".join(roles))

        # Credentials
        self.lbl_user.setText(f"{process.user_name} ({format_identity_badge_html(process.uid, 'UID')})")
        self.lbl_group.setText(f"{process.group_name} ({format_identity_badge_html(process.gid, 'GID')})")

        # Execution environment & Terminals
        self.lbl_comm.setText(process.command)

        if process.tty:
            self.lbl_tty.setText(f"<code>{process.tty}</code> <span style='color: #888;'>(tty_nr: {process.tty_nr})</span>")
        else:
            self.lbl_tty.setText(f"<span style='color: #888;'>None (tty_nr: {process.tty_nr})</span>")

        if process.stdin_target:
            self.lbl_stdin.setText(f"<code>{process.stdin_target}</code>")
            self.lbl_fd_stdin.setText(f"<code>{process.stdin_target}</code>")
        else:
            self.lbl_stdin.setText("<span style='color: #888;'>None / inaccessible</span>")
            self.lbl_fd_stdin.setText("<span style='color: #888;'>None / inaccessible</span>")

        self.lbl_cwd.setText(str(process.cwd) if process.cwd else "Unknown / restricted")
        self.lbl_cmdline.setText(process.cmdline)

        # CPU Scheduling & Ticks
        if process.derived_cpu_percent is not None:
            self.lbl_cpu_pct.setText(
                f"<b style='color: #38bdf8;'>{process.derived_cpu_percent:.1f}%</b> "
                f"<span style='color: #888;'>(wall-time ratio)</span>"
            )
        else:
            self.lbl_cpu_pct.setText("<span style='color: #888;'>— (awaiting baseline)</span>")

        self.lbl_utime.setText(f"<code>{process.utime_ticks:,} ticks</code>")
        self.lbl_stime.setText(f"<code>{process.stime_ticks:,} ticks</code>")
        self.lbl_starttime.setText(f"<code>{process.starttime:,} ticks after boot</code>")


class ProcessLabWidget(QWidget):
    """
    Combined Process Lab Widget housing the ProcessTreeWidget, toolbar controls, and ProcessInspectorWidget.
    Supports live freeze/pause, quick filter presets, selection pinning, and direct I/O lab jumps.
    """

    inspect_io_requested = Signal(int)  # Emitted when inspecting process in I/O lab
    process_selected = Signal(object)  # Emitted when a process is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_paused: bool = False
        self._cached_snapshot: tuple[dict[int, Process], int | None] | None = None
        self._pinned_pid: int | None = None
        self._is_pinned: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar: Search Bar + Filter Preset + Pause + Pin + Inspector Toggle
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(2, 2, 2, 2)
        toolbar.setSpacing(6)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Filter multiple: sleep, cat, bash or 10228, pts/1...")
        self.search_edit.setClearButtonEnabled(True)
        toolbar.addWidget(self.search_edit, 2)

        preset_lbl = QLabel("Filter:")
        preset_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        toolbar.addWidget(preset_lbl)

        self.preset_combo = QComboBox()
        self.preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                selection-background-color: #334155;
                selection-color: #38bdf8;
            }
        """)
        self.preset_combo.addItem("All Processes", "all")
        self.preset_combo.addItem("🐚 Focused Shell Tree", "shell_tree")
        self.preset_combo.addItem(f"👤 My User Processes (UID {os.getuid()})", "user")
        self.preset_combo.addItem("⚡ Active / Non-Idle", "active")
        self.preset_combo.addItem("🏛️ Session Leaders", "session_leaders")
        toolbar.addWidget(self.preset_combo)

        self.pause_btn = QPushButton("⏸️ Pause Updates")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QPushButton:checked {
                background-color: #d97706;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #fbbf24;
            }
        """)
        toolbar.addWidget(self.pause_btn)

        self.pin_btn = QPushButton("📌 Pin Selection")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QPushButton:checked {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
            }
        """)
        toolbar.addWidget(self.pin_btn)

        self.toggle_inspector_btn = QPushButton("👁️ Inspector")
        self.toggle_inspector_btn.setCheckable(True)
        self.toggle_inspector_btn.setChecked(True)
        self.toggle_inspector_btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
        toolbar.addWidget(self.toggle_inspector_btn)

        layout.addLayout(toolbar)

        # Splitter: Process Tree (Left/Top) + Inspector (Right/Bottom)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(True)

        self.tree_widget = ProcessTreeWidget()
        self.inspector_widget = ProcessInspectorWidget()

        self.splitter.addWidget(self.tree_widget)
        self.splitter.addWidget(self.inspector_widget)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([650, 270])

        layout.addWidget(self.splitter, 1)

        # Connect signals
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.pause_btn.toggled.connect(self._on_pause_toggled)
        self.pin_btn.toggled.connect(self._on_pin_toggled)
        self.toggle_inspector_btn.toggled.connect(self._toggle_inspector)
        self.tree_widget.process_selected.connect(self._on_tree_process_selected)
        self.tree_widget.process_double_clicked.connect(self._on_tree_double_clicked)
        self.inspector_widget.inspect_io_requested.connect(self.inspect_io_requested)

    def _on_tree_process_selected(self, process: Process):
        self.inspector_widget.set_context(process)
        if self._is_pinned:
            self._pinned_pid = process.pid
        self.process_selected.emit(process)

    def _on_tree_double_clicked(self, process: Process):
        self.inspect_io_requested.emit(process.pid)

    def _on_search_text_changed(self, text: str):
        self.tree_widget.apply_filter(query=text)

    def _on_preset_changed(self, idx: int):
        preset = self.preset_combo.currentData() or "all"
        self.tree_widget.apply_filter(preset=preset)

    def _on_pause_toggled(self, checked: bool):
        self.is_paused = checked
        if checked:
            self.pause_btn.setText("▶️ Resume Updates")
        else:
            self.pause_btn.setText("⏸️ Pause Updates")
            if self._cached_snapshot:
                procs, f_pid = self._cached_snapshot
                self.tree_widget.update_processes(procs, focused_pid=f_pid)

    def _on_pin_toggled(self, checked: bool):
        self._is_pinned = checked
        if checked:
            self._pinned_pid = self.tree_widget._selected_pid
            self.pin_btn.setText("📌 Pinned")
        else:
            self._pinned_pid = None
            self.pin_btn.setText("📌 Pin Selection")

    def _toggle_inspector(self, checked: bool):
        self.inspector_widget.setVisible(checked)
        if checked:
            self.splitter.setSizes([650, 270])

    def set_focused_pid(self, pid: int | None):
        self.tree_widget.set_focused_pid(pid)

    def update_processes(self, processes: dict[int, Process], focused_pid: int | None = None):
        self._cached_snapshot = (processes, focused_pid)
        if self.is_paused:
            return

        self.tree_widget.update_processes(processes, focused_pid=focused_pid)
        if self._is_pinned and self._pinned_pid is not None and self._pinned_pid in processes:
            self.tree_widget.select_pid(self._pinned_pid)

