from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from app.core.events import SystemEvent


class ActivityTimelineWidget(QListWidget):
    """
    Visual representation of recent Linux events.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self.setSpacing(4)

        self.setMinimumWidth(500)
        self.setMaximumWidth(700)

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

    def add_event(self, event: SystemEvent):
        """
        Add one Linux event to the visual timeline.
        """

        timestamp = event.timestamp.strftime(
            "%H:%M:%S"
        )

        title, details = self.format_event(
            event
        )

        text = (
            f"{timestamp}  {title}\n"
            f"{details}"
        )

        item = QListWidgetItem(text)

        item.setTextAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        item.setToolTip(text)

        # Give multiline events more vertical space.
        if "\n" in details:
            item.setSizeHint(
                QSize(0, 72)
            )
        else:
            item.setSizeHint(
                QSize(0, 48)
            )

        # Newest event goes to the top.
        self.insertItem(
            0,
            item
        )

        self.scrollToTop()

    def format_event(self, event: SystemEvent):
        """
        Convert an internal SystemEvent into
        human-readable text.
        """

        event_type = event.event_type
        data = event.data

        if event_type == "file.created":
            return (
                "📄 FILE CREATED",
                data.get("path", "")
            )

        if event_type == "directory.created":
            return (
                "📁 DIRECTORY CREATED",
                data.get("path", "")
            )

        if event_type == "file.modified":
            return (
                "✏️ FILE MODIFIED",
                data.get("path", "")
            )

        if event_type == "file.deleted":
            return (
                "🗑 FILE DELETED",
                data.get("path", "")
            )

        if event_type == "directory.deleted":
            return (
                "🗑 DIRECTORY DELETED",
                data.get("path", "")
            )

        if event_type == "file.moved":

            old_path = data.get(
                "old_path",
                ""
            )

            new_path = data.get(
                "new_path",
                ""
            )

            return (
                "↔️ FILE MOVED",
                f"{old_path}\n"
                f"        ↓\n"
                f"{new_path}"
            )

        return (
            event_type,
            str(data)
        )

    def clear_events(self):
        """
        Remove all events from the timeline.
        """

        self.clear()
