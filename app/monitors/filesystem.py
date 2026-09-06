import os
import stat
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

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
    permissions_changed = Signal(str, str, str)
    event_detected = Signal(object)


class LinuxLabFileHandler(FileSystemEventHandler):
    """
    Receives real filesystem events from watchdog, performs POSIX stat diffing
    to detect content vs permission changes, and emits Qt signals.
    """

    def __init__(
        self,
        signals: FileSystemSignals,
        stat_cache: dict[str, tuple[int, int, int]],
    ):
        super().__init__()
        self.signals = signals
        self.stat_cache = stat_cache

    def on_created(self, event):
        path_str = event.src_path
        is_dir = event.is_directory

        try:
            st = os.lstat(path_str)
            self.stat_cache[path_str] = (st.st_mode, st.st_uid, st.st_gid)
        except OSError:
            pass

        self.signals.created.emit(path_str, is_dir)

        event_type = "directory.created" if is_dir else "file.created"
        system_event = SystemEvent(
            event_type=event_type,
            data={
                "path": path_str,
                "is_directory": is_dir,
            },
            source="Filesystem observer",
            mechanism="inotify",
        )
        self.signals.event_detected.emit(system_event)

    def on_deleted(self, event):
        path_str = event.src_path
        is_dir = event.is_directory

        self.stat_cache.pop(path_str, None)

        self.signals.deleted.emit(path_str, is_dir)

        event_type = "directory.deleted" if is_dir else "file.deleted"
        system_event = SystemEvent(
            event_type=event_type,
            data={
                "path": path_str,
                "is_directory": is_dir,
            },
            source="Filesystem observer",
            mechanism="inotify",
        )
        self.signals.event_detected.emit(system_event)

    def on_modified(self, event):
        path_str = event.src_path
        is_dir = event.is_directory

        try:
            st = os.lstat(path_str)
            current_stat = (st.st_mode, st.st_uid, st.st_gid)
        except OSError:
            current_stat = None

        prev_stat = self.stat_cache.get(path_str)

        if current_stat is not None:
            self.stat_cache[path_str] = current_stat

        # Check if permissions / mode changed
        if prev_stat is not None and current_stat is not None:
            prev_mode = prev_stat[0] & 0o7777
            curr_mode = current_stat[0] & 0o7777

            if prev_mode != curr_mode or prev_stat[1] != current_stat[1] or prev_stat[2] != current_stat[2]:
                old_oct = oct(prev_mode)[2:].zfill(4)
                new_oct = oct(curr_mode)[2:].zfill(4)

                self.signals.permissions_changed.emit(path_str, old_oct, new_oct)

                system_event = SystemEvent(
                    event_type="file.permissions_changed",
                    data={
                        "path": path_str,
                        "old_mode": old_oct,
                        "new_mode": new_oct,
                        "is_directory": is_dir,
                    },
                    source="Filesystem observer",
                    mechanism="stat()",
                )
                self.signals.event_detected.emit(system_event)
                return

        if is_dir:
            return

        self.signals.modified.emit(path_str)

        system_event = SystemEvent(
            event_type="file.modified",
            data={
                "path": path_str,
            },
            source="Filesystem observer",
            mechanism="inotify",
        )
        self.signals.event_detected.emit(system_event)

    def on_moved(self, event):
        old_path = event.src_path
        new_path = event.dest_path
        is_dir = event.is_directory

        self.stat_cache.pop(old_path, None)
        try:
            st = os.lstat(new_path)
            self.stat_cache[new_path] = (st.st_mode, st.st_uid, st.st_gid)
        except OSError:
            pass

        self.signals.moved.emit(old_path, new_path)

        system_event = SystemEvent(
            event_type="file.moved",
            data={
                "old_path": old_path,
                "new_path": new_path,
                "is_directory": is_dir,
            },
            source="Filesystem observer",
            mechanism="inotify",
        )
        self.signals.event_detected.emit(system_event)


class FileSystemMonitor:
    """
    Watches a target directory recursively using watchdog and POSIX stat diffing.
    Translates OS filesystem changes into standardized SystemEvent instances.
    """

    def __init__(self, path: str | Path, event_bus=None):
        self.path = Path(path)
        self.signals = FileSystemSignals()
        self.event_bus = event_bus
        self.stat_cache: dict[str, tuple[int, int, int]] = {}

        if self.event_bus is not None:
            self.signals.event_detected.connect(self._publish_to_event_bus)

        self.handler = LinuxLabFileHandler(self.signals, self.stat_cache)
        self.observer = Observer()

    def _publish_to_event_bus(self, event: SystemEvent):
        """Bridge Qt signal to EventBus."""
        if self.event_bus:
            self.event_bus.publish(event)

    def _scan_initial_stats(self):
        """Populate initial stat cache for accurate permission diffing."""
        self.stat_cache.clear()
        if not self.path.exists():
            return

        try:
            for root, dirs, files in os.walk(self.path):
                for name in dirs + files:
                    full_path = os.path.join(root, name)
                    try:
                        st = os.lstat(full_path)
                        self.stat_cache[full_path] = (st.st_mode, st.st_uid, st.st_gid)
                    except OSError:
                        pass
        except OSError:
            pass

    def start(self) -> bool:
        """Start recursive filesystem monitoring."""
        if not self.path.exists():
            try:
                self.path.mkdir(parents=True, exist_ok=True)
            except OSError:
                return False

        self._scan_initial_stats()

        if not hasattr(self, "observer") or self.observer is None:
            self.observer = Observer()

        try:
            self.observer.schedule(
                self.handler,
                str(self.path),
                recursive=True,
            )
            self.observer.start()
            return True
        except Exception:
            return False

    def stop(self):
        """Stop filesystem monitoring."""
        if hasattr(self, "observer") and self.observer is not None:
            try:
                if self.observer.is_alive():
                    self.observer.stop()
                    self.observer.join(timeout=2.0)
            except Exception:
                pass

    def set_path(self, new_path: str | Path) -> bool:
        """Switch to watching a different directory."""
        self.stop()
        self.path = Path(new_path)
        self.observer = Observer()
        return self.start()
