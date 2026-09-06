"""
Advanced Process CPU Tests — Edge Cases, PID Lifecycle, and Live Verification.

Tests cover:
  - Live process reading from /proc/<pid>/stat
  - CLK_TCK-sensitive CPU% calculation across different tick rates
  - CPU% stability across multiple sample intervals
  - Zero-tick delta (completely idle process)
  - Concurrent process tracking (multiple PIDs)
  - Baseline pruning after process termination
  - Formatted CPU percentage output
  - Process model properties (total_cpu_ticks, formatted_cpu_percent)
  - Edge case: process with parentheses in name
  - Edge case: kernel thread with no cmdline
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.cpu.clock import get_clk_tck
from app.process.discovery import read_process_info
from app.process.model import Process
from app.process.registry import ProcessRegistry, diff_process_snapshots


def _proc(
    pid: int = 100,
    ppid: int = 1,
    utime: int = 0,
    stime: int = 0,
    starttime: int = 50000,
    command: str = "worker",
    state: str = "R",
    derived_cpu: float | None = None,
) -> Process:
    """Helper to build Process objects quickly."""
    return Process(
        pid=pid, ppid=ppid, pgid=pid, sid=pid, tpgid=0,
        uid=1000, gid=1000, tty=None,
        state=state, command=command,
        utime_ticks=utime, stime_ticks=stime,
        starttime=starttime, derived_cpu_percent=derived_cpu,
    )


class TestLiveProcessCpu(unittest.TestCase):
    """Verify process CPU fields from live /proc."""

    def test_live_current_process_has_cpu_fields(self):
        """Our own PID should have utime, stime, and starttime from /proc/<pid>/stat."""
        pid = os.getpid()
        proc = read_process_info(pid)
        self.assertIsNotNone(proc, f"Should be able to read /proc/{pid}/stat")
        self.assertGreaterEqual(proc.utime_ticks, 0)
        self.assertGreaterEqual(proc.stime_ticks, 0)
        self.assertGreater(proc.starttime, 0, "starttime should be > 0 for a running process")
        self.assertGreaterEqual(proc.total_cpu_ticks, 0)

    def test_live_init_process_readable(self):
        """PID 1 (init/systemd) should be readable and have CPU fields."""
        proc = read_process_info(1)
        if proc is not None:  # May fail in containers without access
            self.assertEqual(proc.pid, 1)
            self.assertGreaterEqual(proc.utime_ticks, 0)
            self.assertGreaterEqual(proc.stime_ticks, 0)
            self.assertGreater(proc.starttime, 0)


class TestProcessCpuCalculation(unittest.TestCase):
    """Deterministic CPU% calculations with various CLK_TCK values."""

    def test_cpu_percent_with_clk_tck_100(self):
        """Standard Linux: CLK_TCK=100, 50 ticks in 0.5s = 100%."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=0.5)

        p1 = _proc(utime=80, stime=20)  # total=100
        registry.compute_cpu_utilization({100: p1}, observed_at=t0, clk_tck=100)

        p2 = _proc(utime=120, stime=30)  # total=150, delta=50
        enriched = registry.compute_cpu_utilization({100: p2}, observed_at=t1, clk_tck=100)
        # (50 / 100) / 0.5 * 100 = 100.0%
        self.assertAlmostEqual(enriched[100].derived_cpu_percent, 100.0, places=1)

    def test_cpu_percent_with_clk_tck_250(self):
        """Some kernels use CLK_TCK=250. Same formula must apply."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        p1 = _proc(utime=0, stime=0)
        registry.compute_cpu_utilization({100: p1}, observed_at=t0, clk_tck=250)

        p2 = _proc(utime=200, stime=50)  # total=250, delta=250
        enriched = registry.compute_cpu_utilization({100: p2}, observed_at=t1, clk_tck=250)
        # (250 / 250) / 1.0 * 100 = 100.0%
        self.assertAlmostEqual(enriched[100].derived_cpu_percent, 100.0, places=1)

    def test_cpu_percent_with_clk_tck_1000(self):
        """High-resolution kernels with CLK_TCK=1000."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        p1 = _proc(utime=0, stime=0)
        registry.compute_cpu_utilization({100: p1}, observed_at=t0, clk_tck=1000)

        p2 = _proc(utime=400, stime=100)  # total=500, delta=500
        enriched = registry.compute_cpu_utilization({100: p2}, observed_at=t1, clk_tck=1000)
        # (500 / 1000) / 1.0 * 100 = 50.0%
        self.assertAlmostEqual(enriched[100].derived_cpu_percent, 50.0, places=1)

    def test_idle_process_produces_zero_percent(self):
        """A process that uses no CPU ticks between samples should show 0%."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        p1 = _proc(utime=500, stime=100)  # total=600
        registry.compute_cpu_utilization({100: p1}, observed_at=t0, clk_tck=100)

        p2 = _proc(utime=500, stime=100)  # total=600, delta=0
        enriched = registry.compute_cpu_utilization({100: p2}, observed_at=t1, clk_tck=100)
        self.assertAlmostEqual(enriched[100].derived_cpu_percent, 0.0, places=5)

    def test_fractional_cpu_percent(self):
        """Small delta over long interval produces fractional CPU%."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=10.0)

        p1 = _proc(utime=1000, stime=0)
        registry.compute_cpu_utilization({100: p1}, observed_at=t0, clk_tck=100)

        p2 = _proc(utime=1005, stime=0)  # delta=5 ticks
        enriched = registry.compute_cpu_utilization({100: p2}, observed_at=t1, clk_tck=100)
        # (5 / 100) / 10.0 * 100 = 0.5%
        self.assertAlmostEqual(enriched[100].derived_cpu_percent, 0.5, places=2)


class TestMultiProcessTracking(unittest.TestCase):
    """Track multiple processes simultaneously."""

    def test_multiple_processes_independent_baselines(self):
        """Each PID maintains its own CPU baseline independently."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        procs_t0 = {
            100: _proc(pid=100, utime=0, stime=0, starttime=10000, command="fast"),
            200: _proc(pid=200, utime=0, stime=0, starttime=20000, command="slow"),
            300: _proc(pid=300, utime=0, stime=0, starttime=30000, command="idle"),
        }
        registry.compute_cpu_utilization(procs_t0, observed_at=t0, clk_tck=100)

        procs_t1 = {
            100: _proc(pid=100, utime=100, stime=0, starttime=10000, command="fast"),   # 100 ticks
            200: _proc(pid=200, utime=10, stime=0, starttime=20000, command="slow"),    # 10 ticks
            300: _proc(pid=300, utime=0, stime=0, starttime=30000, command="idle"),     # 0 ticks
        }
        enriched = registry.compute_cpu_utilization(procs_t1, observed_at=t1, clk_tck=100)

        self.assertAlmostEqual(enriched[100].derived_cpu_percent, 100.0, places=1)
        self.assertAlmostEqual(enriched[200].derived_cpu_percent, 10.0, places=1)
        self.assertAlmostEqual(enriched[300].derived_cpu_percent, 0.0, places=1)

    def test_process_exits_baseline_pruned(self):
        """When a PID disappears from the snapshot, its baseline should be cleaned up."""
        registry = ProcessRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)
        t2 = t1 + timedelta(seconds=1.0)

        procs_t0 = {
            100: _proc(pid=100, utime=0, stime=0, starttime=10000),
            200: _proc(pid=200, utime=0, stime=0, starttime=20000),
        }
        registry.compute_cpu_utilization(procs_t0, observed_at=t0, clk_tck=100)

        # PID 200 exits
        procs_t1 = {
            100: _proc(pid=100, utime=50, stime=0, starttime=10000),
        }
        enriched = registry.compute_cpu_utilization(procs_t1, observed_at=t1, clk_tck=100)
        self.assertIn(100, enriched)
        self.assertNotIn(200, enriched)

        # PID 200 comes back (new process, different starttime)
        procs_t2 = {
            100: _proc(pid=100, utime=100, stime=0, starttime=10000),
            200: _proc(pid=200, utime=5, stime=0, starttime=99999),
        }
        enriched2 = registry.compute_cpu_utilization(procs_t2, observed_at=t2, clk_tck=100)
        # PID 200 should have no CPU% (fresh baseline)
        self.assertIsNone(enriched2[200].derived_cpu_percent)


class TestProcessCpuStability(unittest.TestCase):
    """Verify CPU% remains stable across multiple intervals."""

    def test_stable_cpu_across_three_intervals(self):
        """A process using 50 ticks per second should report ~50% consistently."""
        registry = ProcessRegistry()
        t = datetime(2026, 9, 6, 12, 0, 0)

        results = []
        for i in range(4):
            p = _proc(utime=50 * i, stime=0, starttime=10000)
            enriched = registry.compute_cpu_utilization(
                {100: p}, observed_at=t + timedelta(seconds=i), clk_tck=100
            )
            if enriched[100].derived_cpu_percent is not None:
                results.append(enriched[100].derived_cpu_percent)

        self.assertEqual(len(results), 3)  # 3 intervals (skip first baseline)
        for pct in results:
            self.assertAlmostEqual(pct, 50.0, places=1)


class TestProcessModelProperties(unittest.TestCase):
    """Verify Process model computed properties."""

    def test_total_cpu_ticks(self):
        p = _proc(utime=450, stime=150)
        self.assertEqual(p.total_cpu_ticks, 600)

    def test_formatted_cpu_percent_none(self):
        p = _proc(derived_cpu=None)
        self.assertEqual(p.formatted_cpu_percent, "—")

    def test_formatted_cpu_percent_zero(self):
        p = _proc(derived_cpu=0.0)
        self.assertEqual(p.formatted_cpu_percent, "0.0%")

    def test_formatted_cpu_percent_normal(self):
        p = _proc(derived_cpu=42.7)
        self.assertEqual(p.formatted_cpu_percent, "42.7%")

    def test_formatted_cpu_percent_over_100(self):
        p = _proc(derived_cpu=350.0)
        self.assertEqual(p.formatted_cpu_percent, "350.0%")

    def test_process_is_frozen(self):
        """Process is a frozen dataclass — mutation should raise."""
        p = _proc()
        with self.assertRaises(AttributeError):
            p.utime_ticks = 999


class TestDiffProcessSnapshots(unittest.TestCase):
    """Verify process lifecycle event generation with CPU context."""

    def test_new_process_has_cpu_fields_in_event_data(self):
        """process.created events should include CPU tick fields."""
        p = _proc(utime=100, stime=50, starttime=50000)
        events = diff_process_snapshots({}, {100: p})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "process.created")
        self.assertIn("process", events[0].data)
        self.assertEqual(events[0].data["process"].utime_ticks, 100)
        self.assertEqual(events[0].data["process"].stime_ticks, 50)

    def test_pid_reuse_detection_generates_remove_and_create(self):
        """Same PID with different starttime → removed old + created new."""
        old = _proc(pid=5000, starttime=10000, command="old_proc")
        new = _proc(pid=5000, starttime=20000, command="new_proc")

        events = diff_process_snapshots({5000: old}, {5000: new})
        types = [e.event_type for e in events]
        self.assertIn("process.removed", types)
        self.assertIn("process.created", types)

    def test_same_pid_same_starttime_no_remove(self):
        """Same PID, same starttime, different state → state_changed only."""
        old = _proc(pid=5000, starttime=10000, state="S")
        new = _proc(pid=5000, starttime=10000, state="R")

        events = diff_process_snapshots({5000: old}, {5000: new})
        types = [e.event_type for e in events]
        self.assertNotIn("process.removed", types)
        self.assertIn("process.state_changed", types)


class TestProcessParsingEdgeCases(unittest.TestCase):
    """Edge cases in /proc/<pid>/stat parsing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_process_name_with_parentheses(self):
        """Process names like '(sd-pam)' contain parentheses — parser must use rfind(')')."""
        pid_dir = self.base_path / "999"
        pid_dir.mkdir(parents=True)
        # comm = "(sd-pam)" contains inner parentheses
        stat_content = "999 ((sd-pam)) S 1 999 999 0 0 0 0 0 0 0 100 50 0 0 20 0 1 0 12345 0 0 0 0"
        (pid_dir / "stat").write_text(stat_content, encoding="utf-8")
        (pid_dir / "status").write_text("Uid:\t0\t0\t0\t0\nGid:\t0\t0\t0\t0\n", encoding="utf-8")
        (pid_dir / "cmdline").write_bytes(b"")

        proc = read_process_info(999, proc_root=self.base_path)
        self.assertIsNotNone(proc)
        self.assertEqual(proc.command, "(sd-pam)")
        self.assertEqual(proc.utime_ticks, 100)
        self.assertEqual(proc.stime_ticks, 50)
        self.assertEqual(proc.starttime, 12345)

    def test_process_name_with_spaces(self):
        """Process names can contain spaces."""
        pid_dir = self.base_path / "888"
        pid_dir.mkdir(parents=True)
        stat_content = "888 (Web Content) S 1 888 888 0 0 0 0 0 0 0 200 75 0 0 20 0 1 0 99999 0 0 0 0"
        (pid_dir / "stat").write_text(stat_content, encoding="utf-8")
        (pid_dir / "status").write_text("Uid:\t1000\t1000\t1000\t1000\nGid:\t1000\t1000\t1000\t1000\n", encoding="utf-8")
        (pid_dir / "cmdline").write_bytes(b"firefox\x00--content\x00")

        proc = read_process_info(888, proc_root=self.base_path)
        self.assertIsNotNone(proc)
        self.assertEqual(proc.command, "Web Content")
        self.assertEqual(proc.utime_ticks, 200)
        self.assertEqual(proc.stime_ticks, 75)

    def test_kernel_thread_no_cmdline(self):
        """Kernel threads have empty /proc/<pid>/cmdline — command should be [comm]."""
        pid_dir = self.base_path / "777"
        pid_dir.mkdir(parents=True)
        stat_content = "777 (kworker/0:1) I 2 0 0 0 0 0 0 0 0 0 5 3 0 0 20 0 1 0 555 0 0 0 0"
        (pid_dir / "stat").write_text(stat_content, encoding="utf-8")
        (pid_dir / "status").write_text("Uid:\t0\t0\t0\t0\nGid:\t0\t0\t0\t0\n", encoding="utf-8")
        (pid_dir / "cmdline").write_bytes(b"")

        proc = read_process_info(777, proc_root=self.base_path)
        self.assertIsNotNone(proc)
        self.assertEqual(proc.command, "kworker/0:1")
        self.assertEqual(proc.cmdline, "[kworker/0:1]")
        self.assertEqual(proc.utime_ticks, 5)
        self.assertEqual(proc.stime_ticks, 3)

    def test_nonexistent_pid_returns_none(self):
        proc = read_process_info(999999, proc_root=self.base_path)
        self.assertIsNone(proc)

    def test_truncated_stat_file(self):
        """If /proc/<pid>/stat has fewer fields than expected, CPU fields default to 0."""
        pid_dir = self.base_path / "666"
        pid_dir.mkdir(parents=True)
        # Only 6 fields after comm → not enough for utime/stime/starttime
        stat_content = "666 (short) S 1 666 666"
        (pid_dir / "stat").write_text(stat_content, encoding="utf-8")
        (pid_dir / "status").write_text("Uid:\t0\t0\t0\t0\nGid:\t0\t0\t0\t0\n", encoding="utf-8")
        (pid_dir / "cmdline").write_bytes(b"")

        proc = read_process_info(666, proc_root=self.base_path)
        if proc is not None:
            self.assertEqual(proc.utime_ticks, 0)
            self.assertEqual(proc.stime_ticks, 0)
            self.assertEqual(proc.starttime, 0)


if __name__ == "__main__":
    unittest.main()
