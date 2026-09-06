import sys
import unittest
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.process.model import Process


class TestProcessIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_main_window_process_flow(self):
        """Verify MainWindow process monitor, tab switching, and process update handling."""
        window = MainWindow(process_interval_ms=100)

        # Tab check
        self.assertEqual(window.center_tabs.count(), 5)
        self.assertEqual(window.center_tabs.tabText(0), "🔬 POSIX Filesystem Lab")
        self.assertEqual(window.center_tabs.tabText(1), "⚡ Linux Process Lab")
        self.assertEqual(window.center_tabs.tabText(2), "🗂️ Linux File Descriptors & I/O Lab")
        self.assertEqual(window.center_tabs.tabText(3), "🧠 Linux Memory Lab")
        self.assertEqual(window.center_tabs.tabText(4), "🔥 Linux CPU Lab")

        # Simulate process snapshot update
        p1 = Process(
            pid=1234,
            ppid=1,
            pgid=1234,
            sid=1234,
            tpgid=1234,
            uid=1000,
            gid=1000,
            tty="/dev/pts/0",
            state="S",
            command="custom_app",
            cmdline="custom_app --daemon",
            cwd=Path("/home/dev"),
        )
        snapshot = {1234: p1}
        window.handle_processes_updated(snapshot)

        # Check that tree widget got updated
        self.assertEqual(window.process_lab.tree_widget.topLevelItemCount(), 1)
        root_item = window.process_lab.tree_widget.topLevelItem(0)
        self.assertEqual(root_item.data(1, 0x0100), 1234)

        # Cleanup
        window.session_thread.stop()
        window.process_monitor.stop()
        window.memory_monitor.stop()
        window.cpu_monitor.stop()
        window.io_monitor.stop()
        window.fs_monitor.stop()
        window.close()


if __name__ == "__main__":
    unittest.main()
