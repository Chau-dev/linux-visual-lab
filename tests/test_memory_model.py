from __future__ import annotations

import unittest
from app.memory.model import MemorySnapshot, SystemLoadSnapshot, format_kb


class TestMemoryModel(unittest.TestCase):
    def test_memory_snapshot_raw_preservation(self):
        snap = MemorySnapshot(
            mem_total_kb=16384000,
            mem_free_kb=4096000,
            mem_available_kb=8192000,
            buffers_kb=512000,
            cached_kb=3584000,
            swap_total_kb=2048000,
            swap_free_kb=1024000,
            active_anon_kb=2048000,
            inactive_anon_kb=1024000,
            active_file_kb=1536000,
            inactive_file_kb=1536000,
            unevictable_kb=0,
            dirty_kb=128,
            writeback_kb=0,
            anon_pages_kb=3072000,
            mapped_kb=512000,
            shmem_kb=256000,
            kreclaimable_kb=256000,
            slab_kb=512000,
            sreclaimable_kb=256000,
            sunreclaim_kb=256000,
            committed_as_kb=6144000,
            commit_limit_kb=10240000,
            swap_cached_kb=0,
        )

        self.assertEqual(snap.mem_total_kb, 16384000)
        self.assertEqual(snap.mem_free_kb, 4096000)
        self.assertEqual(snap.mem_available_kb, 8192000)
        self.assertEqual(snap.buffers_kb, 512000)
        self.assertEqual(snap.cached_kb, 3584000)
        self.assertEqual(snap.swap_total_kb, 2048000)
        self.assertEqual(snap.swap_free_kb, 1024000)
        self.assertEqual(snap.kreclaimable_kb, 256000)

    def test_memory_snapshot_derived_properties(self):
        snap = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=4000,
            mem_available_kb=10000,
            buffers_kb=1000,
            cached_kb=3000,
            swap_total_kb=8000,
            swap_free_kb=2000,
            kreclaimable_kb=500,
        )

        # derived_used_approx_kb = MemTotal - MemAvailable = 16000 - 10000 = 6000
        self.assertEqual(snap.derived_used_approx_kb, 6000)

        # derived_available_percent = 10000 / 16000 * 100 = 62.5%
        self.assertAlmostEqual(snap.derived_available_percent, 62.5)

        # derived_swap_used_kb = SwapTotal - SwapFree = 8000 - 2000 = 6000
        self.assertEqual(snap.derived_swap_used_kb, 6000)

        # derived_swap_used_percent = 6000 / 8000 * 100 = 75.0%
        self.assertAlmostEqual(snap.derived_swap_used_percent, 75.0)

        # derived_buffers_cached_kreclaimable_kb = Buffers + Cached + KReclaimable = 1000 + 3000 + 500 = 4500
        self.assertEqual(snap.derived_buffers_cached_kreclaimable_kb, 4500)

    def test_memory_snapshot_derived_properties_zero_swap(self):
        snap = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=4000,
            mem_available_kb=10000,
            buffers_kb=1000,
            cached_kb=3000,
            swap_total_kb=0,
            swap_free_kb=0,
            kreclaimable_kb=None,
        )

        self.assertEqual(snap.derived_swap_used_kb, 0)
        self.assertEqual(snap.derived_swap_used_percent, 0.0)
        # Without kreclaimable: Buffers + Cached = 1000 + 3000 = 4000
        self.assertEqual(snap.derived_buffers_cached_kreclaimable_kb, 4000)

    def test_format_kb(self):
        self.assertEqual(format_kb(None), "N/A")
        self.assertEqual(format_kb(0), "0 KB")
        self.assertEqual(format_kb(512), "512 KB")
        self.assertEqual(format_kb(1024), "1.00 MB")
        self.assertEqual(format_kb(1048576), "1.00 GB")
        self.assertEqual(format_kb(16777216), "16.00 GB")

    def test_system_load_snapshot_and_properties(self):
        load = SystemLoadSnapshot(
            load_1m=0.52,
            load_5m=0.75,
            load_15m=1.20,
            runnable_entities=2,
            total_entities=345,
            last_pid=12345,
            uptime_seconds=3665.5,
            idle_seconds=14000.2,
        )

        self.assertEqual(load.load_1m, 0.52)
        self.assertEqual(load.load_5m, 0.75)
        self.assertEqual(load.load_15m, 1.20)
        self.assertEqual(load.runnable_entities, 2)
        self.assertEqual(load.total_entities, 345)
        self.assertEqual(load.last_pid, 12345)
        # 3665 seconds = 1h 1m 5s
        self.assertEqual(load.uptime_formatted, "1h 1m 5s")


if __name__ == "__main__":
    unittest.main()
