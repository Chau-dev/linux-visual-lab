import os
import stat
import tempfile
import unittest
from pathlib import Path

from app.core.models import FilesystemObject, AccessEvaluationResult


class TestFilesystemObject(unittest.TestCase):

    def test_from_path_regular_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"Hello Linux Visual Lab")
            tmp_path = Path(tmp.name)

        try:
            # Set known permissions 0o644 (rw-r--r--)
            os.chmod(tmp_path, 0o644)

            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)
            self.assertEqual(obj.name, tmp_path.name)
            self.assertEqual(obj.file_type, "Regular file")
            self.assertTrue(obj.is_file)
            self.assertFalse(obj.is_dir)
            self.assertFalse(obj.is_symlink)
            self.assertEqual(obj.octal_mode, "0644")
            self.assertEqual(obj.size_bytes, 22)
            self.assertFalse(obj.suid)
            self.assertFalse(obj.sgid)
            self.assertFalse(obj.sticky)

            # Check permission flags
            self.assertTrue(obj.owner_r)
            self.assertTrue(obj.owner_w)
            self.assertFalse(obj.owner_x)

            self.assertTrue(obj.group_r)
            self.assertFalse(obj.group_w)
            self.assertFalse(obj.group_x)

            self.assertTrue(obj.other_r)
            self.assertFalse(obj.other_w)
            self.assertFalse(obj.other_x)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_special_mode_bits(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Set SUID (4755)
            os.chmod(tmp_path, 0o4755)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)
            self.assertTrue(obj.suid)
            self.assertFalse(obj.sgid)
            self.assertFalse(obj.sticky)
            self.assertEqual(obj.octal_mode, "4755")

            # Set SGID (2755)
            os.chmod(tmp_path, 0o2755)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)
            self.assertFalse(obj.suid)
            self.assertTrue(obj.sgid)
            self.assertFalse(obj.sticky)
            self.assertEqual(obj.octal_mode, "2755")

            # Set Sticky (1777)
            os.chmod(tmp_path, 0o1777)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)
            self.assertFalse(obj.suid)
            self.assertFalse(obj.sgid)
            self.assertTrue(obj.sticky)
            self.assertEqual(obj.octal_mode, "1777")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_directory_inspection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dir_path = Path(tmp_dir)
            obj = FilesystemObject.from_path(dir_path)
            self.assertIsNotNone(obj)
            self.assertTrue(obj.is_dir)
            self.assertFalse(obj.is_file)
            self.assertEqual(obj.file_type, "Directory")

    def test_symlink_inspection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "target.txt"
            target.write_text("content")

            link = Path(tmp_dir) / "link.txt"
            os.symlink(target, link)

            obj = FilesystemObject.from_path(link)
            self.assertIsNotNone(obj)
            self.assertTrue(obj.is_symlink)
            self.assertFalse(obj.is_broken_symlink)
            self.assertEqual(obj.symlink_target, str(target))

    def test_evaluate_access_dac_rules(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Mode 0640: Owner rw-, Group r--, Other ---
            os.chmod(tmp_path, 0o640)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)

            # Step 1: Owner match
            owner_res = obj.evaluate_access(subject_uid=obj.uid, subject_gid=9999)
            self.assertEqual(owner_res.matched_class, "owner")
            self.assertEqual(owner_res.step_number, 1)
            self.assertTrue(owner_res.can_read)
            self.assertTrue(owner_res.can_write)
            self.assertFalse(owner_res.can_execute)

            # Step 2: Group match
            diff_uid = obj.uid + 100
            group_res = obj.evaluate_access(subject_uid=diff_uid, subject_gid=obj.gid)
            self.assertEqual(group_res.matched_class, "group")
            self.assertEqual(group_res.step_number, 2)
            self.assertTrue(group_res.can_read)
            self.assertFalse(group_res.can_write)
            self.assertFalse(group_res.can_execute)

            # Step 3: Other fallback
            other_res = obj.evaluate_access(subject_uid=diff_uid, subject_gid=obj.gid + 100)
            self.assertEqual(other_res.matched_class, "other")
            self.assertEqual(other_res.step_number, 3)
            self.assertFalse(other_res.can_read)
            self.assertFalse(other_res.can_write)
            self.assertFalse(other_res.can_execute)

            # Root bypass check (UID 0)
            root_res = obj.evaluate_access(subject_uid=0, subject_gid=0)
            self.assertTrue(root_res.can_read)
            self.assertTrue(root_res.can_write)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
