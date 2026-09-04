from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QLineEdit,
    QPushButton,
    QComboBox,
)

from app.core.events import SystemEvent


class EventCardWidget(QFrame):
    """
    A rich, educational visual card representing a single Linux kernel/filesystem event.
    """

    def __init__(self, event: SystemEvent, parent=None):
        super().__init__(parent)
        self.system_event = event

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        event_type = event.event_type
        data = event.data or {}
        timestamp_str = event.timestamp.strftime("%H:%M:%S")

        # ----------------------------------------------------
        # 1. HEADER ROW: Category Badge + Timestamp + PID
        # ----------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        badge_info = self._get_badge_info(event_type)
        self.badge_lbl = QLabel(badge_info["title"])
        self.badge_lbl.setStyleSheet(
            f"""
            QLabel {{
                background-color: {badge_info["bg_color"]};
                color: {badge_info["text_color"]};
                font-weight: bold;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid {badge_info["border_color"]};
            }}
            """
        )
        header_layout.addWidget(self.badge_lbl)

        # PID badge (if applicable)
        pid = data.get("pid")
        if pid is not None:
            from app.ui.identity import get_identity_style
            bg, fg, border = get_identity_style(pid)
            pid_lbl = QLabel(f"PID {pid}")
            pid_lbl.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {border};
                    font-size: 10px;
                    font-weight: bold;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-family: monospace;
                }}
                """
            )
            header_layout.addWidget(pid_lbl)

        header_layout.addStretch(1)

        time_lbl = QLabel(f"🕒 {timestamp_str}")
        time_lbl.setStyleSheet("color: #888; font-size: 11px; font-family: monospace;")
        header_layout.addWidget(time_lbl)

        layout.addLayout(header_layout)

        # ----------------------------------------------------
        # 2. TARGET / ACTION DESCRIPTION
        # ----------------------------------------------------
        target_text = self._format_target_description(event_type, data)
        self.target_lbl = QLabel(target_text)
        self.target_lbl.setWordWrap(True)
        self.target_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #fff; padding-top: 2px;")
        layout.addWidget(self.target_lbl)

        # ----------------------------------------------------
        # 3. EDUCATIONAL "LINUX KERNEL INSIGHT" BOX
        # ----------------------------------------------------
        insight_frame = QFrame()
        insight_frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(255, 255, 255, 0.04);
                border-left: 3px solid #3498db;
                border-radius: 3px;
                padding: 4px 6px;
            }
            """
        )
        insight_layout = QVBoxLayout(insight_frame)
        insight_layout.setContentsMargins(4, 2, 4, 2)
        insight_layout.setSpacing(2)

        insight_text = self._get_educational_insight(event_type, data)
        insight_lbl = QLabel(f"💡 {insight_text}")
        insight_lbl.setWordWrap(True)
        insight_lbl.setStyleSheet("font-size: 11px; color: #bbb; line-height: 1.3;")
        insight_layout.addWidget(insight_lbl)

        layout.addWidget(insight_frame)

        # Container styling
        self.setStyleSheet(
            f"""
            EventCardWidget {{
                background-color: rgba(35, 39, 46, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }}
            EventCardWidget:hover {{
                border: 1px solid {badge_info["border_color"]};
                background-color: rgba(45, 50, 60, 0.95);
            }}
            """
        )

    def _get_badge_info(self, event_type: str) -> dict:
        badges = {
            "file.created": {
                "title": "📄 FILE CREATED",
                "bg_color": "rgba(46, 204, 113, 0.2)",
                "text_color": "#2ecc71",
                "border_color": "#27ae60",
            },
            "directory.created": {
                "title": "📁 DIRECTORY CREATED",
                "bg_color": "rgba(46, 204, 113, 0.25)",
                "text_color": "#2ecc71",
                "border_color": "#27ae60",
            },
            "file.modified": {
                "title": "✏️ FILE MODIFIED",
                "bg_color": "rgba(241, 196, 15, 0.2)",
                "text_color": "#f1c40f",
                "border_color": "#f39c12",
            },
            "file.deleted": {
                "title": "🗑️ FILE DELETED",
                "bg_color": "rgba(231, 76, 60, 0.2)",
                "text_color": "#e74c3c",
                "border_color": "#c0392b",
            },
            "directory.deleted": {
                "title": "🗑️ DIRECTORY DELETED",
                "bg_color": "rgba(231, 76, 60, 0.25)",
                "text_color": "#e74c3c",
                "border_color": "#c0392b",
            },
            "file.moved": {
                "title": "↔️ RENAMED / MOVED",
                "bg_color": "rgba(52, 152, 219, 0.2)",
                "text_color": "#3498db",
                "border_color": "#2980b9",
            },
            "shell.cwd_changed": {
                "title": "🐚 SHELL NAV (cd)",
                "bg_color": "rgba(155, 89, 182, 0.2)",
                "text_color": "#9b59b6",
                "border_color": "#8e44ad",
            },
            "shell.session_created": {
                "title": "🖥️ SHELL SPAWNED",
                "bg_color": "rgba(26, 188, 156, 0.2)",
                "text_color": "#1abc9c",
                "border_color": "#16a085",
            },
            "shell.session_removed": {
                "title": "🚪 SHELL EXITED",
                "bg_color": "rgba(127, 140, 141, 0.2)",
                "text_color": "#bdc3c7",
                "border_color": "#7f8c8d",
            },
            "file.permissions_changed": {
                "title": "🔐 CHMOD (Mode Changed)",
                "bg_color": "rgba(230, 126, 34, 0.2)",
                "text_color": "#e67e22",
                "border_color": "#d35400",
            },
            "process.created": {
                "title": "⚡ PROCESS CREATED",
                "bg_color": "rgba(46, 204, 113, 0.2)",
                "text_color": "#2ecc71",
                "border_color": "#27ae60",
            },
            "process.removed": {
                "title": "🚪 PROCESS REMOVED",
                "bg_color": "rgba(231, 76, 60, 0.2)",
                "text_color": "#e74c3c",
                "border_color": "#c0392b",
            },
            "process.state_changed": {
                "title": "🔄 STATE CHANGED",
                "bg_color": "rgba(241, 196, 15, 0.2)",
                "text_color": "#f1c40f",
                "border_color": "#f39c12",
            },
            "process.cwd_changed": {
                "title": "🧭 PROCESS CWD",
                "bg_color": "rgba(155, 89, 182, 0.2)",
                "text_color": "#9b59b6",
                "border_color": "#8e44ad",
            },
        }

        return badges.get(
            event_type,
            {
                "title": f"⚡ {event_type.upper()}",
                "bg_color": "rgba(255, 255, 255, 0.1)",
                "text_color": "#ddd",
                "border_color": "#555",
            },
        )

    def _format_target_description(self, event_type: str, data: dict) -> str:
        if event_type in ("file.created", "file.modified", "file.deleted", "directory.created", "directory.deleted"):
            path_str = data.get("path", "")
            try:
                p = Path(path_str)
                return f"{p.name}  ({p.parent})"
            except Exception:
                return path_str

        if event_type == "file.moved":
            old_p = data.get("old_path", "")
            new_p = data.get("new_path", "")
            try:
                old_name = Path(old_p).name
                new_name = Path(new_p).name
                return f"{old_name}  ➔  {new_name}"
            except Exception:
                return f"{old_p} ➔ {new_p}"

        if event_type == "shell.cwd_changed":
            old_cwd = data.get("old_path", "unknown")
            new_cwd = data.get("new_path", "unknown")
            return f"{old_cwd}  ➔  {new_cwd}"

        if event_type == "shell.session_created":
            cmd = data.get("command", "shell")
            tty = data.get("tty", "unknown TTY")
            cwd = data.get("cwd", "unknown")
            return f"Started '{cmd}' on {tty} at {cwd}"

        if event_type == "shell.session_removed":
            cmd = data.get("command", "shell")
            return f"Closed shell session '{cmd}'"

        if event_type == "process.created":
            pid = data.get("pid", "?")
            cmd = data.get("command", "process")
            return f"PID {pid} observed in /proc ({cmd})"

        if event_type == "process.removed":
            pid = data.get("pid", "?")
            cmd = data.get("command", "process")
            return f"PID {pid} no longer present in /proc ({cmd})"

        if event_type == "process.state_changed":
            pid = data.get("pid", "?")
            cmd = data.get("command", "process")
            old_s = data.get("old_state", "?")
            new_s = data.get("new_state", "?")
            return f"PID {pid} ({cmd}): state {old_s} ➔ {new_s}"

        if event_type == "process.cwd_changed":
            pid = data.get("pid", "?")
            cmd = data.get("command", "process")
            old_c = data.get("old_cwd", "?")
            new_c = data.get("new_cwd", "?")
            return f"PID {pid} ({cmd}): {old_c} ➔ {new_c}"

        return str(data)

    def _get_educational_insight(self, event_type: str, data: dict) -> str:
        if event_type == "file.created":
            return f"VFS Observation: Inode/dentry entry instantiated at {data.get('path', '')}."
        if event_type == "directory.created":
            return f"VFS Observation: Directory entry created at {data.get('path', '')}."
        if event_type == "file.modified":
            return f"VFS Observation: Content write or attribute modification reported for {data.get('path', '')}."
        if event_type == "file.deleted":
            return f"VFS Observation: Directory entry unlinked at {data.get('path', '')}."
        if event_type == "directory.deleted":
            return f"VFS Observation: Directory entry unlinked at {data.get('path', '')}."
        if event_type == "file.moved":
            return f"VFS Observation: Dentry rename from {data.get('old_path', '')} to {data.get('new_path', '')}."
        if event_type == "file.permissions_changed":
            return f"POSIX stat Observation: st_mode changed from {data.get('old_mode', '')} to {data.get('new_mode', '')}."
        if event_type == "shell.session_created":
            return f"/proc Observation: Shell PID {data.get('pid', '')} ({data.get('command', '')}) active on {data.get('tty', 'unknown')} with CWD {data.get('cwd', '')}."
        if event_type == "shell.session_removed":
            return f"/proc Observation: Shell PID {data.get('pid', '')} ({data.get('command', '')}) terminated."
        if event_type == "shell.cwd_changed":
            return f"/proc Observation: /proc/{data.get('pid', '')}/cwd symlink target updated to {data.get('new_path', '')}."
        if event_type == "process.created":
            return f"/proc Observation: PID {data.get('pid', '')} (/proc/{data.get('pid', '')}) newly observed in snapshot (command: {data.get('command', '')}, state: {data.get('state', '')})."
        if event_type == "process.removed":
            return f"/proc Observation: PID {data.get('pid', '')} (/proc/{data.get('pid', '')}) no longer present in snapshot (command: {data.get('command', '')})."
        if event_type == "process.state_changed":
            return f"/proc Observation: /proc/{data.get('pid', '')}/stat state field transitioned from {data.get('old_state', '')} to {data.get('new_state', '')}."
        if event_type == "process.cwd_changed":
            return f"/proc Observation: /proc/{data.get('pid', '')}/cwd symlink target updated to {data.get('new_cwd', '')}."

        return f"System Observation: {event_type} reported."


class ActivityTimelineWidget(QWidget):
    """
    Rich, educational Activity Timeline Widget for learners.

    Features:
    - Educational card layout for every Linux event
    - Category filtering (All, Filesystem, Shell Activity)
    - Live Search filtering
    - Event counter and Clear functionality
    """

    def __init__(self, parent=None, max_events: int = 100):
        super().__init__(parent)
        self.max_events = max_events

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ----------------------------------------------------
        # TOP TOOLBAR: Filter & Search
        # ----------------------------------------------------
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(2, 2, 2, 2)
        toolbar.setSpacing(6)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "🔍 All Events",
            "📁 Filesystem Only",
            "🐚 Shell & Terminal Only",
            "⚡ Process Subsystem Only",
        ])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter path, PID, or multiple (e.g. sleep, cat, bash)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit, 1)


        self.clear_btn = QPushButton("🗑️")
        self.clear_btn.setToolTip("Clear activity timeline")
        self.clear_btn.setMaximumWidth(32)
        self.clear_btn.clicked.connect(self.clear_events)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # ----------------------------------------------------
        # EVENT LIST WIDGET
        # ----------------------------------------------------
        self.list_widget = QListWidget()
        self.list_widget.setSpacing(6)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                background-color: transparent;
                padding: 0px;
                border: none;
            }
            """
        )
        layout.addWidget(self.list_widget, 1)

        # ----------------------------------------------------
        # FOOTER: Event Counter
        # ----------------------------------------------------
        self.footer_lbl = QLabel("0 events recorded")
        self.footer_lbl.setStyleSheet("font-size: 11px; color: #888; padding: 2px;")
        layout.addWidget(self.footer_lbl)

        self._all_events: list[tuple[QListWidgetItem, EventCardWidget]] = []

    def count(self) -> int:
        """Return the number of events in the timeline."""
        return len(self._all_events)

    def event_count(self) -> int:
        """Return the total number of events recorded."""
        return len(self._all_events)

    def visible_count(self) -> int:
        """Return the number of currently visible events matching filters."""
        return sum(1 for item, _ in self._all_events if not item.isHidden())

    def add_event(self, event: SystemEvent):
        """
        Add a rich educational card for a newly detected Linux event.
        """
        card = EventCardWidget(event)

        item = QListWidgetItem()
        item.setSizeHint(card.sizeHint())

        # Insert at the very top of the visual list (newest first)
        self.list_widget.insertItem(0, item)
        self.list_widget.setItemWidget(item, card)

        self._all_events.insert(0, (item, card))

        # Maintain max capacity of 100 visual items
        if len(self._all_events) > 100:
            old_item, old_card = self._all_events.pop()
            row = self.list_widget.row(old_item)
            if row >= 0:
                self.list_widget.takeItem(row)

        self._update_counter()
        self._apply_filter()
        self.list_widget.scrollToTop()

    def _apply_filter(self):
        filter_idx = self.filter_combo.currentIndex()
        query = self.search_edit.text().strip().lower()

        visible_count = 0
        for item, card in self._all_events:
            event_type = card.system_event.event_type
            data_str = str(card.system_event.data).lower()
            type_str = event_type.lower()

            # Category check
            cat_match = True
            if filter_idx == 1:  # Filesystem Only
                cat_match = event_type.startswith("file.") or event_type.startswith("directory.")
            elif filter_idx == 2:  # Shell Only
                cat_match = event_type.startswith("shell.")
            elif filter_idx == 3:  # Process Only
                cat_match = event_type.startswith("process.")

            # Search query check
            query_match = True
            if query:
                if "," in query or "|" in query:
                    import re
                    terms = [t.strip() for t in re.split(r"[,|]", query) if t.strip()]
                else:
                    tokens = [t.strip() for t in query.split() if t.strip()]
                    terms = list(dict.fromkeys([query] + tokens))

                target_text = card.target_lbl.text().lower()
                query_match = any(
                    term in data_str or term in type_str or term in target_text
                    for term in terms
                )

            is_visible = cat_match and query_match

            item.setHidden(not is_visible)
            if is_visible:
                visible_count += 1

        total = len(self._all_events)
        if total == visible_count:
            self.footer_lbl.setText(f"{total} events recorded")
        else:
            self.footer_lbl.setText(f"Showing {visible_count} of {total} events")

    def _update_counter(self):
        total = len(self._all_events)
        self.footer_lbl.setText(f"{total} events recorded")

    def clear_events(self):
        """Remove all events from the timeline."""
        self.list_widget.clear()
        self._all_events.clear()
        self._update_counter()

    def clear(self):
        """Alias for clear_events."""
        self.clear_events()
