from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)


class ContextPanel(QFrame):
    """
    Top Context Banner displaying the focused shell's current location,
    visual breadcrumb trail, parent/home/root indicators, and path anatomy.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # 1. Location Header
        self.location_label = QLabel("📍 CURRENT LOCATION: unknown")
        self.location_label.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #60a5fa;
            }
            """
        )
        layout.addWidget(self.location_label)

        # 2. Breadcrumb Trail
        self.breadcrumb_label = QLabel("/")
        self.breadcrumb_label.setWordWrap(True)
        self.breadcrumb_label.setStyleSheet(
            """
            QLabel {
                font-size: 13px;
                font-weight: 500;
                color: #e2e8f0;
            }
            """
        )
        layout.addWidget(self.breadcrumb_label)

        # 3. Navigation info (Parent, Home, Root)
        self.navigation_label = QLabel("Parent: /    |    Home: /    |    Root: /")
        self.navigation_label.setWordWrap(True)
        self.navigation_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(self.navigation_label)

        # 4. Path Anatomy breakdown
        self.path_anatomy_label = QLabel("Path anatomy: /")
        self.path_anatomy_label.setWordWrap(True)
        self.path_anatomy_label.setStyleSheet(
            """
            QLabel {
                font-size: 11px;
                color: #cbd5e1;
                font-family: monospace;
            }
            """
        )
        layout.addWidget(self.path_anatomy_label)

    def set_location(self, path: Path | str | None):
        """Update the context banner with the current working directory."""
        if path is None:
            self.show_unknown()
            return

        try:
            current_dir = Path(path).resolve()
        except OSError:
            self.show_unknown()
            return

        # Location header
        self.location_label.setText(f"📍 CURRENT LOCATION: {current_dir}")

        # Breadcrumb trail
        parts = current_dir.parts
        if not parts or parts == ('/',):
            breadcrumb = "ROOT (/)"
        else:
            breadcrumb = "  →  ".join(parts)
        self.breadcrumb_label.setText(breadcrumb)

        # Navigation
        parent_dir = current_dir.parent
        home_dir = Path.home()
        self.navigation_label.setText(
            f"Parent: {parent_dir}    |    Home: {home_dir}    |    Root: /"
        )

        # Path Anatomy
        if not parts:
            anatomy = "ROOT (/)"
        else:
            pieces = []
            for idx, part in enumerate(parts):
                if part == "/":
                    pieces.append("ROOT (/)")
                else:
                    pieces.append(f"{idx}: {part}")
            anatomy = "  |  ".join(pieces)
        self.path_anatomy_label.setText(f"Path anatomy: {anatomy}")

    def show_unknown(self):
        """Display placeholder state when no terminal is focused or CWD is unavailable."""
        self.location_label.setText("📍 CURRENT LOCATION: unknown")
        self.breadcrumb_label.setText("/")
        self.navigation_label.setText("Parent: unknown    |    Home: /    |    Root: /")
        self.path_anatomy_label.setText("Path anatomy: unknown")
