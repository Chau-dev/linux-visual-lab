from __future__ import annotations

import stat
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QGroupBox,
    QFrame,
    QScrollArea,
)

from app.models.filesystem_object import FilesystemObject
from app.visualizers.base import BaseVisualizer


class PermissionSimulatorWidget(BaseVisualizer):
    """
    Interactive Permission Lab.

    Visually explains:
    1. Special Mode Bits (SUID, SGID, Sticky) and Symbolic mapping
    2. 3x3 Standard Permission Matrix with additive arithmetic
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        # Scroll Area for clean UI fit on smaller screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(12)

        # ====================================================
        # 1. HEADER: File Info, Symbolic & Octal Modes
        # ====================================================
        header_box = QGroupBox("📄 Target File & Mode Overview")
        header_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; }")
        header_layout = QFormLayout(header_box)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(6)

        self.file_name_label = QLabel("No file selected")
        self.file_name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addRow("File:", self.file_name_label)

        self.ownership_label = QLabel("-")
        header_layout.addRow("Ownership:", self.ownership_label)

        self.symbolic_label = QLabel("-")
        self.symbolic_label.setStyleSheet("font-family: monospace; font-size: 14px; font-weight: bold;")
        header_layout.addRow("Symbolic Mode:", self.symbolic_label)

        self.octal_label = QLabel("-")
        self.octal_label.setStyleSheet("font-family: monospace; font-size: 14px; font-weight: bold;")
        header_layout.addRow("Numeric (Octal):", self.octal_label)

        layout.addWidget(header_box)

        # ====================================================
        # 2. SPECIAL MODE BITS (SUID, SGID, STICKY)
        # ====================================================
        special_box = QGroupBox("🔐 Special Mode Bits (Kernel Flags)")
        special_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; }")
        special_layout = QHBoxLayout(special_box)
        special_layout.setContentsMargins(10, 10, 10, 10)
        special_layout.setSpacing(10)

        self.suid_badge = self._create_badge_widget("SUID (4000)", "Runs with File Owner UID")
        self.sgid_badge = self._create_badge_widget("SGID (2000)", "Runs with File Group GID / Inherits Dir Group")
        self.sticky_badge = self._create_badge_widget("STICKY (1000)", "Only Owner/Root can delete in dir (e.g. /tmp)")

        special_layout.addWidget(self.suid_badge["frame"])
        special_layout.addWidget(self.sgid_badge["frame"])
        special_layout.addWidget(self.sticky_badge["frame"])

        layout.addWidget(special_box)

        # ====================================================
        # 3. 3x3 PERMISSION MATRIX & ADDITIVE MATH
        # ====================================================
        matrix_box = QGroupBox("📊 3x3 Standard Permission Matrix")
        matrix_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 13px; }")
        matrix_vbox = QVBoxLayout(matrix_box)
        matrix_vbox.setContentsMargins(10, 10, 10, 10)
        matrix_vbox.setSpacing(8)

        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(16)
        self.grid_layout.setVerticalSpacing(4)

        # Column Headers
        for col, header in enumerate(["", "OWNER (User)", "GROUP", "OTHER (World)"], start=0):
            lbl = QLabel(header)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
            self.grid_layout.addWidget(lbl, 0, col)

        # Rows
        self.matrix_cells = {}
        rows = [
            ("READ (4)", "r"),
            ("WRITE (2)", "w"),
            ("EXECUTE (1)", "x"),
        ]

        for row_idx, (row_label, _) in enumerate(rows, start=1):
            lbl = QLabel(row_label)
            lbl.setStyleSheet("font-weight: bold;")
            self.grid_layout.addWidget(lbl, row_idx, 0)

            for col_idx, category in enumerate(["owner", "group", "other"], start=1):
                cell = QLabel("—")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px; border: 1px solid #444; border-radius: 4px;")
                self.grid_layout.addWidget(cell, row_idx, col_idx)
                self.matrix_cells[(category, row_idx)] = cell

        matrix_vbox.addWidget(grid_widget)

        self.math_label = QLabel("Permission math: -")
        self.math_label.setStyleSheet("font-family: monospace; font-size: 12px; padding: 4px;")
        matrix_vbox.addWidget(self.math_label)

        layout.addWidget(matrix_box)

        layout.addStretch(1)

    def _create_badge_widget(self, title: str, description: str) -> dict:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame { border: 1px solid #555; border-radius: 6px; padding: 4px; }")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_lbl = QLabel("OFF")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #888;")

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 10px; color: #aaa;")

        layout.addWidget(title_lbl)
        layout.addWidget(status_lbl)
        layout.addWidget(desc_lbl)

        return {"frame": frame, "status": status_lbl}

    def render_context(self, fs_object: FilesystemObject):
        """
        Populate the visualizer with data from the domain model.
        """
        # Header Info
        self.file_name_label.setText(f"{fs_object.name}  ({fs_object.file_type})")
        self.ownership_label.setText(
            f"UID {fs_object.uid} ({fs_object.owner_name})  •  GID {fs_object.gid} ({fs_object.group_name})"
        )
        self.symbolic_label.setText(fs_object.symbolic_mode)
        self.octal_label.setText(f"0{fs_object.octal_mode}  (Decimal: {fs_object.permission_mode})")

        # Special Mode Badges
        self._update_badge(self.suid_badge, fs_object.suid, "ON (SetUID active)", "OFF (Normal)")
        self._update_badge(self.sgid_badge, fs_object.sgid, "ON (SetGID active)", "OFF (Normal)")
        self._update_badge(self.sticky_badge, fs_object.sticky, "ON (Sticky active)", "OFF (Normal)")

        # 3x3 Matrix
        matrix_vals = {
            ("owner", 1): fs_object.owner_r,
            ("owner", 2): fs_object.owner_w,
            ("owner", 3): fs_object.owner_x,
            ("group", 1): fs_object.group_r,
            ("group", 2): fs_object.group_w,
            ("group", 3): fs_object.group_x,
            ("other", 1): fs_object.other_r,
            ("other", 2): fs_object.other_w,
            ("other", 3): fs_object.other_x,
        }

        for (cat, row_idx), cell in self.matrix_cells.items():
            is_set = matrix_vals.get((cat, row_idx), False)
            if is_set:
                cell.setText("✓")
                cell.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px; background-color: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid #2ecc71; border-radius: 4px;")
            else:
                cell.setText("✗")
                cell.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px; background-color: rgba(231, 76, 60, 0.1); color: #e74c3c; border: 1px solid #555; border-radius: 4px;")

        # Permission Arithmetic Explanation
        owner_math = self._format_octal_math(fs_object.owner_r, fs_object.owner_w, fs_object.owner_x)
        group_math = self._format_octal_math(fs_object.group_r, fs_object.group_w, fs_object.group_x)
        other_math = self._format_octal_math(fs_object.other_r, fs_object.other_w, fs_object.other_x)

        self.math_label.setText(
            f"Permission Math Breakdown:\n"
            f"  OWNER = {owner_math}\n"
            f"  GROUP = {group_math}\n"
            f"  OTHER = {other_math}"
        )

    def _format_octal_math(self, r: bool, w: bool, x: bool) -> str:
        parts = []
        val = 0
        if r:
            parts.append("4 (r)")
            val += 4
        if w:
            parts.append("2 (w)")
            val += 2
        if x:
            parts.append("1 (x)")
            val += 1
        if not parts:
            return "0 = 0"
        return f"{' + '.join(parts)} = {val}"

    def _update_badge(self, badge: dict, is_on: bool, on_text: str, off_text: str):
        if is_on:
            badge["status"].setText(on_text)
            badge["status"].setStyleSheet("font-weight: bold; font-size: 12px; color: #f39c12;")
            badge["frame"].setStyleSheet("QFrame { border: 2px solid #f39c12; border-radius: 6px; padding: 4px; background-color: rgba(243, 156, 18, 0.1); }")
        else:
            badge["status"].setText(off_text)
            badge["status"].setStyleSheet("font-weight: bold; font-size: 12px; color: #777;")
            badge["frame"].setStyleSheet("QFrame { border: 1px solid #444; border-radius: 6px; padding: 4px; }")

    def clear_context(self):
        super().clear_context()
        self.file_name_label.setText("No file selected")
        self.ownership_label.setText("-")
        self.symbolic_label.setText("-")
        self.octal_label.setText("-")
        self._update_badge(self.suid_badge, False, "", "OFF")
        self._update_badge(self.sgid_badge, False, "", "OFF")
        self._update_badge(self.sticky_badge, False, "", "OFF")

        for cell in self.matrix_cells.values():
            cell.setText("—")
            cell.setStyleSheet("font-size: 14px; padding: 4px; border: 1px solid #444; border-radius: 4px;")

        self.math_label.setText("Permission math: -")
