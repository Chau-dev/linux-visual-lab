from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from app.core.event_bus import EventBus
from app.core.activity import ActivityTimeline
from app.core.events import SystemEvent
from app.io.monitor import IoMonitor
from app.visualizers.activity_timeline import ActivityTimelineWidget
from app.visualizers.io_view import IoLabWidget


class TestIoIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_io_integration_")
        self.proc_root = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_io_event_flow(self):
        pid = 5555
        fd_dir = self.proc_root / str(pid) / "fd"
        fdinfo_dir = self.proc_root / str(pid) / "fdinfo"
        fd_dir.mkdir(parents=True)
        fdinfo_dir.mkdir(parents=True)

        os.symlink("/dev/pts/1", fd_dir / "0")
        (fdinfo_dir / "0").write_text("pos:\t0\nflags:\t02\n")

        event_bus = EventBus()
        activity = ActivityTimeline(max_events=50)
        timeline_widget = ActivityTimelineWidget()
        io_lab = IoLabWidget()

        received_events = []

        def on_event(ev: SystemEvent):
            received_events.append(ev)
            activity.record(ev)
            timeline_widget.add_event(ev)

        event_bus.subscribe("io.fd_appeared", on_event)
        event_bus.subscribe("io.fd_disappeared", on_event)
        event_bus.subscribe("io.pipe_shared", on_event)

        monitor = IoMonitor(target_pid=pid, interval_ms=50, proc_root=self.proc_root)
        monitor.event_detected.connect(event_bus.publish)
        monitor.io_updated.connect(io_lab.update_io_state)

        # Single poll to discover fd 0
        monitor.poll_once()

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].event_type, "io.fd_appeared")
        self.assertEqual(received_events[0].data["fd"], 0)
        self.assertEqual(timeline_widget.event_count(), 1)
        self.assertEqual(io_lab.fd_table.rowCount(), 1)

    def test_main_window_process_io_sync(self):
        from app.ui.main_window import MainWindow
        from app.process.model import Process

        win = MainWindow(lab_path=Path(self.temp_dir))
        
        # Mock processes in registry
        p1 = Process(pid=1000, ppid=1, pgid=1000, sid=1000, tpgid=1000, uid=1000, gid=1000, tty="/dev/pts/1", tty_nr=34817, command="bash")
        p2 = Process(pid=2000, ppid=1, pgid=2000, sid=2000, tpgid=0, uid=1000, gid=1000, tty=None, tty_nr=0, command="sleep")
        procs = {1000: p1, 2000: p2}

        # Authoritative snapshot update
        win.handle_processes_updated(procs)

        # 1. Process Lab selects PID 2000 -> IO Lab follows PID 2000
        win.handle_process_selected(p2)
        self.assertEqual(win.io_lab.current_pid, 2000)

        # 2. IO Lab chooses/pins PID 1000 -> Process Lab synchronizes selection
        win.handle_io_process_chosen(1000)
        self.assertEqual(win.process_lab.tree_widget._selected_pid, 1000)
        self.assertEqual(win.io_lab.current_pid, 1000)

        # 3. Switching back to follow mode
        win.handle_io_follow_mode_requested()
        self.assertFalse(win.io_lab.is_pinned)

        win.close()


if __name__ == "__main__":
    unittest.main()
