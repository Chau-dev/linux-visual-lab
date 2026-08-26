from pathlib import Path

from PySide6.QtCore import QObject, Signal

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FileSystemSignals(QObject):
    created = Signal(str, bool)
    deleted = Signal(str, bool)
    modified = Signal(str)
    moved = Signal(str, str)


class LinuxLabFileHandler(FileSystemEventHandler):

    def __init__(self, signals):
        super().__init__()
        self.signals = signals

    def on_created(self, event):
        self.signals.created.emit(
            event.src_path,
            event.is_directory
        )

    def on_deleted(self, event):
        self.signals.deleted.emit(
            event.src_path,
            event.is_directory
        )

    def on_modified(self, event):
        if not event.is_directory:
            self.signals.modified.emit(event.src_path)

    def on_moved(self, event):
        self.signals.moved.emit(
            event.src_path,
            event.dest_path
        )


class FileSystemMonitor:

    def __init__(self, path):
        self.path = Path(path)

        self.signals = FileSystemSignals()

        self.observer = Observer()

        self.handler = LinuxLabFileHandler(
            self.signals
        )

    def start(self):
        self.observer.schedule(
            self.handler,
            str(self.path),
            recursive=True
        )

        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
