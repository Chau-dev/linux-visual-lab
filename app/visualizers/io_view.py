from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.io.model import (
    FdType,
    FileDescriptor,
    PipeEndpoint,
    ProcessIoSnapshot,
    DerivedProcessIoRates,
    DiskDeviceStat,
    KernelFileLock,
)
from app.io.registry import ProcessIoState
from app.process.model import Process
from app.ui.identity import format_identity_badge_html, get_identity_style
from app.visualizers.base import BaseVisualizer


def format_bytes_human(val_bytes: int | float | None) -> str:
    """Format bytes into human-readable B, KB, MB, GB."""
    if val_bytes is None:
        return "N/A"
    val = float(val_bytes)
    if val < 1024:
        return f"{val:.0f} B"
    elif val < 1024 * 1024:
        return f"{val / 1024:.2f} KB"
    elif val < 1024 * 1024 * 1024:
        return f"{val / (1024 * 1024):.2f} MB"
    else:
        return f"{val / (1024 * 1024 * 1024):.2f} GB"


def format_rate_human(rate_bytes_per_sec: float | None) -> str:
    """Format bytes/sec rate into human-readable unit with [DERIVED] indicator."""
    if rate_bytes_per_sec is None:
        return "—"
    if rate_bytes_per_sec < 1024:
        return f"{rate_bytes_per_sec:.1f} B/s"
    elif rate_bytes_per_sec < 1024 * 1024:
        return f"{rate_bytes_per_sec / 1024:.2f} KB/s"
    else:
        return f"{rate_bytes_per_sec / (1024 * 1024):.2f} MB/s"


class FdTableWidget(QTableWidget):
    """
    Live interactive table displaying the open file descriptors of the selected process.
    Features deterministic identity badge highlighting on pipe and socket inodes.
    """

    fd_selected = Signal(object)  # Emits FileDescriptor instance or None

    COL_FD = 0
    COL_TYPE = 1
    COL_STREAM = 2
    COL_TARGET = 3
    COL_POS = 4
    COL_MODE = 5
    COL_FLAGS = 6
    COL_MNT = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fd_table")
        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "FD #",
            "TYPE",
            "ROLE",
            "TARGET / INODE IDENTIFIER",
            "OFFSET (pos)",
            "ACCESS MODE",
            "STATUS FLAGS",
            "MNT ID",
        ])

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_FD, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_STREAM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TARGET, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_POS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_MODE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_FLAGS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_MNT, QHeaderView.ResizeMode.ResizeToContents)

        self.setStyleSheet("""
            QTableWidget#fd_table {
                background-color: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                gridline-color: rgba(255, 255, 255, 0.05);
            }
            QTableWidget#fd_table QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 4px 6px;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            QTableWidget#fd_table::item {
                padding: 4px 6px;
                font-size: 12px;
            }
        """)

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self._current_descriptors: list[FileDescriptor] = []

    def populate(self, descriptors: list[FileDescriptor]):
        """Populate the table with current descriptors."""
        selected_fd = self.get_selected_fd_num()
        self._current_descriptors = descriptors
        self.setRowCount(len(descriptors))

        new_select_row = -1

        for row, fd_obj in enumerate(descriptors):
            if selected_fd is not None and fd_obj.fd == selected_fd:
                new_select_row = row

            # 1. FD Number
            item_fd = QTableWidgetItem(str(fd_obj.fd))
            item_fd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_fd.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
            if fd_obj.is_standard_stream:
                item_fd.setForeground(QBrush(QColor("#38bdf8")))
            self.setItem(row, self.COL_FD, item_fd)

            # 2. Type Badge
            item_type = QTableWidgetItem(fd_obj.fd_type.value)
            item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if fd_obj.fd_type == FdType.REGULAR_FILE:
                item_type.setForeground(QBrush(QColor("#a78bfa")))
            elif fd_obj.fd_type == FdType.PTY_TTY:
                item_type.setForeground(QBrush(QColor("#60a5fa")))
            elif fd_obj.fd_type == FdType.PIPE:
                item_type.setForeground(QBrush(QColor("#f59e0b")))
            elif fd_obj.fd_type == FdType.SOCKET:
                item_type.setForeground(QBrush(QColor("#10b981")))
            elif fd_obj.fd_type == FdType.ANON_INODE:
                item_type.setForeground(QBrush(QColor("#ec4899")))
            self.setItem(row, self.COL_TYPE, item_type)

            # 3. Stream Role
            stream_text = fd_obj.display_role if fd_obj.is_standard_stream else "—"
            item_stream = QTableWidgetItem(stream_text)
            item_stream.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_stream.setForeground(QBrush(QColor("#94a3b8")))
            self.setItem(row, self.COL_STREAM, item_stream)

            # 4. Target Path / Inode Identifier (with deterministic identity highlight)
            target_display = fd_obj.target
            item_target = QTableWidgetItem(target_display)
            item_target.setFont(QFont("Monospace", 10))

            if fd_obj.target_inode is not None:
                bg, fg, _ = get_identity_style(fd_obj.target_inode)
                item_target.setBackground(QBrush(QColor(bg)))
                item_target.setForeground(QBrush(QColor(fg)))
            elif fd_obj.fd_type == FdType.PTY_TTY:
                item_target.setForeground(QBrush(QColor("#93c5fd")))
            elif fd_obj.fd_type == FdType.REGULAR_FILE:
                item_target.setForeground(QBrush(QColor("#e2e8f0")))

            self.setItem(row, self.COL_TARGET, item_target)

            # 5. Offset (pos)
            pos_text = f"{fd_obj.pos:,} B" if fd_obj.pos is not None else "N/A (Stream)"
            item_pos = QTableWidgetItem(pos_text)
            item_pos.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_pos.setFont(QFont("Monospace", 10))
            item_pos.setForeground(QBrush(QColor("#cbd5e1") if fd_obj.pos is not None else QColor("#64748b")))
            self.setItem(row, self.COL_POS, item_pos)

            # 6. Access Mode
            item_mode = QTableWidgetItem(fd_obj.access_mode)
            item_mode.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if fd_obj.access_mode == "O_WRONLY":
                item_mode.setForeground(QBrush(QColor("#f87171")))
            elif fd_obj.access_mode == "O_RDONLY":
                item_mode.setForeground(QBrush(QColor("#4ade80")))
            elif fd_obj.access_mode == "O_RDWR":
                item_mode.setForeground(QBrush(QColor("#fbbf24")))
            self.setItem(row, self.COL_MODE, item_mode)

            # 7. Status Flags
            flags_str = ", ".join(fd_obj.status_flags) if fd_obj.status_flags else "—"
            item_flags = QTableWidgetItem(flags_str)
            item_flags.setFont(QFont("Monospace", 9))
            item_flags.setForeground(QBrush(QColor("#94a3b8")))
            self.setItem(row, self.COL_FLAGS, item_flags)

            # 8. Mount ID
            mnt_text = str(fd_obj.mnt_id) if fd_obj.mnt_id is not None else "—"
            item_mnt = QTableWidgetItem(mnt_text)
            item_mnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_mnt.setForeground(QBrush(QColor("#64748b")))
            self.setItem(row, self.COL_MNT, item_mnt)

        if new_select_row >= 0:
            self.selectRow(new_select_row)
        elif len(descriptors) > 0 and self.currentRow() < 0:
            self.selectRow(0)

    def get_selected_fd_num(self) -> int | None:
        row = self.currentRow()
        if 0 <= row < len(self._current_descriptors):
            return self._current_descriptors[row].fd
        return None

    def _on_selection_changed(self):
        row = self.currentRow()
        if 0 <= row < len(self._current_descriptors):
            self.fd_selected.emit(self._current_descriptors[row])
        else:
            self.fd_selected.emit(None)


class SelectedFdInspector(QFrame):
    """
    Detailed factual inspector for a selected file descriptor and its open flags / peer endpoints.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            SelectedFdInspector {
                background-color: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        title = QLabel("🔍 SELECTED FILE DESCRIPTOR ANATOMY")
        title.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(title)

        self.info_lbl = QLabel("Select a descriptor from the table to inspect its Linux kernel metadata.")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        layout.addWidget(self.info_lbl)

        # Peer endpoint section
        self.peer_frame = QFrame()
        self.peer_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(234, 179, 8, 0.3);
                border-radius: 4px;
                padding: 6px;
            }
        """)
        peer_layout = QVBoxLayout(self.peer_frame)
        peer_layout.setContentsMargins(6, 4, 6, 4)
        peer_layout.setSpacing(2)

        self.peer_title = QLabel("🔗 SHARED PIPE ENDPOINTS")
        self.peer_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #eab308;")
        peer_layout.addWidget(self.peer_title)

        self.peer_desc = QLabel("—")
        self.peer_desc.setWordWrap(True)
        self.peer_desc.setStyleSheet("font-size: 11px; color: #f8fafc;")
        peer_layout.addWidget(self.peer_desc)

        layout.addWidget(self.peer_frame)
        self.peer_frame.setVisible(False)
        layout.addStretch()

    def update_fd(self, fd_obj: FileDescriptor | None, resolved_pipes: dict[int, list[PipeEndpoint]] | None = None):
        if fd_obj is None:
            self.info_lbl.setText("Select a descriptor from the table to inspect its Linux kernel metadata.")
            self.peer_frame.setVisible(False)
            return

        resolved_pipes = resolved_pipes or {}

        # Build detailed anatomy HTML
        lines = [
            f"<b>Descriptor:</b> <code>fd {fd_obj.fd}</code> ({fd_obj.display_role})",
            f"<b>Target:</b> <code>{fd_obj.target}</code>",
            f"<b>Type:</b> <b>{fd_obj.fd_type.value}</b>",
        ]

        if fd_obj.target_inode is not None:
            badge = format_identity_badge_html(fd_obj.target_inode, "INODE")
            lines.append(f"<b>Extracted Inode:</b> {badge}")

        if fd_obj.anon_type:
            lines.append(f"<b>Anon Tag:</b> <code>{fd_obj.anon_type}</code>")

        lines.append(f"<b>Access Mode:</b> <code>{fd_obj.access_mode}</code> (Endpoint role: <b>{fd_obj.pipe_endpoint_role}</b>)")

        if fd_obj.flags_octal:
            lines.append(f"<b>Raw Flags (octal):</b> <code>{fd_obj.flags_octal}</code>")

        if fd_obj.status_flags:
            flags_badges = " ".join(f"<code>{f}</code>" for f in fd_obj.status_flags)
            lines.append(f"<b>Decoded Flags:</b> {flags_badges}")

        if fd_obj.pos is not None:
            lines.append(f"<b>File Offset (pos):</b> <code>{fd_obj.pos:,} bytes</code>")
        else:
            lines.append("<b>File Offset (pos):</b> <span style='color: #888;'>N/A (Non-seekable stream)</span>")

        if fd_obj.mnt_id is not None:
            lines.append(f"<b>Mount ID:</b> <code>{fd_obj.mnt_id}</code>")

        self.info_lbl.setText("<br>".join(lines))

        # Check for resolved pipe peers
        if fd_obj.is_pipe and fd_obj.target_inode in resolved_pipes:
            endpoints = resolved_pipes[fd_obj.target_inode]
            if len(endpoints) >= 2:
                self.peer_frame.setVisible(True)
                peer_lines = []
                for ep in endpoints:
                    badge = format_identity_badge_html(ep.pid, "PID")
                    is_self = ep.pid == getattr(self, "_current_pid", None) and ep.fd == fd_obj.fd
                    self_tag = " <span style='color: #38bdf8;'>(this process)</span>" if is_self else ""
                    peer_lines.append(
                        f"• {badge} <b>{ep.process_command}</b> fd {ep.fd} "
                        f"[<code>{ep.access_mode}</code> — {ep.endpoint_role}]{self_tag}"
                    )
                self.peer_desc.setText("<br>".join(peer_lines))
            else:
                self.peer_frame.setVisible(True)
                self.peer_desc.setText("<span style='color: #94a3b8;'>No peer endpoint currently accessible in user space.</span>")
        else:
            self.peer_frame.setVisible(False)


class ProcessIoStatsWidget(QFrame):
    """
    Displays raw cumulative /proc/<pid>/io counters and derived live rates,
    strictly separating VFS syscall accounting from storage device block I/O.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ProcessIoStatsWidget {
                background-color: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # 1. Header
        header = QHBoxLayout()
        title = QLabel("📊 PROCESS I/O ACCOUNTING (/proc/<pid>/io)")
        title.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        header.addWidget(title)
        header.addStretch()

        self.derived_badge = QLabel("⚡ DERIVED RATES ACTIVE")
        self.derived_badge.setStyleSheet("""
            background-color: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid #0284c7;
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
        """)
        header.addWidget(self.derived_badge)
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(8)

        # 2. VFS System Call Accounting Card
        vfs_group = QGroupBox("📁 VFS / System Call Layer (rchar / wchar / syscr / syscw)")
        vfs_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cbd5e1; font-size: 11px; }")
        vfs_layout = QGridLayout(vfs_group)
        vfs_layout.setContentsMargins(8, 8, 8, 8)
        vfs_layout.setSpacing(4)

        self.lbl_rchar = QLabel("rchar: —")
        self.lbl_wchar = QLabel("wchar: —")
        self.lbl_syscr = QLabel("syscr: —")
        self.lbl_syscw = QLabel("syscw: —")
        self.lbl_rchar_rate = QLabel("Rate: —")
        self.lbl_wchar_rate = QLabel("Rate: —")
        self.lbl_syscr_rate = QLabel("Rate: —")
        self.lbl_syscw_rate = QLabel("Rate: —")

        for lbl in (self.lbl_rchar, self.lbl_wchar, self.lbl_syscr, self.lbl_syscw):
            lbl.setFont(QFont("Monospace", 10))
            lbl.setStyleSheet("color: #f8fafc;")

        for lbl in (self.lbl_rchar_rate, self.lbl_wchar_rate, self.lbl_syscr_rate, self.lbl_syscw_rate):
            lbl.setFont(QFont("Monospace", 9))
            lbl.setStyleSheet("color: #38bdf8;")

        vfs_layout.addWidget(self.lbl_rchar, 0, 0)
        vfs_layout.addWidget(self.lbl_rchar_rate, 0, 1)
        vfs_layout.addWidget(self.lbl_wchar, 1, 0)
        vfs_layout.addWidget(self.lbl_wchar_rate, 1, 1)
        vfs_layout.addWidget(self.lbl_syscr, 2, 0)
        vfs_layout.addWidget(self.lbl_syscr_rate, 2, 1)
        vfs_layout.addWidget(self.lbl_syscw, 3, 0)
        vfs_layout.addWidget(self.lbl_syscw_rate, 3, 1)

        grid.addWidget(vfs_group, 0, 0)

        # 3. Storage Block Device Layer Card
        disk_group = QGroupBox("💽 Storage / Block Device Layer (read_bytes / write_bytes)")
        disk_group.setStyleSheet("QGroupBox { font-weight: bold; color: #cbd5e1; font-size: 11px; }")
        disk_layout = QGridLayout(disk_group)
        disk_layout.setContentsMargins(8, 8, 8, 8)
        disk_layout.setSpacing(4)

        self.lbl_read_bytes = QLabel("read_bytes: —")
        self.lbl_write_bytes = QLabel("write_bytes: —")
        self.lbl_cancelled = QLabel("cancelled_write: —")
        self.lbl_read_rate = QLabel("Rate: —")
        self.lbl_write_rate = QLabel("Rate: —")

        for lbl in (self.lbl_read_bytes, self.lbl_write_bytes, self.lbl_cancelled):
            lbl.setFont(QFont("Monospace", 10))
            lbl.setStyleSheet("color: #f8fafc;")

        for lbl in (self.lbl_read_rate, self.lbl_write_rate):
            lbl.setFont(QFont("Monospace", 9))
            lbl.setStyleSheet("color: #38bdf8;")

        disk_layout.addWidget(self.lbl_read_bytes, 0, 0)
        disk_layout.addWidget(self.lbl_read_rate, 0, 1)
        disk_layout.addWidget(self.lbl_write_bytes, 1, 0)
        disk_layout.addWidget(self.lbl_write_rate, 1, 1)
        disk_layout.addWidget(self.lbl_cancelled, 2, 0)

        grid.addWidget(disk_group, 0, 1)
        layout.addLayout(grid)

    def update_io(self, snap: ProcessIoSnapshot | None, rates: DerivedProcessIoRates | None):
        if snap is None:
            self.lbl_rchar.setText("rchar: N/A")
            self.lbl_wchar.setText("wchar: N/A")
            self.lbl_syscr.setText("syscr: N/A")
            self.lbl_syscw.setText("syscw: N/A")
            self.lbl_read_bytes.setText("read_bytes: N/A")
            self.lbl_write_bytes.setText("write_bytes: N/A")
            self.lbl_cancelled.setText("cancelled_write: N/A")
            self.lbl_rchar_rate.setText("Rate: —")
            self.lbl_wchar_rate.setText("Rate: —")
            self.lbl_syscr_rate.setText("Rate: —")
            self.lbl_syscw_rate.setText("Rate: —")
            self.lbl_read_rate.setText("Rate: —")
            self.lbl_write_rate.setText("Rate: —")
            return

        self.lbl_rchar.setText(f"rchar: {format_bytes_human(snap.rchar)} ({snap.rchar:,} B)")
        self.lbl_wchar.setText(f"wchar: {format_bytes_human(snap.wchar)} ({snap.wchar:,} B)")
        self.lbl_syscr.setText(f"syscr: {snap.syscr:,} calls")
        self.lbl_syscw.setText(f"syscw: {snap.syscw:,} calls")

        self.lbl_read_bytes.setText(f"read_bytes: {format_bytes_human(snap.read_bytes)} ({snap.read_bytes:,} B)")
        self.lbl_write_bytes.setText(f"write_bytes: {format_bytes_human(snap.write_bytes)} ({snap.write_bytes:,} B)")
        self.lbl_cancelled.setText(f"cancelled_write: {format_bytes_human(snap.cancelled_write_bytes)}")

        if rates is not None:
            self.lbl_rchar_rate.setText(f"➔ {format_rate_human(rates.rchar_per_sec)} [DERIVED]")
            self.lbl_wchar_rate.setText(f"➔ {format_rate_human(rates.wchar_per_sec)} [DERIVED]")
            self.lbl_syscr_rate.setText(f"➔ {rates.syscr_per_sec:.1f} syscalls/s [DERIVED]")
            self.lbl_syscw_rate.setText(f"➔ {rates.syscw_per_sec:.1f} syscalls/s [DERIVED]")
            self.lbl_read_rate.setText(f"➔ {format_rate_human(rates.read_bytes_per_sec)} [DERIVED]")
            self.lbl_write_rate.setText(f"➔ {format_rate_human(rates.write_bytes_per_sec)} [DERIVED]")
        else:
            self.lbl_rchar_rate.setText("Awaiting baseline...")
            self.lbl_wchar_rate.setText("Awaiting baseline...")
            self.lbl_syscr_rate.setText("Awaiting baseline...")
            self.lbl_syscw_rate.setText("Awaiting baseline...")
            self.lbl_read_rate.setText("Awaiting baseline...")
            self.lbl_write_rate.setText("Awaiting baseline...")


class SystemTelemetryWidget(QTabWidget):
    """
    Secondary system-wide telemetry tabs for /proc/diskstats and /proc/locks.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                background-color: rgba(15, 23, 42, 0.7);
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #334155;
                color: #38bdf8;
            }
        """)

        # Tab 1: Diskstats
        self.disk_table = QTableWidget()
        self.disk_table.setColumnCount(7)
        self.disk_table.setHorizontalHeaderLabels([
            "DEVICE",
            "READS COMPLETED",
            "SECTORS READ",
            "WRITES COMPLETED",
            "SECTORS WRITTEN",
            "I/O IN PROGRESS",
            "I/O TIME (ms)",
        ])
        self.disk_table.verticalHeader().setVisible(False)
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.addTab(self.disk_table, "💽 Storage Devices (/proc/diskstats)")

        # Tab 2: Locks
        self.lock_table = QTableWidget()
        self.lock_table.setColumnCount(7)
        self.lock_table.setHorizontalHeaderLabels([
            "LOCK #",
            "TYPE",
            "STATE",
            "MODE",
            "PID",
            "MAJ:MIN:INODE",
            "BYTE RANGE",
        ])
        self.lock_table.verticalHeader().setVisible(False)
        self.lock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.addTab(self.lock_table, "🔒 Kernel File Locks (/proc/locks)")

    def update_diskstats(self, stats: list[DiskDeviceStat]):
        self.disk_table.setRowCount(len(stats))
        for row, item in enumerate(stats):
            self.disk_table.setItem(row, 0, QTableWidgetItem(item.device_name))
            self.disk_table.setItem(row, 1, QTableWidgetItem(f"{item.reads_completed:,}"))
            self.disk_table.setItem(row, 2, QTableWidgetItem(f"{item.sectors_read:,}"))
            self.disk_table.setItem(row, 3, QTableWidgetItem(f"{item.writes_completed:,}"))
            self.disk_table.setItem(row, 4, QTableWidgetItem(f"{item.sectors_written:,}"))
            self.disk_table.setItem(row, 5, QTableWidgetItem(str(item.io_in_progress)))
            self.disk_table.setItem(row, 6, QTableWidgetItem(f"{item.io_time_ms:,}"))

    def update_locks(self, locks: list[KernelFileLock]):
        self.lock_table.setRowCount(len(locks))
        for row, lock in enumerate(locks):
            self.lock_table.setItem(row, 0, QTableWidgetItem(str(lock.lock_num)))
            self.lock_table.setItem(row, 1, QTableWidgetItem(lock.lock_type))
            self.lock_table.setItem(row, 2, QTableWidgetItem(lock.state))
            self.lock_table.setItem(row, 3, QTableWidgetItem(lock.mode))
            self.lock_table.setItem(row, 4, QTableWidgetItem(str(lock.pid) if lock.pid else "—"))
            self.lock_table.setItem(row, 5, QTableWidgetItem(lock.maj_min_ino))
            self.lock_table.setItem(row, 6, QTableWidgetItem(f"{lock.start_pos} - {lock.end_pos}"))


class IoLabWidget(BaseVisualizer):
    """
    Main educational workspace for Linux File Descriptors & System I/O.
    Adheres strictly to the Linux as Truth principle, focus-driven observation rule,
    and single source of truth for process existence via ProcessRegistry snapshots.
    """

    process_chosen = Signal(int)  # Emitted when user explicitly selects/pins a PID
    follow_mode_requested = Signal()  # Emitted when user returns to Follow Focused Shell mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pid: int | None = None
        self._pinned_pid: int | None = None
        self._is_pinned: bool = False
        self._processes: dict[int, Process] = {}
        self._focused_pid: int | None = None
        self._category_filter: str = "all"
        self._current_state: ProcessIoState | None = None
        self._is_updating_ui: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ----------------------------------------------------
        # 1. TOP PROCESS CONTEXT & SCOPE CONTROL BAR
        # ----------------------------------------------------
        context_bar = QFrame()
        context_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        context_layout = QVBoxLayout(context_bar)
        context_layout.setContentsMargins(6, 4, 6, 4)
        context_layout.setSpacing(6)

        # Top line: Status Title + Scope Badge
        top_line = QHBoxLayout()
        top_line.setSpacing(10)

        self.proc_title_lbl = QLabel("📍 Following: No process selected")
        self.proc_title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #f8fafc;")
        top_line.addWidget(self.proc_title_lbl)

        top_line.addStretch()

        self.scope_badge = QLabel("● Scope: Selected process (+ resolved peer endpoints)")
        self.scope_badge.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid #059669;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        top_line.addWidget(self.scope_badge)
        context_layout.addLayout(top_line)

        # Bottom line: Observation Mode Buttons + Category Filter + Process Picker
        ctrl_line = QHBoxLayout()
        ctrl_line.setSpacing(6)

        self.mode_follow_btn = QPushButton("🎯 Follow Focused Shell")
        self.mode_follow_btn.setCheckable(True)
        self.mode_follow_btn.setChecked(True)
        self.mode_follow_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 3px 8px;
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
        ctrl_line.addWidget(self.mode_follow_btn)

        self.mode_pin_btn = QPushButton("📌 Pin Process")
        self.mode_pin_btn.setCheckable(True)
        self.mode_pin_btn.setChecked(False)
        self.mode_pin_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 3px 8px;
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
        ctrl_line.addWidget(self.mode_pin_btn)

        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        ctrl_line.addWidget(filter_lbl)

        self.category_combo = QComboBox()
        self.category_combo.setStyleSheet("""
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
        self.category_combo.addItem("All Running Processes", "all")
        self.category_combo.addItem(f"👤 My User Processes (UID {os.getuid()})", "user")
        self.category_combo.addItem("🏛️ Session Leaders without Controlling TTY", "session_leaders_no_tty")
        self.category_combo.addItem("⚪ No Controlling TTY (tty_nr: 0)", "no_tty")
        self.category_combo.addItem("👑 Process Group Leaders", "pgid_leaders")
        self.category_combo.addItem("🐚 Shell Sessions", "shells")
        ctrl_line.addWidget(self.category_combo)

        proc_lbl = QLabel("Process:")
        proc_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        ctrl_line.addWidget(proc_lbl)

        self.proc_combo = QComboBox()
        self.proc_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.proc_combo.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
                min-width: 260px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                selection-background-color: #334155;
                selection-color: #38bdf8;
            }
        """)
        ctrl_line.addWidget(self.proc_combo, 1)

        context_layout.addLayout(ctrl_line)
        layout.addWidget(context_bar)

        # ----------------------------------------------------
        # 2. MAIN SPLITTER (Table on top, Details on bottom)
        # ----------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Top section: FD Table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        table_hdr = QLabel("🗂️ OPEN FILE DESCRIPTORS (/proc/<pid>/fd/)")
        table_hdr.setStyleSheet("font-size: 11px; font-weight: bold; color: #94a3b8;")
        table_layout.addWidget(table_hdr)

        self.fd_table = FdTableWidget()
        table_layout.addWidget(self.fd_table)
        splitter.addWidget(table_container)

        # Bottom section: Horizontal Splitter (Inspector + I/O Stats + Telemetry)
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setChildrenCollapsible(False)

        self.fd_inspector = SelectedFdInspector()
        bottom_splitter.addWidget(self.fd_inspector)

        self.io_stats_widget = ProcessIoStatsWidget()
        bottom_splitter.addWidget(self.io_stats_widget)

        splitter.addWidget(bottom_splitter)

        # 3. Secondary Telemetry (Collapsible Tabs)
        self.telemetry_widget = SystemTelemetryWidget()
        splitter.addWidget(self.telemetry_widget)

        # Splitter proportions
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        layout.addWidget(splitter, 1)

        # Wire table selection to inspector
        self.fd_table.fd_selected.connect(self._on_fd_selected)

        # Wire top control signals
        self.mode_follow_btn.clicked.connect(self._on_follow_clicked)
        self.mode_pin_btn.clicked.connect(self._on_pin_clicked)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        self.proc_combo.currentIndexChanged.connect(self._on_proc_combo_changed)

    @property
    def is_pinned(self) -> bool:
        return self._is_pinned

    @property
    def pinned_pid(self) -> int | None:
        return self._pinned_pid

    def _on_follow_clicked(self):
        self._is_pinned = False
        self._pinned_pid = None
        self.mode_follow_btn.setChecked(True)
        self.mode_pin_btn.setChecked(False)
        self.follow_mode_requested.emit()

    def _on_pin_clicked(self):
        if self.current_pid is not None:
            self._is_pinned = True
            self._pinned_pid = self.current_pid
            self.mode_follow_btn.setChecked(False)
            self.mode_pin_btn.setChecked(True)
            self._update_title_label()
        else:
            self.mode_pin_btn.setChecked(False)

    def pin_pid(self, pid: int | None):
        """Pin observation to a specific PID."""
        self._is_pinned = True
        self._pinned_pid = pid
        self.mode_follow_btn.setChecked(False)
        self.mode_pin_btn.setChecked(True)
        if pid is not None:
            p = self._processes.get(pid)
            cmd = p.command if p else ""
            self.set_target_process(pid, cmd)
        else:
            self.set_target_process(None)

    def unpin(self):
        """Return to Follow Focused Terminal mode."""
        self._is_pinned = False
        self._pinned_pid = None
        self.mode_follow_btn.setChecked(True)
        self.mode_pin_btn.setChecked(False)
        self._update_title_label()

    def _on_category_changed(self, index: int):
        self._category_filter = self.category_combo.currentData() or "all"
        self._rebuild_proc_combo()

    def _on_proc_combo_changed(self, index: int):
        if self._is_updating_ui:
            return
        selected_pid = self.proc_combo.currentData()
        if selected_pid is None:
            return

        # Idempotent check: if already targeting this PID and pinned, do nothing
        if selected_pid == self.current_pid and self._is_pinned:
            return

        self._is_pinned = True
        self._pinned_pid = selected_pid
        self.mode_follow_btn.setChecked(False)
        self.mode_pin_btn.setChecked(True)

        p = self._processes.get(selected_pid)
        cmd = p.command if p else ""
        self.set_target_process(selected_pid, cmd)
        self.process_chosen.emit(selected_pid)

    def _filter_processes(self, processes: dict[int, Process], category: str) -> list[Process]:
        procs = list(processes.values())
        if category == "user":
            current_uid = os.getuid()
            procs = [p for p in procs if p.uid == current_uid]
        elif category == "session_leaders_no_tty":
            procs = [p for p in procs if p.is_session_leader and p.tty_nr == 0]
        elif category == "no_tty":
            procs = [p for p in procs if p.tty_nr == 0]
        elif category == "pgid_leaders":
            procs = [p for p in procs if p.is_process_group_leader]
        elif category == "shells":
            procs = [
                p for p in procs
                if (self._focused_pid and p.pid == self._focused_pid)
                or p.command in ("bash", "zsh", "sh", "fish", "dash", "ksh", "csh", "tcsh")
            ]
        return sorted(procs, key=lambda p: p.pid)

    def _rebuild_proc_combo(self):
        self._is_updating_ui = True
        try:
            self.proc_combo.blockSignals(True)
            self.proc_combo.clear()

            filtered = self._filter_processes(self._processes, self._category_filter)

            current_in_filtered = any(p.pid == self.current_pid for p in filtered)
            if self.current_pid is not None and not current_in_filtered and self.current_pid in self._processes:
                p_curr = self._processes[self.current_pid]
                tty_str = p_curr.tty.replace("/dev/", "") if p_curr.tty else "no tty"
                self.proc_combo.addItem(
                    f"⭐ PID {p_curr.pid} — {p_curr.command} (SID: {p_curr.sid}, {tty_str}, {p_curr.user_name})",
                    p_curr.pid,
                )

            for p in filtered:
                tty_str = p.tty.replace("/dev/", "") if p.tty else "no tty"
                self.proc_combo.addItem(
                    f"PID {p.pid} — {p.command} (SID: {p.sid}, {tty_str}, {p.user_name})",
                    p.pid,
                )

            if self.current_pid is not None:
                for idx in range(self.proc_combo.count()):
                    if self.proc_combo.itemData(idx) == self.current_pid:
                        self.proc_combo.setCurrentIndex(idx)
                        break
        finally:
            self.proc_combo.blockSignals(False)
            self._is_updating_ui = False

    def _sync_combo_selection(self, pid: int | None):
        if pid is None:
            return
        self._is_updating_ui = True
        try:
            self.proc_combo.blockSignals(True)
            found = False
            for idx in range(self.proc_combo.count()):
                if self.proc_combo.itemData(idx) == pid:
                    self.proc_combo.setCurrentIndex(idx)
                    found = True
                    break
            if not found and pid in self._processes:
                p = self._processes[pid]
                tty_str = p.tty.replace("/dev/", "") if p.tty else "no tty"
                self.proc_combo.insertItem(
                    0,
                    f"⭐ PID {p.pid} — {p.command} (SID: {p.sid}, {tty_str}, {p.user_name})",
                    p.pid,
                )
                self.proc_combo.setCurrentIndex(0)
        finally:
            self.proc_combo.blockSignals(False)
            self._is_updating_ui = False

    def _update_title_label(self, command: str = ""):
        if self.current_pid is None:
            mode_prefix = "📌 Pinned:" if self._is_pinned else "📍 Following:"
            self.proc_title_lbl.setText(f"{mode_prefix} No process selected")
            return

        if not command and self.current_pid in self._processes:
            command = self._processes[self.current_pid].command

        badge = format_identity_badge_html(self.current_pid, "PID")
        cmd_text = f" — <b>{command}</b>" if command else ""
        mode_prefix = "📌 Pinned:" if self._is_pinned else "📍 Following:"
        self.proc_title_lbl.setText(f"{mode_prefix} {badge}{cmd_text}")

    def select_pid(self, pid: int | None, command: str = ""):
        """
        Idempotent programmatic PID selection.
        Does not emit signals or loop if PID is already active.
        """
        if self.current_pid == pid:
            self._update_title_label(command)
            return

        self.set_target_process(pid, command)
        self._sync_combo_selection(pid)

    def set_target_process(self, pid: int | None, command: str = ""):
        """Update the target process tracked in the FD Lab."""
        self.current_pid = pid
        self.fd_inspector._current_pid = pid

        if pid is None:
            self._update_title_label()
            self.clear_context()
        else:
            self._update_title_label(command)

    def update_process_list(self, processes: dict[int, Process], focused_pid: int | None = None):
        """
        Authoritative process update forwarded from ProcessRegistry.
        Single source of truth for process existence.
        """
        self._processes = dict(processes)
        self._focused_pid = focused_pid

        # 1. Handle pinned process exit on authoritative ProcessRegistry snapshot
        if self._is_pinned and self._pinned_pid is not None:
            if self._pinned_pid not in processes:
                # Process exited in authoritative registry snapshot
                self.clear_context()
                self.current_pid = None
                self.proc_title_lbl.setText(
                    f"📌 Pinned: PID {self._pinned_pid} <span style='color: #f59e0b;'>⚠️ Process exited / no longer present in /proc</span>"
                )
            else:
                p = processes[self._pinned_pid]
                self.set_target_process(p.pid, p.command)
        else:
            # Follow mode: follow focused shell if present
            if focused_pid is not None and focused_pid in processes:
                p = processes[focused_pid]
                self.set_target_process(p.pid, p.command)
            elif not processes:
                self.clear_context()
                self.current_pid = None
                self.proc_title_lbl.setText("📍 Following: No process selected")

        # 2. Rebuild picker options
        self._rebuild_proc_combo()

    def update_io_state(self, state: ProcessIoState):
        """Update visualizer with newly sampled ProcessIoState."""
        self._current_state = state
        if self.current_pid is None or self.current_pid == state.pid:
            self.current_pid = state.pid
            self.fd_inspector._current_pid = state.pid

        if state.error_reason:
            if state.error_reason == "EACCES":
                self.proc_title_lbl.setText(
                    f"📍 Target PID {state.pid} <span style='color: #ef4444;'>🔒 EACCES (Permission Denied - Process owned by another user)</span>"
                )
            elif state.error_reason == "ESRCH":
                self.proc_title_lbl.setText(
                    f"📍 Target PID {state.pid} <span style='color: #f59e0b;'>⚠️ Process not currently observable to IO subsystem</span>"
                )
            self.fd_table.populate([])
            self.fd_inspector.update_fd(None)
            self.io_stats_widget.update_io(None, None)
            return

        self._update_title_label()
        self.fd_table.populate(state.descriptors)
        self.io_stats_widget.update_io(state.io_snapshot, state.derived_rates)

        # Update inspector with current selection
        selected_fd = self.fd_table.get_selected_fd_num()
        current_fd_obj = None
        if selected_fd is not None:
            for fd_obj in state.descriptors:
                if fd_obj.fd == selected_fd:
                    current_fd_obj = fd_obj
                    break

        self.fd_inspector.update_fd(current_fd_obj, state.resolved_pipes)

    def update_diskstats(self, stats: list[DiskDeviceStat]):
        self.telemetry_widget.update_diskstats(stats)

    def update_locks(self, locks: list[KernelFileLock]):
        self.telemetry_widget.update_locks(locks)

    def _on_fd_selected(self, fd_obj: FileDescriptor | None):
        resolved_pipes = self._current_state.resolved_pipes if self._current_state else {}
        self.fd_inspector.update_fd(fd_obj, resolved_pipes)

    def clear_context(self):
        super().clear_context()
        self.fd_table.populate([])
        self.fd_inspector.update_fd(None)
        self.io_stats_widget.update_io(None, None)

    def render_context(self, fs_object: Any):
        pass
