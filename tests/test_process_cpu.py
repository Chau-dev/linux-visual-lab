from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.process.discovery import read_process_info
from app.process.model import Process
from app.process.registry import ProcessRegistry, diff_process_snapshots


class TestProcessCpu(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_read_process_info_extracts_cpu_ticks_and_starttime(self):
        pid_dir = self.base_path / "1234"
        pid_dir.mkdir(parents=True, exist_ok=True)

        # /proc/1234/stat
        # Field 1: 1234
        # Field 2: (my_process)
        # Remainder:
        # idx 0: S (field 3)
        # idx 1: 1 (field 4)
        # idx 2: 1234 (field 5)
        # idx 3: 1000 (field 6)
        # idx 4: 0 (field 7)
        # idx 5: 0 (field 8)
        # idx 6: 0 (field 9)
        # idx 7: 0 (field 10)
        # idx 8: 0 (field 11)
        # idx 9: 0 (field 12)
        # idx 10: 0 (field 13)
        # idx 11: 450 (field 14: utime)
        # idx 12: 150 (field 15: stime)
        # idx 13: 0 (field 16: cutime)
        # idx 14: 0 (field 17: cstime)
        # idx 15: 20 (field 18: priority)
        # idx 16: 0 (field 19: nice)
        # idx 17: 4 (field 20: num_threads)
        # idx 18: 0 (field 21: itrealvalue)
        # idx 19: 987654 (field 22: starttime)
        stat_content = "1234 (my_process) S 1 1234 1000 0 0 0 0 0 0 0 450 150 0 0 20 0 4 0 987654 0 0 0 0"
        (pid_dir / "stat").write_text(stat_content, encoding="utf-8")
        (pid_dir / "status").write_text("Uid:\t1000\t1000\t1000\t1000\nGid:\t1000\t1000\t1000\t1000\n", encoding="utf-8")
        (pid_dir / "cmdline").write_bytes(b"my_process\x00arg1\x00")

        proc = read_process_info(1234, proc_root=self.base_path)
        self.assertIsNotNone(proc)
        self.assertEqual(proc.pid, 1234)
        self.assertEqual(proc.command, "my_process")
        self.assertEqual(proc.utime_ticks, 450)
        self.assertEqual(proc.stime_ticks, 150)
        self.assertEqual(proc.total_cpu_ticks, 600)
        self.assertEqual(proc.starttime, 987654)

    def test_deterministic_process_cpu_calculation(self):
        """Mathematical verification: (Δticks / CLK_TCK) / Δt * 100%."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=0.5)

        p1 = Process(
            pid=100,
            ppid=1,
            pgid=100,
            sid=100,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="worker",
            utime_ticks=80,
            stime_ticks=20,     # total = 100 ticks
            starttime=50000,
        )

        # Baseline sample (t0)
        enriched_t0 = registry.compute_cpu_utilization({100: p1}, observed_at=t0, clk_tck=100)
        self.assertIsNone(enriched_t0[100].derived_cpu_percent)

        # Sample at t1 (+0.5s): total ticks increases to 150 (Δticks = 50)
        p2 = Process(
            pid=100,
            ppid=1,
            pgid=100,
            sid=100,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="worker",
            utime_ticks=120,
            stime_ticks=30,     # total = 150 ticks
            starttime=50000,
        )
        enriched_t1 = registry.compute_cpu_utilization({100: p2}, observed_at=t1, clk_tck=100)
        # Expected: (50 ticks / 100 ticks_per_sec) / 0.5s * 100 = 100.0%
        self.assertIsNotNone(enriched_t1[100].derived_cpu_percent)
        self.assertAlmostEqual(enriched_t1[100].derived_cpu_percent, 100.0, places=1)
        self.assertEqual(enriched_t1[100].formatted_cpu_percent, "100.0%")

    def test_multi_threaded_smp_cpu_scaling_exceeds_100_percent(self):
        """Verify that multi-threaded processes are not clamped to 100%."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=0.5)

        p1 = Process(
            pid=200,
            ppid=1,
            pgid=200,
            sid=200,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="threaded_app",
            utime_ticks=100,
            stime_ticks=0,      # total = 100 ticks
            starttime=60000,
        )
        registry.compute_cpu_utilization({200: p1}, observed_at=t0, clk_tck=100)

        # In 0.5s, 4 threads accumulate 150 ticks (Δticks = 150)
        p2 = Process(
            pid=200,
            ppid=1,
            pgid=200,
            sid=200,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="threaded_app",
            utime_ticks=250,
            stime_ticks=0,      # total = 250 ticks
            starttime=60000,
        )
        enriched = registry.compute_cpu_utilization({200: p2}, observed_at=t1, clk_tck=100)
        # Expected: (150 ticks / 100 ticks_per_sec) / 0.5s * 100 = 300.0%
        self.assertIsNotNone(enriched[200].derived_cpu_percent)
        self.assertAlmostEqual(enriched[200].derived_cpu_percent, 300.0, places=1)
        self.assertEqual(enriched[200].formatted_cpu_percent, "300.0%")

    def test_pid_reuse_protection_with_starttime(self):
        """Verify that when Linux reuses a PID with a different starttime, the old baseline is discarded."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=0.5)

        # Process A: PID 5000, starttime 10000, accumulated 5000 ticks
        proc_a = Process(
            pid=5000,
            ppid=1,
            pgid=5000,
            sid=5000,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="S",
            command="proc_a",
            utime_ticks=4000,
            stime_ticks=1000,   # total = 5000 ticks
            starttime=10000,
        )
        registry.compute_cpu_utilization({5000: proc_a}, observed_at=t0, clk_tck=100)

        # Process A exits. New Process B gets recycled PID 5000, starttime 20000, 10 ticks
        proc_b = Process(
            pid=5000,
            ppid=1,
            pgid=5000,
            sid=5000,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="proc_b",
            utime_ticks=8,
            stime_ticks=2,      # total = 10 ticks
            starttime=20000,
        )

        # Diffing snapshots must emit removed for proc_a and created for proc_b
        events = diff_process_snapshots({5000: proc_a}, {5000: proc_b}, observed_at=t1)
        event_types = [e.event_type for e in events]
        self.assertIn("process.removed", event_types)
        self.assertIn("process.created", event_types)

        # CPU calculation must treat proc_b as a fresh baseline, NOT calculating fake negative delta (10 - 5000)
        enriched = registry.compute_cpu_utilization({5000: proc_b}, observed_at=t1, clk_tck=100)
        self.assertIsNone(enriched[5000].derived_cpu_percent)

    def test_process_counter_decrease_resets_baseline(self):
        """Verify that unexpected tick counter decrease does not produce negative CPU%."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=0.5)

        p1 = Process(
            pid=300,
            ppid=1,
            pgid=300,
            sid=300,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="test",
            utime_ticks=500,
            stime_ticks=100,    # 600 ticks
            starttime=70000,
        )
        registry.compute_cpu_utilization({300: p1}, observed_at=t0, clk_tck=100)

        p2 = Process(
            pid=300,
            ppid=1,
            pgid=300,
            sid=300,
            tpgid=0,
            uid=1000,
            gid=1000,
            tty=None,
            state="R",
            command="test",
            utime_ticks=100,
            stime_ticks=50,     # Decreased to 150 ticks
            starttime=70000,
        )
        enriched = registry.compute_cpu_utilization({300: p2}, observed_at=t1, clk_tck=100)
        self.assertIsNone(enriched[300].derived_cpu_percent)
