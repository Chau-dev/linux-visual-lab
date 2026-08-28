from pathlib import Path

from PySide6.QtCore import QObject, Signal

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.core.events import SystemEvent


class FileSystemSignals(QObject):
    """
    Qt signals used by the existing GUI.

    We keep these because the current GUI already depends on them.
    """

    created = Signal(str, bool)
    deleted = Signal(str, bool)
    modified = Signal(str)
    moved = Signal(str, str)


class LinuxLabFileHandler(FileSystemEventHandler):
    """
    Receives real filesystem events from watchdog.

    Each event is sent in two directions:

    1. Existing Qt signal system
    2. New Event Bus
    """

    def __init__(
        self,
        signals,
        event_bus=None
    ):
        super().__init__()

        self.signals = signals
        self.event_bus = event_bus

    # --------------------------------------------------------
    # Created
    # --------------------------------------------------------

    def on_created(self, event):

        # Existing GUI system
        self.signals.created.emit(
            event.src_path,
            event.is_directory
        )

        # New Event Bus system
        if self.event_bus:

            event_type = (
                "directory.created"
                if event.is_directory
                else "file.created"
            )

            self.event_bus.publish(
                SystemEvent(
                    event_type=event_type,
                    data={
                        "path": event.src_path,
                        "is_directory": event.is_directory,
                    }
                )
            )

    # --------------------------------------------------------
    # Deleted
    # --------------------------------------------------------

    def on_deleted(self, event):

        # Existing GUI system
        self.signals.deleted.emit(
            event.src_path,
            event.is_directory
        )

        # New Event Bus system
        if self.event_bus:

            event_type = (
                "directory.deleted"
                if event.is_directory
                else "file.deleted"
            )

            self.event_bus.publish(
                SystemEvent(
                    event_type=event_type,
                    data={
                        "path": event.src_path,
                        "is_directory": event.is_directory,
                    }
                )
            )

    # --------------------------------------------------------
    # Modified
    # --------------------------------------------------------

    def on_modified(self, event):

        # Ignore directory modifications for now.
        if event.is_directory:
            return

        # Existing GUI system
        self.signals.modified.emit(
            event.src_path
        )

        # New Event Bus system
        if self.event_bus:

            self.event_bus.publish(
                SystemEvent(
                    event_type="file.modified",
                    data={
                        "path": event.src_path,
                    }
                )
            )

    # --------------------------------------------------------
    # Moved
    # --------------------------------------------------------

    def on_moved(self, event):

        # Existing GUI system
        self.signals.moved.emit(
            event.src_path,
            event.dest_path
        )

        # New Event Bus system
        if self.event_bus:

            self.event_bus.publish(
                SystemEvent(
                    event_type="file.moved",
                    data={
                        "old_path": event.src_path,
                        "new_path": event.dest_path,
                    }
                )
            )


class FileSystemMonitor:
    """
    Watches the LinuxLab directory recursively.
    """

    def __init__(
        self,
        path,
        event_bus=None
    ):

        self.path = Path(path)

        # Existing Qt signal system
        self.signals = FileSystemSignals()

        # New Event Bus
        self.event_bus = event_bus

        # watchdog observer
        self.observer = Observer()

        # Handler receives BOTH systems
        self.handler = LinuxLabFileHandler(
            self.signals,
            self.event_bus
        )

    # --------------------------------------------------------
    # Start monitoring
    # --------------------------------------------------------

    def start(self):

        self.observer.schedule(
            self.handler,
            str(self.path),
            recursive=True
        )

        self.observer.start()

    # --------------------------------------------------------
    # Stop monitoring
    # --------------------------------------------------------

    def stop(self):

        self.observer.stop()

        self.observer.join()
