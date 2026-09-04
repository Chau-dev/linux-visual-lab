import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.event_bus import EventBus
from app.core.events import SystemEvent
from app.monitors.filesystem import FileSystemMonitor
from app.ui.main_window import MainWindow, get_default_lab_path


class TestRobustness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_event_bus_error_isolation(self):
        """Ensure a faulty subscriber does not prevent other subscribers from receiving events."""
        bus = EventBus()
        delivered = []

        def failing_subscriber(event):
            raise RuntimeError("Intentional subscriber failure")

        def working_subscriber(event):
            delivered.append(event.event_type)

        bus.subscribe("test.event", failing_subscriber)
        bus.subscribe("test.event", working_subscriber)

        # Should not raise exception and working subscriber must be called
        bus.publish(SystemEvent(event_type="test.event"))
        self.assertEqual(delivered, ["test.event"])

    def test_event_bus_unsubscribe(self):
        """Test unsubscribing from event bus."""
        bus = EventBus()
        calls = []

        def handler(event):
            calls.append(1)

        bus.subscribe("test.event", handler)
        bus.publish(SystemEvent(event_type="test.event"))
        self.assertEqual(len(calls), 1)

        bus.unsubscribe("test.event", handler)
        bus.publish(SystemEvent(event_type="test.event"))
        self.assertEqual(len(calls), 1)

    def test_default_lab_path_fallback(self):
        """Test that get_default_lab_path always returns a valid, existing Path."""
        path = get_default_lab_path()
        self.assertIsInstance(path, Path)
        self.assertTrue(path.exists())

    def test_filesystem_monitor_set_path(self):
        """Test dynamic path switching on FileSystemMonitor."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            monitor = FileSystemMonitor(tmpdir1)
            started = monitor.start()
            self.assertTrue(started)
            self.assertEqual(monitor.path, Path(tmpdir1))

            switched = monitor.set_path(tmpdir2)
            self.assertTrue(switched)
            self.assertEqual(monitor.path, Path(tmpdir2))

            monitor.stop()

    def test_broken_symlink_details(self):
        """Test that MainWindow handles broken symlinks without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            broken_symlink = Path(tmpdir) / "broken_link"
            nonexistent_target = Path(tmpdir) / "does_not_exist.txt"

            try:
                os.symlink(nonexistent_target, broken_symlink)
            except OSError:
                return  # Skip if symlink creation is not permitted

            window = MainWindow(lab_path=Path(tmpdir))
            window.handle_tree_selection(broken_symlink)
            self.assertIn("Broken symlink", window.inspector_widget.type_badge.text())
            window.session_thread.stop()
            window.fs_monitor.stop()
            window.close()

    def test_concurrent_event_bus_pub_sub(self):
        """Test EventBus under concurrent multi-threaded publish and subscribe loads."""
        import threading
        from app.core.activity import ActivityTimeline

        bus = EventBus()
        timeline = ActivityTimeline(max_events=500)
        received_count = [0]
        count_lock = threading.Lock()

        def counter_handler(event):
            with count_lock:
                received_count[0] += 1
            timeline.record(event)

        bus.subscribe("threaded.event", counter_handler)

        def worker_task(thread_id):
            for i in range(50):
                bus.publish(SystemEvent(event_type="threaded.event", data={"thread": thread_id, "i": i}))

        threads = [threading.Thread(target=worker_task, args=(tid,)) for tid in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(received_count[0], 500)
        self.assertEqual(len(timeline.get_events()), 500)


if __name__ == "__main__":
    unittest.main()
