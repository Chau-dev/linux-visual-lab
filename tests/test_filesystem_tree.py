import sys
import unittest
import tempfile
import shutil
from pathlib import Path

from PySide6.QtWidgets import QApplication
from app.visualizers.filesystem_view import FilesystemTreeWidget


class TestFilesystemTreeExpansion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_fs_tree_"))
        (self.temp_dir / "file1.txt").write_text("content 1")
        (self.temp_dir / "file2.txt").write_text("content 2")
        
        self.subfolder = self.temp_dir / "subfolder1"
        self.subfolder.mkdir()
        (self.subfolder / "subfile.txt").write_text("sub content")
        
        self.sub_subfolder = self.subfolder / "sub_subfolder"
        self.sub_subfolder.mkdir()
        (self.sub_subfolder / "deep.txt").write_text("deep content")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tree_expansion_respects_ls_scoping(self):
        """
        Verify that building tree or highlighting CWD only expands the immediate directory,
        leaving nested subdirectories collapsed (matching Linux non-recursive ls behavior).
        """
        tree = FilesystemTreeWidget()
        tree.build_tree(self.temp_dir)

        root_item = tree.topLevelItem(0)
        self.assertIsNotNone(root_item)
        self.assertTrue(root_item.isExpanded(), "Root directory should be expanded to list its immediate entries")

        # Find subfolder item
        subfolder_item = None
        for i in range(root_item.childCount()):
            child = root_item.child(i)
            if child.data(0, 0x0100) == str(self.subfolder):  # Qt.ItemDataRole.UserRole == 0x0100 (256)
                subfolder_item = child
                break

        self.assertIsNotNone(subfolder_item, "subfolder1 should be present under root")
        self.assertFalse(subfolder_item.isExpanded(), "Immediate subfolder should NOT be auto-expanded (ls scoping)")

        # Find sub_subfolder item under subfolder
        sub_sub_item = None
        for i in range(subfolder_item.childCount()):
            child = subfolder_item.child(i)
            if child.data(0, 0x0100) == str(self.sub_subfolder):
                sub_sub_item = child
                break

        self.assertIsNotNone(sub_sub_item, "sub_subfolder should be in the tree hierarchy")
        self.assertFalse(sub_sub_item.isExpanded(), "Sub-subfolder must NOT be expanded")

        # Now simulate user navigating into subfolder1 (e.g. cd subfolder1)
        tree.highlight_current_directory(self.subfolder)

        self.assertTrue(subfolder_item.isExpanded(), "Active CWD subfolder must now be expanded to show its entries")
        self.assertIn("👈", subfolder_item.text(0))
        self.assertFalse(sub_sub_item.isExpanded(), "Sub-subfolder inside active CWD must remain collapsed (non-recursive ls)")

    def test_selection_not_stolen_by_highlight(self):
        """
        Verify that clicking/selecting another file or folder in the tree
        is preserved when CWD updates/polls occur, and is not stolen back.
        """
        tree = FilesystemTreeWidget()
        tree.build_tree(self.temp_dir)

        # CWD is initially root
        tree.highlight_current_directory(self.temp_dir)

        # User selects file1.txt
        file1_path = self.temp_dir / "file1.txt"
        selected = tree.select_path(file1_path)
        self.assertTrue(selected, "Should successfully select file1.txt")
        self.assertEqual(tree.currentItem().data(0, 0x0100), str(file1_path))

        # Periodic CWD update occurs for the same or different directory
        tree.highlight_current_directory(self.temp_dir)

        # Selection must still be file1.txt!
        self.assertEqual(
            tree.currentItem().data(0, 0x0100),
            str(file1_path),
            "User's selected item must NOT be stolen by CWD background highlights",
        )

    def test_delegate_strips_duplicate_emoji(self):
        """
        Verify that FilesystemTreeDelegate removes the static '👈' from
        Qt's base text renderer so only the animated, larger emoji is drawn.
        """
        from PySide6.QtWidgets import QStyleOptionViewItem

        tree = FilesystemTreeWidget()
        tree.build_tree(self.temp_dir)
        tree.highlight_current_directory(self.temp_dir)

        root_index = tree.model().index(0, 0)
        opt = QStyleOptionViewItem()
        tree.tree_delegate.initStyleOption(opt, root_index)

        self.assertNotIn("👈", opt.text, "Delegate initStyleOption must strip static 👈 from base rendering")


if __name__ == "__main__":
    unittest.main()
