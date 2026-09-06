from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
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
    QGridLayout,
)

from app.core.events import SystemEvent


class EventCardWidget(QFrame):
    """
    A strictly factual visual card representing an observed Linux event.
    Presents structured facts, observation source, and underlying mechanism without speculation.
    """

    def __init__(self, event: SystemEvent, parent=None):
        super().__init__(parent)
        self.system_event = event

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        event_type = event.event_type
        data = event.data or {}
        time_str = event.formatted_time

        # ----------------------------------------------------
        # 1. HEADER ROW: Category Badge + PID + Observed Time
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

        time_lbl = QLabel(f"🕒 {time_str}")
        time_lbl.setStyleSheet("color: #888; font-size: 11px; font-family: monospace;")
        header_layout.addWidget(time_lbl)

        layout.addLayout(header_layout)

        # ----------------------------------------------------
        # 2. TARGET / PRIMARY DESCRIPTION
        # ----------------------------------------------------
        target_text = self._format_target_description(event_type, data)
        self.target_lbl = QLabel(target_text)
        self.target_lbl.setWordWrap(True)
        self.target_lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #f8fafc; padding-top: 1px;")
        layout.addWidget(self.target_lbl)

        # ----------------------------------------------------
        # 3. OBSERVATION PROVENANCE & FACTS
        # ----------------------------------------------------
        details_frame = QFrame()
        details_frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 4px;
                padding: 4px 6px;
            }
            """
        )
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(6, 4, 6, 4)
        details_layout.setSpacing(4)

        # Provenance line (Source & Mechanism)
        src_text = f"📡 <b>Source:</b> {event.source}"
        if event.mechanism:
            src_text += f" &nbsp;|&nbsp; <b>Mechanism:</b> <code>{event.mechanism}</code>"

        src_lbl = QLabel(src_text)
        src_lbl.setStyleSheet("font-size: 10px; color: #94a3b8;")
        details_layout.addWidget(src_lbl)

        # Structured Facts Grid
        facts_text = self._format_facts_summary(event_type, data)
        if facts_text:
            facts_lbl = QLabel(facts_text)
            facts_lbl.setWordWrap(True)
            facts_lbl.setStyleSheet("font-size: 11px; color: #cbd5e1; font-family: monospace;")
            details_layout.addWidget(facts_lbl)

        layout.addWidget(details_frame)

        # Container styling
        self.setStyleSheet(
            f"""
            EventCardWidget {{
                background-color: rgba(30, 41, 59, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }}
            EventCardWidget:hover {{
                border: 1px solid {badge_info["border_color"]};
                background-color: rgba(40, 53, 75, 0.95);
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
            "file.permissions_changed": {
                "title": "🔐 CHMOD (MODE CHANGED)",
                "bg_color": "rgba(230, 126, 34, 0.2)",
                "text_color": "#e67e22",
                "border_color": "#d35400",
            },
            "shell.cwd_changed": {
                "title": "🐚 SHELL CWD",
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
            "memory.swap_usage_changed": {
                "title": "🔄 SWAP USAGE CHANGED",
                "bg_color": "rgba(234, 179, 8, 0.2)",
                "text_color": "#eab308",
                "border_color": "#ca8a04",
            },
            "io.fd_appeared": {
                "title": "🗂️ FD APPEARED",
                "bg_color": "rgba(56, 189, 248, 0.2)",
                "text_color": "#38bdf8",
                "border_color": "#0284c7",
            },
            "io.fd_disappeared": {
                "title": "🚪 FD DISAPPEARED",
                "bg_color": "rgba(148, 163, 184, 0.2)",
                "text_color": "#94a3b8",
                "border_color": "#64748b",
            },
            "io.pipe_shared": {
                "title": "🔗 PIPE SHARED",
                "bg_color": "rgba(234, 179, 8, 0.2)",
                "text_color": "#eab308",
                "border_color": "#ca8a04",
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

        if event_type == "file.permissions_changed":
            path_str = data.get("path", "")
            old_m = data.get("old_mode", "?")
            new_m = data.get("new_mode", "?")
            try:
                name = Path(path_str).name
                return f"{name}: mode {old_m} ➔ {new_m}"
            except Exception:
                return f"{path_str}: mode {old_m} ➔ {new_m}"

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
            return f"PID {pid} observed: {cmd}"

        if event_type == "process.removed":
            pid = data.get("pid", "?")
            cmd = data.get("command", "process")
            return f"PID {pid} exited: {cmd}"

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

        if event_type == "memory.swap_usage_changed":
            old_s = data.get("old_swap_used_kb", 0)
            new_s = data.get("new_swap_used_kb", 0)
            return f"Swap reported usage changed: {old_s:,} kB ➔ {new_s:,} kB"

        if event_type == "io.fd_appeared":
            pid = data.get("pid", "?")
            target = data.get("target", "?")
            role = data.get("role", f"fd {data.get('fd', '?')}")
            return f"PID {pid} opened {role} ➔ {target}"

        if event_type == "io.fd_disappeared":
            pid = data.get("pid", "?")
            target = data.get("target", "?")
            role = data.get("role", f"fd {data.get('fd', '?')}")
            return f"PID {pid} closed {role} ({target})"

        if event_type == "io.pipe_shared":
            ino = data.get("pipe_inode", "?")
            count = data.get("endpoints_count", 2)
            return f"Observed {count} process endpoints sharing pipe:[{ino}]"

        return str(data)

    def _format_facts_summary(self, event_type: str, data: dict) -> str:
        """Format strictly observed structured facts."""
        facts: list[str] = []

        if event_type in ("io.fd_appeared", "io.fd_disappeared"):
            if "pid" in data:
                facts.append(f"PID: {data['pid']}")
            if "fd" in data:
                facts.append(f"FD: {data['fd']}")
            if "fd_type" in data:
                facts.append(f"TYPE: {data['fd_type']}")
            if "target" in data:
                facts.append(f"TARGET: {data['target']}")
            if "access_mode" in data:
                facts.append(f"ACCESS_MODE: {data['access_mode']}")

        elif event_type == "io.pipe_shared":
            if "pipe_inode" in data:
                facts.append(f"PIPE_INODE: {data['pipe_inode']}")
            if "endpoints" in data:
                for ep in data["endpoints"]:
                    facts.append(f"• PID {ep['pid']} ({ep.get('command', '')}) fd {ep['fd']} [{ep['access_mode']} - {ep.get('role', '')}]")

        if event_type == "process.created":
            if "pid" in data:
                facts.append(f"PID: {data['pid']}")
            if "ppid" in data:
                facts.append(f"PPID: {data['ppid']}")
            if "state" in data:
                facts.append(f"STATE: {data['state']}")
            if "command" in data:
                facts.append(f"CMD: {data['command']}")
            if data.get("cmdline") and data.get("cmdline") != data.get("command"):
                facts.append(f"ARGS: {data['cmdline']}")
            if data.get("tty"):
                facts.append(f"TTY: {data['tty']}")
            if data.get("cwd"):
                facts.append(f"CWD: {data['cwd']}")

        elif event_type == "process.removed":
            if "pid" in data:
                facts.append(f"PID: {data['pid']}")
            if "ppid" in data:
                facts.append(f"PPID: {data['ppid']}")
            if "command" in data:
                facts.append(f"CMD: {data['command']}")
            if "state" in data:
                facts.append(f"LAST_STATE: {data['state']}")

        elif event_type == "process.state_changed":
            if "pid" in data:
                facts.append(f"PID: {data['pid']}")
            if "command" in data:
                facts.append(f"CMD: {data['command']}")
            if "old_state" in data and "new_state" in data:
                facts.append(f"STATE: {data['old_state']} ➔ {data['new_state']}")

        elif event_type == "process.cwd_changed":
            if "pid" in data:
                facts.append(f"PID: {data['pid']}")
            if "command" in data:
                facts.append(f"CMD: {data['command']}")
            if "old_cwd" in data and "new_cwd" in data:
                facts.append(f"CWD: {data['old_cwd']} ➔ {data['new_cwd']}")

        elif event_type == "file.permissions_changed":
            if "path" in data:
                facts.append(f"PATH: {data['path']}")
            if "old_mode" in data and "new_mode" in data:
                facts.append(f"MODE: {data['old_mode']} ➔ {data['new_mode']}")

        elif event_type in ("file.created", "file.modified", "file.deleted", "directory.created", "directory.deleted"):
            if "path" in data:
                facts.append(f"PATH: {data['path']}")
            if "is_directory" in data:
                facts.append(f"IS_DIR: {data['is_directory']}")

        elif event_type == "file.moved":
            if "old_path" in data:
                facts.append(f"FROM: {data['old_path']}")
            if "new_path" in data:
                facts.append(f"TO: {data['new_path']}")

        elif event_type.startswith("shell."):
            if "pid" in data:
                facts.append(f"PID: {data['pid']}")
            if "command" in data:
                facts.append(f"CMD: {data['command']}")
            if "tty" in data:
                facts.append(f"TTY: {data['tty']}")
            if "cwd" in data:
                facts.append(f"CWD: {data['cwd']}")
            if "old_path" in data and "new_path" in data:
                facts.append(f"CWD: {data['old_path']} ➔ {data['new_path']}")

        elif event_type == "memory.swap_usage_changed":
            if "old_swap_used_kb" in data:
                facts.append(f"OLD_SWAP: {data['old_swap_used_kb']:,} kB")
            if "new_swap_used_kb" in data:
                facts.append(f"NEW_SWAP: {data['new_swap_used_kb']:,} kB")
            if "swap_total_kb" in data:
                facts.append(f"SWAP_TOTAL: {data['swap_total_kb']:,} kB")

        if not facts:
            # Fallback to key-values for other generic events
            return " | ".join(f"{k.upper()}: {v}" for k, v in data.items() if k not in ("observed_at", "process"))

        return " | ".join(facts)


class ActivityTimelineWidget(QWidget):
    """
    Live Activity Timeline Widget.
    Presents a real-time chronological stream of Linux activity observed by the Lab's observers.

    Features:
    - Domain-driven filtering (All, Filesystem, Process Subsystem, Shell & Terminal)
    - Live Search filtering across facts, event types, and sources
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
            "📁 Filesystem (file.*, directory.*)",
            "⚡ Process Subsystem (process.*)",
            "🐚 Shell & Terminal (shell.*)",
            "🧠 Memory Subsystem (memory.*)",
            "🗂️ File Descriptors & I/O (io.*)",
        ])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by PID, command, path, source, or facts...")
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
        Add a rich factual card for a newly observed Linux event.
        """
        card = EventCardWidget(event)

        item = QListWidgetItem()
        item.setSizeHint(card.sizeHint())

        # Insert at the very top of the visual list (newest first)
        self.list_widget.insertItem(0, item)
        self.list_widget.setItemWidget(item, card)

        self._all_events.insert(0, (item, card))

        # Maintain max capacity of visual items
        if len(self._all_events) > self.max_events:
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
            event = card.system_event
            event_type = event.event_type
            data_str = str(event.data).lower()
            type_str = event_type.lower()
            source_str = event.source.lower()
            mech_str = (event.mechanism or "").lower()

            # Domain check
            cat_match = True
            if filter_idx == 1:  # Filesystem (file.*, directory.*)
                cat_match = event_type.startswith("file.") or event_type.startswith("directory.")
            elif filter_idx == 2:  # Process (process.*)
                cat_match = event_type.startswith("process.")
            elif filter_idx == 3:  # Shell (shell.*)
                cat_match = event_type.startswith("shell.")
            elif filter_idx == 4:  # Memory (memory.*)
                cat_match = event_type.startswith("memory.")
            elif filter_idx == 5:  # File Descriptors & I/O (io.*)
                cat_match = event_type.startswith("io.")

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
                    term in data_str
                    or term in type_str
                    or term in target_text
                    or term in source_str
                    or term in mech_str
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
