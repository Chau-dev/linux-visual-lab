from __future__ import annotations

import sys
import unittest
from PySide6.QtWidgets import QApplication

from app.memory.model import MemorySnapshot, SystemLoadSnapshot
from app.visualizers.memory_view import MemoryLabWidget


class TestMemoryVisualizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_memory_lab_widget_initialization_and_update(self):
        widget = MemoryLabWidget()
        self.assertIsNotNone(widget)

        # Initial state before update
        self.assertIn("Awaiting", widget.lbl_hero_total.text())

        # Create mock snapshots
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
        load = SystemLoadSnapshot(
            load_1m=0.75,
            load_5m=0.82,
            load_15m=1.05,
            runnable_entities=2,
            total_entities=350,
            last_pid=28491,
            uptime_seconds=3660.0,
            idle_seconds=14000.0,
        )

        widget.update_memory(snap, load)

        # Verify hero metrics
        self.assertIn("15.62 GB", widget.lbl_hero_total.text())
        self.assertIn("7.81 GB", widget.lbl_hero_avail.text())

        # Verify raw grid items
        self.assertEqual(widget.raw_labels["MemTotal"].text(), "16384000 kB")
        self.assertEqual(widget.raw_labels["MemAvailable"].text(), "8192000 kB")
        self.assertEqual(widget.raw_labels["MemFree"].text(), "4096000 kB")
        self.assertEqual(widget.raw_labels["KReclaimable"].text(), "256000 kB")

        # Verify system load panel
        self.assertIn("0.75", widget.lbl_load_1m.text())
        self.assertIn("0.82", widget.lbl_load_5m.text())
        self.assertIn("1.05", widget.lbl_load_15m.text())
        self.assertIn("2 / 350", widget.lbl_entities.text())
        self.assertIn("28491", widget.lbl_last_pid.text())
        self.assertIn("1h 1m 0s", widget.lbl_uptime.text())

        # Verify truth label exists
        from PySide6.QtWidgets import QGroupBox
        group_boxes = widget.findChildren(QGroupBox)
        has_truth_disclaimer = any("Not a mathematical partition" in gb.title() for gb in group_boxes)
        self.assertTrue(has_truth_disclaimer, "Must display disclaimer that metrics are not a partition.")


if __name__ == "__main__":
    unittest.main()
