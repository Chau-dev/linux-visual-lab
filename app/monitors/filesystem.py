from pathlib import Path

from PySide6.QtCore import QObject, Signal

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.core.events import SystemEvent


class FileSystemSignals(QObject):
    """
    Qt signals used by the GUI.

    All signals cross thread boundaries safely into the GUI thread.
    """

    created = Signal(str, bool)
    deleted = Signal(str, bool)
    modified = Signal(str)
    moved = Signal(str, str)
    event_detected = Signal(object)


class LinuxLabFileHandler(FileSystemEventHandler):
    """
    Receives real filesystem events from watchdog.

    Emits Qt signals which are delivered safely onto the GUI thread.
    """

    def __init__(
        self,
        signals: FileSystemSignals,
    ):
        super().__init__()

        self.signals = signals

    # --------------------------------------------------------
    # Created
    # --------------------------------------------------------

    def on_created(self, event):

        self.signals.created.emit(
            event.src_path,
            event.is_directory
        )

        event_type = (
            "directory.created"
            if event.is_directory
            else "file.created"
        )

        system_event = SystemEvent(
            event_type=event_type,
            data={
                "path": event.src_path,
                "is_directory": event.is_directory,
            }
        )

        self.signals.event_detected.emit(
            system_event
        )

    # --------------------------------------------------------
    # Deleted
    # --------------------------------------------------------

    def on_deleted(self, event):

        self.signals.deleted.emit(
            event.src_path,
            event.is_directory
        )

        event_type = (
            "directory.deleted"
            if event.is_directory
            else "file.deleted"
        )

        system_event = SystemEvent(
            event_type=event_type,
            data={
                "path": event.src_path,
                "is_directory": event.is_directory,
            }
        )

        self.signals.event_detected.emit(
            system_event
        )

    # --------------------------------------------------------
    # Modified
    # --------------------------------------------------------

    def on_modified(self, event):

        if event.is_directory:
            return

        self.signals.modified.emit(
            event.src_path
        )

        system_event = SystemEvent(
            event_type="file.modified",
            data={
                "path": event.src_path,
            }
        )

        self.signals.event_detected.emit(
            system_event
        )

    # --------------------------------------------------------
    # Moved
    # --------------------------------------------------------

    def on_moved(self, event):

        self.signals.moved.emit(
            event.src_path,
            event.dest_path
        )

        system_event = SystemEvent(
            event_type="file.moved",
            data={
                "old_path": event.src_path,
                "new_path": event.dest_path,
            }
        )

        self.signals.event_detected.emit(
            system_event
        )


class FileSystemMonitor:
    """
    Watches a target directory recursively.
    """

    def __init__(
        self,
        path,
        event_bus=None
    ):

        self.path = Path(path)

        # Qt signals system
        self.signals = FileSystemSignals()

        # Event Bus
        self.event_bus = event_bus

        if self.event_bus is not None:
            self.signals.event_detected.connect(
                self._publish_to_event_bus
            )

        # Watchdog handler
        self.handler = LinuxLabFileHandler(
            self.signals,
        )

        # Watchdog observer
        self.observer = Observer()

    def _publish_to_event_bus(self, event: SystemEvent):
        """Bridge Qt signal to EventBus."""
        if self.event_bus:
            self.event_bus.publish(event)


    # --------------------------------------------------------
    # Start monitoring
    # --------------------------------------------------------

    def start(self):

        if not self.path.exists():

            try:
                self.path.mkdir(
                    parents=True,
                    exist_ok=True
                )
            except OSError:
                return False

        if not hasattr(self, "observer") or self.observer is None:
            self.observer = Observer()

        try:
            self.observer.schedule(
                self.handler,
                str(self.path),
                recursive=True
            )

            self.observer.start()

            return True

        except Exception:

            return False

    # --------------------------------------------------------
    # Stop monitoring
    # --------------------------------------------------------

    def stop(self):

        if hasattr(self, "observer") and self.observer is not None:

            try:
                if self.observer.is_alive():
                    self.observer.stop()
                    self.observer.join(timeout=2.0)
            except Exception:
                pass

    # --------------------------------------------------------
    # Change watched path dynamically
    # --------------------------------------------------------

    def set_path(self, new_path) -> bool:
        """
        Switch to watching a different directory.
        """
        self.stop()
        self.path = Path(new_path)
        self.observer = Observer()
        return self.start()


