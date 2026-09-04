import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.events import SystemEvent
from app.process.session import TerminalSession
from app.ui.main_window import MainWindow


class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.lab_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_pipeline_initialization_and_shutdown(self):
        # Create test subdirectories and files
        subdir = self.lab_path / "project"
        subdir.mkdir(parents=True, exist_ok=True)
        test_file = subdir / "main.py"
        test_file.write_text("print('hello')")

        # 1. Initialize MainWindow
        window = MainWindow(lab_path=self.lab_path)
        self.assertEqual(window.lab_path, self.lab_path)

        # 2. Verify visualizers initialized
        self.assertIsNotNone(window.context_panel)
        self.assertIsNotNone(window.session_widget)
        self.assertIsNotNone(window.tree_widget)
        self.assertIsNotNone(window.inspector_widget)
        self.assertIsNotNone(window.timeline_widget)

        # 3. Simulate session discovery snapshot
        mock_sessions = {
            1001: TerminalSession(
                pid=1001,
                ppid=1000,
                command="bash",
                tty="/dev/pts/1",
                cwd=subdir,
            )
        }
        window.handle_sessions_updated(mock_sessions)

        # Verify focused session and top banner
        self.assertEqual(window.focused_session.pid, 1001)
        self.assertIn("project", window.context_panel.location_label.text())

        # 4. Simulate tree selection -> Inspector
        window.handle_tree_selection(test_file)
        self.assertEqual(window.selected_path, test_file)
        self.assertEqual(window.inspector_widget.lbl_path.text(), str(test_file))
        self.assertIn("06", window.inspector_widget.mode_banner.text())

        # 5. Simulate system event delivery
        event = SystemEvent(
            event_type="file.created",
            data={"path": str(test_file), "is_directory": False},
        )
        window.event_bus.publish(event)
        self.assertGreaterEqual(window.activity_timeline.get_events().__len__(), 1)

        # 6. Clean close
        window.session_thread.stop()
        window.fs_monitor.stop()
        window.close()


if __name__ == "__main__":
    unittest.main()
