import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.models.filesystem_object import FilesystemObject
from app.visualizers.permission_simulator import PermissionSimulatorWidget


class TestPermissionSimulatorWidget(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_widget_render_and_clear_context(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Mode 0755 (rwxr-xr-x)
            os.chmod(tmp_path, 0o755)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)

            widget = PermissionSimulatorWidget()
            widget.set_context(obj)

            # Check File and Mode Headers
            self.assertIn(tmp_path.name, widget.file_name_label.text())
            self.assertIn("0755", widget.octal_label.text())
            self.assertIn("-rwxr-xr-x", widget.symbolic_label.text())

            # Check Special Mode Badges
            self.assertEqual(widget.suid_badge["status"].text(), "OFF (Normal)")
            self.assertEqual(widget.sgid_badge["status"].text(), "OFF (Normal)")
            self.assertEqual(widget.sticky_badge["status"].text(), "OFF (Normal)")

            # Check 3x3 Matrix Cells
            # Owner: r (✓), w (✓), x (✓)
            self.assertEqual(widget.matrix_cells[("owner", 1)].text(), "✓")
            self.assertEqual(widget.matrix_cells[("owner", 2)].text(), "✓")
            self.assertEqual(widget.matrix_cells[("owner", 3)].text(), "✓")

            # Group: r (✓), w (✗), x (✓)
            self.assertEqual(widget.matrix_cells[("group", 1)].text(), "✓")
            self.assertEqual(widget.matrix_cells[("group", 2)].text(), "✗")
            self.assertEqual(widget.matrix_cells[("group", 3)].text(), "✓")

            # Other: r (✓), w (✗), x (✓)
            self.assertEqual(widget.matrix_cells[("other", 1)].text(), "✓")
            self.assertEqual(widget.matrix_cells[("other", 2)].text(), "✗")
            self.assertEqual(widget.matrix_cells[("other", 3)].text(), "✓")

            # Test Clearing Context
            widget.clear_context()
            self.assertEqual(widget.file_name_label.text(), "No file selected")
            self.assertEqual(widget.matrix_cells[("owner", 1)].text(), "—")

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_special_bits_rendering(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Mode 4755 (SUID)
            os.chmod(tmp_path, 0o4755)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)

            widget = PermissionSimulatorWidget()
            widget.set_context(obj)

            self.assertIn("ON", widget.suid_badge["status"].text())
            self.assertIn("OFF", widget.sgid_badge["status"].text())
            self.assertIn("4755", widget.octal_label.text())
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
