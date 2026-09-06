from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.cpu.discovery import read_cpu_stat


class TestCpuDiscovery(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_read_cpu_stat_valid_multicore(self):
        mock_stat = (
            "cpu  2255 34 2290 22625563 6290 127 456 0 0 0\n"
            "cpu0 1132 17 1141 11311718 3675  35 211 0 0 0\n"
            "cpu1 1123 17 1149 11313845 2614  92 245 0 0 0\n"
            "intr 11493054 22 0 0 0\n"
            "ctxt 1150495\n"
            "btime 1709683200\n"
            "processes 86420\n"
            "procs_running 2\n"
            "procs_blocked 1\n"
            "softirq 482015 0 200\n"
        )
        stat_file = self.base_path / "stat"
        stat_file.write_text(mock_stat, encoding="utf-8")

        snap = read_cpu_stat(stat_path=stat_file)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.total_cpu.user, 2255)
        self.assertEqual(snap.total_cpu.nice, 34)
        self.assertEqual(snap.total_cpu.system, 2290)
        self.assertEqual(snap.total_cpu.idle, 22625563)
        self.assertEqual(snap.total_cpu.iowait, 6290)
        self.assertEqual(snap.total_cpu.irq, 127)
        self.assertEqual(snap.total_cpu.softirq, 456)
        self.assertEqual(snap.total_cpu.steal, 0)
        self.assertEqual(snap.total_cpu.guest, 0)
        self.assertEqual(snap.total_cpu.guest_nice, 0)

        self.assertEqual(len(snap.cores), 2)
        self.assertIn(0, snap.cores)
        self.assertIn(1, snap.cores)
        self.assertEqual(snap.cores[0].user, 1132)
        self.assertEqual(snap.cores[1].user, 1123)

        self.assertEqual(snap.ctxt, 1150495)
        self.assertEqual(snap.btime, 1709683200)
        self.assertEqual(snap.processes, 86420)
        self.assertEqual(snap.procs_running, 2)
        self.assertEqual(snap.procs_blocked, 1)

    def test_read_cpu_stat_minimal_format(self):
        # Only 4 fields on cpu line
        mock_stat = (
            "cpu  100 20 30 850\n"
            "ctxt 500\n"
            "processes 10\n"
        )
        stat_file = self.base_path / "stat"
        stat_file.write_text(mock_stat, encoding="utf-8")

        snap = read_cpu_stat(stat_path=stat_file)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.total_cpu.user, 100)
        self.assertEqual(snap.total_cpu.nice, 20)
        self.assertEqual(snap.total_cpu.system, 30)
        self.assertEqual(snap.total_cpu.idle, 850)
        self.assertEqual(snap.total_cpu.iowait, 0)
        self.assertEqual(snap.ctxt, 500)
        self.assertEqual(snap.processes, 10)

    def test_read_cpu_stat_missing_file_returns_none(self):
        non_existent = self.base_path / "does_not_exist"
        self.assertIsNone(read_cpu_stat(stat_path=non_existent))

    def test_read_cpu_stat_missing_cpu_line_returns_none(self):
        mock_stat = "ctxt 500\nprocesses 10\n"
        stat_file = self.base_path / "stat"
        stat_file.write_text(mock_stat, encoding="utf-8")
        self.assertIsNone(read_cpu_stat(stat_path=stat_file))
