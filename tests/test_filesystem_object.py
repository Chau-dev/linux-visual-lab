import os
import stat
import tempfile
import unittest
from pathlib import Path

from app.models.filesystem_object import FilesystemObject, AccessSimulationResult


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
            self.assertIn("s", obj.symbolic_mode)

            # Set SGID (2755)
            os.chmod(tmp_path, 0o2755)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)
            self.assertFalse(obj.suid)
            self.assertTrue(obj.sgid)
            self.assertFalse(obj.sticky)
            self.assertEqual(obj.octal_mode, "2755")

            # Set Sticky bit (1777)
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

    def test_kernel_3_step_access_simulation(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Mode 0750 (rwxr-x---)
            # Owner: rwx (7)
            # Group: r-x (5)
            # Other: --- (0)
            os.chmod(tmp_path, 0o750)
            obj = FilesystemObject.from_path(tmp_path)
            self.assertIsNotNone(obj)

            file_uid = obj.uid
            file_gid = obj.gid

            # ----------------------------------------------------
            # Test Step 1: Owner match
            # ----------------------------------------------------
            res_owner = obj.simulate_kernel_access(
                subject_uid=file_uid,
                subject_gid=9999,
                subject_supplementary_gids=[],
            )
            self.assertEqual(res_owner.matched_class, "owner")
            self.assertEqual(res_owner.step_number, 1)
            self.assertTrue(res_owner.can_read)
            self.assertTrue(res_owner.can_write)
            self.assertTrue(res_owner.can_execute)

            # ----------------------------------------------------
            # Test Step 2: Group match (via primary GID)
            # ----------------------------------------------------
            res_group = obj.simulate_kernel_access(
                subject_uid=9999,  # Different UID
                subject_gid=file_gid,  # Matching primary GID
                subject_supplementary_gids=[],
            )
            self.assertEqual(res_group.matched_class, "group")
            self.assertEqual(res_group.step_number, 2)
            self.assertTrue(res_group.can_read)
            self.assertFalse(res_group.can_write)  # Group has no write bit
            self.assertTrue(res_group.can_execute)

            # ----------------------------------------------------
            # Test Step 2: Group match (via supplementary GIDs)
            # ----------------------------------------------------
            res_supp_group = obj.simulate_kernel_access(
                subject_uid=9999,
                subject_gid=8888,
                subject_supplementary_gids=[file_gid, 7777],
            )
            self.assertEqual(res_supp_group.matched_class, "group")
            self.assertEqual(res_supp_group.step_number, 2)
            self.assertTrue(res_supp_group.can_read)
            self.assertFalse(res_supp_group.can_write)
            self.assertTrue(res_supp_group.can_execute)

            # ----------------------------------------------------
            # Test Step 3: Other fallback
            # ----------------------------------------------------
            res_other = obj.simulate_kernel_access(
                subject_uid=9999,
                subject_gid=8888,
                subject_supplementary_gids=[7777, 6666],
            )
            self.assertEqual(res_other.matched_class, "other")
            self.assertEqual(res_other.step_number, 3)
            self.assertFalse(res_other.can_read)
            self.assertFalse(res_other.can_write)
            self.assertFalse(res_other.can_execute)

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_nonexistent_path_returns_none(self):
        obj = FilesystemObject.from_path("/nonexistent/file/path/does_not_exist")
        self.assertIsNone(obj)


if __name__ == "__main__":
    unittest.main()
