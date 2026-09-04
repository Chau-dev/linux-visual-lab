import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent

from app.core.event_bus import EventBus
from app.core.events import SystemEvent
from app.monitors.filesystem import FileSystemMonitor, LinuxLabFileHandler, FileSystemSignals


class TestFileSystemMonitor(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lab_path = Path(self.temp_dir.name)
        self.event_bus = EventBus()
        self.received_events = []

        for evt in ["file.created", "file.modified", "file.deleted", "file.moved", "file.permissions_changed", "directory.created", "directory.deleted"]:
            self.event_bus.subscribe(evt, lambda e: self.received_events.append(e))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_file_handler_created_and_deleted(self):
        signals = FileSystemSignals()
        stat_cache = {}
        handler = LinuxLabFileHandler(signals, stat_cache)

        emitted_events = []
        signals.event_detected.connect(lambda e: emitted_events.append(e))

        test_file = self.lab_path / "hello.txt"
        test_file.write_text("hello")

        # on_created
        handler.on_created(FileCreatedEvent(str(test_file)))
        self.assertEqual(len(emitted_events), 1)
        self.assertEqual(emitted_events[0].event_type, "file.created")
        self.assertEqual(emitted_events[0].data["path"], str(test_file))

        # on_deleted
        handler.on_deleted(FileDeletedEvent(str(test_file)))
        self.assertEqual(len(emitted_events), 2)
        self.assertEqual(emitted_events[1].event_type, "file.deleted")

    def test_permission_diffing(self):
        signals = FileSystemSignals()
        stat_cache = {}
        handler = LinuxLabFileHandler(signals, stat_cache)

        emitted_events = []
        signals.event_detected.connect(lambda e: emitted_events.append(e))

        test_file = self.lab_path / "script.sh"
        test_file.write_text("#!/bin/sh")

        # Seed initial stat cache
        st = os.lstat(test_file)
        stat_cache[str(test_file)] = (st.st_mode, st.st_uid, st.st_gid)

        # Normal modify without mode change
        handler.on_modified(FileModifiedEvent(str(test_file)))
        self.assertEqual(len(emitted_events), 1)
        self.assertEqual(emitted_events[0].event_type, "file.modified")

        # Change permission mode
        os.chmod(test_file, 0o755)
        handler.on_modified(FileModifiedEvent(str(test_file)))
        self.assertEqual(len(emitted_events), 2)
        self.assertEqual(emitted_events[1].event_type, "file.permissions_changed")
        self.assertEqual(emitted_events[1].data["new_mode"], "0755")

    def test_file_moved(self):
        signals = FileSystemSignals()
        stat_cache = {}
        handler = LinuxLabFileHandler(signals, stat_cache)

        emitted_events = []
        signals.event_detected.connect(lambda e: emitted_events.append(e))

        old_p = str(self.lab_path / "old.txt")
        new_p = str(self.lab_path / "new.txt")

        handler.on_moved(FileMovedEvent(old_p, new_p))
        self.assertEqual(len(emitted_events), 1)
        self.assertEqual(emitted_events[0].event_type, "file.moved")
        self.assertEqual(emitted_events[0].data["old_path"], old_p)
        self.assertEqual(emitted_events[0].data["new_path"], new_p)

    def test_monitor_lifecycle(self):
        monitor = FileSystemMonitor(self.lab_path, self.event_bus)
        started = monitor.start()
        self.assertTrue(started)
        monitor.stop()


if __name__ == "__main__":
    unittest.main()
