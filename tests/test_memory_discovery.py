from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.memory.discovery import read_memory_snapshot, read_system_load


class TestMemoryDiscovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_read_memory_snapshot_success(self):
        mock_meminfo = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         4096000 kB\n"
            "MemAvailable:    8192000 kB\n"
            "Buffers:          512000 kB\n"
            "Cached:          3584000 kB\n"
            "SwapCached:            0 kB\n"
            "Active(anon):    2048000 kB\n"
            "Inactive(anon):  1024000 kB\n"
            "Active(file):    1536000 kB\n"
            "Inactive(file):  1536000 kB\n"
            "Unevictable:           0 kB\n"
            "Mlocked:               0 kB\n"
            "SwapTotal:       2048000 kB\n"
            "SwapFree:        1024000 kB\n"
            "Dirty:               128 kB\n"
            "Writeback:             0 kB\n"
            "AnonPages:       3072000 kB\n"
            "Mapped:           512000 kB\n"
            "Shmem:            256000 kB\n"
            "KReclaimable:     256000 kB\n"
            "Slab:             512000 kB\n"
            "SReclaimable:     256000 kB\n"
            "SUnreclaim:       256000 kB\n"
            "KernelStack:       16384 kB\n"
            "PageTables:        32768 kB\n"
            "NFS_Unstable:          0 kB\n"
            "Bounce:                0 kB\n"
            "WritebackTmp:          0 kB\n"
            "CommitLimit:    10240000 kB\n"
            "Committed_AS:    6144000 kB\n"
        )
        meminfo_path = self.base_path / "meminfo"
        meminfo_path.write_text(mock_meminfo)

        snap = read_memory_snapshot(meminfo_path)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.mem_total_kb, 16384000)
        self.assertEqual(snap.mem_free_kb, 4096000)
        self.assertEqual(snap.mem_available_kb, 8192000)
        self.assertEqual(snap.buffers_kb, 512000)
        self.assertEqual(snap.cached_kb, 3584000)
        self.assertEqual(snap.swap_total_kb, 2048000)
        self.assertEqual(snap.swap_free_kb, 1024000)
        self.assertEqual(snap.kreclaimable_kb, 256000)
        self.assertEqual(snap.active_anon_kb, 2048000)
        self.assertEqual(snap.inactive_anon_kb, 1024000)
        self.assertEqual(snap.committed_as_kb, 6144000)
        self.assertEqual(snap.commit_limit_kb, 10240000)

    def test_required_meminfo_field_missing_does_not_create_fake_zero(self):
        """
        If a required field (such as MemAvailable) is missing, read_memory_snapshot MUST
        return None rather than inventing a fake 0 kB.
        """
        incomplete_meminfo = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         4096000 kB\n"
            # MemAvailable missing!
            "Buffers:          512000 kB\n"
            "Cached:          3584000 kB\n"
            "SwapTotal:       2048000 kB\n"
            "SwapFree:        1024000 kB\n"
        )
        meminfo_path = self.base_path / "meminfo"
        meminfo_path.write_text(incomplete_meminfo)

        snap = read_memory_snapshot(meminfo_path)
        self.assertIsNone(snap, "Missing required key must result in None snapshot, not fake defaults.")

    def test_optional_meminfo_field_missing_is_not_fabricated(self):
        """
        If optional fields (like KReclaimable, Active(anon)) are missing, they must be None,
        not fabricated as 0.
        """
        minimal_meminfo = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         4096000 kB\n"
            "MemAvailable:    8192000 kB\n"
            "Buffers:          512000 kB\n"
            "Cached:          3584000 kB\n"
            "SwapTotal:       2048000 kB\n"
            "SwapFree:        1024000 kB\n"
        )
        meminfo_path = self.base_path / "meminfo"
        meminfo_path.write_text(minimal_meminfo)

        snap = read_memory_snapshot(meminfo_path)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.mem_total_kb, 16384000)
        self.assertIsNone(snap.kreclaimable_kb)
        self.assertIsNone(snap.active_anon_kb)
        self.assertIsNone(snap.committed_as_kb)

    def test_non_kb_unit_error_handling(self):
        """
        If a field has an unexpected unit or is malformed, handle safely.
        """
        bad_meminfo = (
            "MemTotal:       16384000 MB\n"  # unexpected unit
            "MemFree:         4096000 kB\n"
            "MemAvailable:    8192000 kB\n"
            "Buffers:          512000 kB\n"
            "Cached:          3584000 kB\n"
            "SwapTotal:       2048000 kB\n"
            "SwapFree:        1024000 kB\n"
        )
        meminfo_path = self.base_path / "meminfo"
        meminfo_path.write_text(bad_meminfo)

        snap = read_memory_snapshot(meminfo_path)
        self.assertIsNone(snap)

    def test_read_system_load_success(self):
        loadavg_path = self.base_path / "loadavg"
        loadavg_path.write_text("0.45 0.72 1.10 3/420 28419\n")

        uptime_path = self.base_path / "uptime"
        uptime_path.write_text("84321.45 168400.12\n")

        load = read_system_load(loadavg_path=loadavg_path, uptime_path=uptime_path)
        self.assertIsNotNone(load)
        self.assertEqual(load.load_1m, 0.45)
        self.assertEqual(load.load_5m, 0.72)
        self.assertEqual(load.load_15m, 1.10)
        self.assertEqual(load.runnable_entities, 3)
        self.assertEqual(load.total_entities, 420)
        self.assertEqual(load.last_pid, 28419)
        self.assertAlmostEqual(load.uptime_seconds, 84321.45)
        self.assertAlmostEqual(load.idle_seconds, 168400.12)

    def test_read_system_load_missing_file(self):
        loadavg_path = self.base_path / "nonexistent_loadavg"
        uptime_path = self.base_path / "nonexistent_uptime"
        load = read_system_load(loadavg_path=loadavg_path, uptime_path=uptime_path)
        self.assertIsNone(load)

    def test_read_actual_linux_proc(self):
        """Verify discovery against real host /proc."""
        snap = read_memory_snapshot()
        self.assertIsNotNone(snap)
        self.assertGreater(snap.mem_total_kb, 0)
        self.assertGreater(snap.mem_available_kb, 0)

        load = read_system_load()
        self.assertIsNotNone(load)
        self.assertGreater(load.total_entities, 0)
        self.assertGreater(load.uptime_seconds, 0)


if __name__ == "__main__":
    unittest.main()
