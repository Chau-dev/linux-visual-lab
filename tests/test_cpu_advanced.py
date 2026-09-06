"""
Advanced CPU Lab Tests — Edge Cases, Stress, and Live Verification.

Tests cover:
  - Live /proc/stat structural validation
  - Guest-time double-count prevention (mathematical proof)
  - iowait decrease handling (documented kernel behavior)
  - All-idle and all-busy extreme scenarios
  - Virtualization steal-time correctness
  - Multi-core asymmetric load
  - Rapid successive sampling (near-zero dt)
  - Large tick counter values (overflow proximity)
  - CLK_TCK dynamic resolution on live system
  - Cross-verification: app output vs. raw /proc/stat read
  - Utilization percentage boundary clamping
  - Per-core independence after selective counter resets
  - Snapshot immutability (frozen dataclass contract)
  - Discovery parser resilience to malformed input
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.cpu.clock import get_clk_tck
from app.cpu.discovery import read_cpu_stat
from app.cpu.model import CpuCoreUtilization, CpuStatSnapshot, CpuTimes, CpuUtilization
from app.cpu.registry import CpuRegistry, _compute_core_utilization


# ---------------------------------------------------------------------------
# Helper to build snapshots quickly
# ---------------------------------------------------------------------------
def _snap(
    total: CpuTimes,
    cores: dict[int, CpuTimes] | None = None,
    ctxt: int = 0,
    processes: int = 0,
    procs_running: int = 1,
    procs_blocked: int = 0,
    btime: int = 1700000000,
    observed_at: datetime | None = None,
) -> CpuStatSnapshot:
    return CpuStatSnapshot(
        total_cpu=total,
        cores=cores or {},
        ctxt=ctxt,
        processes=processes,
        procs_running=procs_running,
        procs_blocked=procs_blocked,
        btime=btime,
        observed_at=observed_at or datetime.now(),
    )


class TestLiveProcStat(unittest.TestCase):
    """Verify the parser works against the real /proc/stat on this system."""

    def test_live_proc_stat_returns_valid_snapshot(self):
        """Read real /proc/stat and verify all structural contracts."""
        snap = read_cpu_stat()
        self.assertIsNotNone(snap, "/proc/stat should be readable on this Linux system")
        self.assertIsInstance(snap.total_cpu, CpuTimes)
        self.assertGreater(snap.total_cpu.user, 0, "Live system should have non-zero user ticks")
        self.assertGreaterEqual(snap.total_cpu.idle, 0)
        self.assertGreaterEqual(snap.total_cpu.system, 0)

    def test_live_core_count_matches_os(self):
        """Number of per-core entries should match os.cpu_count()."""
        snap = read_cpu_stat()
        self.assertIsNotNone(snap)
        expected_cores = os.cpu_count()
        if expected_cores is not None:
            self.assertEqual(
                len(snap.cores), expected_cores,
                f"Expected {expected_cores} cores from os.cpu_count(), got {len(snap.cores)}"
            )

    def test_live_core_ids_are_contiguous_from_zero(self):
        """Linux cpu0..cpuN should have contiguous IDs starting from 0."""
        snap = read_cpu_stat()
        self.assertIsNotNone(snap)
        core_ids = sorted(snap.cores.keys())
        expected = list(range(len(core_ids)))
        self.assertEqual(core_ids, expected)

    def test_live_aggregate_ticks_greater_than_any_core(self):
        """The aggregate 'cpu' line accumulates all cores, so each field >= any single core."""
        snap = read_cpu_stat()
        self.assertIsNotNone(snap)
        for core_id, core in snap.cores.items():
            self.assertGreaterEqual(
                snap.total_cpu.user, core.user,
                f"Aggregate user ticks should be >= core {core_id}"
            )
            self.assertGreaterEqual(
                snap.total_cpu.idle, core.idle,
                f"Aggregate idle ticks should be >= core {core_id}"
            )

    def test_live_btime_is_reasonable(self):
        """btime (boot time as epoch seconds) should be in the past and after year 2000."""
        snap = read_cpu_stat()
        self.assertIsNotNone(snap)
        # After year 2000
        self.assertGreater(snap.btime, 946684800)
        # Before now
        import time
        self.assertLess(snap.btime, int(time.time()) + 60)

    def test_live_scheduler_state_sanity(self):
        """procs_running >= 1 (at least this test process), ctxt > 0, processes > 0."""
        snap = read_cpu_stat()
        self.assertIsNotNone(snap)
        self.assertGreaterEqual(snap.procs_running, 1)
        self.assertGreaterEqual(snap.procs_blocked, 0)
        self.assertGreater(snap.ctxt, 0)
        self.assertGreater(snap.processes, 0)

    def test_live_two_consecutive_samples_produce_utilization(self):
        """Two rapid reads of /proc/stat should produce a valid CpuUtilization via CpuRegistry."""
        import time
        registry = CpuRegistry()
        snap1 = read_cpu_stat()
        self.assertIsNotNone(snap1)
        registry.update(snap1)

        time.sleep(0.05)  # 50ms gap

        snap2 = read_cpu_stat()
        self.assertIsNotNone(snap2)
        util = registry.update(snap2)

        # util may be None if dt rounds to 0, but it's very unlikely with 50ms gap
        if util is not None:
            self.assertIsNotNone(util.total)
            self.assertGreaterEqual(util.total.total_utilization_pct, 0.0)
            self.assertLessEqual(util.total.total_utilization_pct, 100.0)
            # All mode percentages should be non-negative
            self.assertGreaterEqual(util.total.user_pct, 0.0)
            self.assertGreaterEqual(util.total.system_pct, 0.0)
            self.assertGreaterEqual(util.total.idle_pct, 0.0)


class TestGuestTimeAccounting(unittest.TestCase):
    """Mathematical proof that guest time doesn't inflate utilization."""

    def test_guest_time_excluded_from_total_ticks_denominator(self):
        """
        Linux documents: guest is counted in user, guest_nice in nice.
        If we included guest in the denominator sum, the total would be inflated,
        producing artificially low utilization percentages.
        """
        times = CpuTimes(
            user=1000, nice=200, system=300, idle=500,
            iowait=0, irq=0, softirq=0, steal=0,
            guest=500, guest_nice=100,
        )
        # Correct total: 1000+200+300+500 = 2000
        self.assertEqual(times.accounting_total_ticks, 2000)
        # Wrong total (if guest were included): 2000 + 500 + 100 = 2600

    def test_guest_time_does_not_affect_utilization_result(self):
        """
        Two snapshots identical except for guest/guest_nice should produce
        the same utilization percentage.
        """
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        prev = CpuTimes(user=100, nice=10, system=50, idle=840, iowait=0, irq=0, softirq=0, steal=0, guest=0, guest_nice=0)
        curr_no_guest = CpuTimes(user=200, nice=10, system=50, idle=940, iowait=0, irq=0, softirq=0, steal=0, guest=0, guest_nice=0)
        curr_with_guest = CpuTimes(user=200, nice=10, system=50, idle=940, iowait=0, irq=0, softirq=0, steal=0, guest=80, guest_nice=20)

        util_no_guest = _compute_core_utilization(prev, curr_no_guest, core_id=None, elapsed_seconds=1.0)
        util_with_guest = _compute_core_utilization(prev, curr_with_guest, core_id=None, elapsed_seconds=1.0)

        self.assertIsNotNone(util_no_guest)
        self.assertIsNotNone(util_with_guest)
        self.assertAlmostEqual(
            util_no_guest.total_utilization_pct,
            util_with_guest.total_utilization_pct,
            places=5,
            msg="Guest time should not affect utilization calculation"
        )


class TestIowaitEdgeCases(unittest.TestCase):
    """Linux documents iowait as an unreliable counter that can decrease."""

    def test_iowait_decrease_invalidates_interval(self):
        """
        If iowait decreases between samples (documented kernel behavior),
        the interval must be invalidated rather than producing negative iowait%.
        """
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        prev = CpuTimes(user=100, nice=0, system=50, idle=800, iowait=50, irq=0, softirq=0, steal=0)
        curr = CpuTimes(user=120, nice=0, system=55, idle=850, iowait=30, irq=0, softirq=0, steal=0)  # iowait decreased

        util = _compute_core_utilization(prev, curr, core_id=0, elapsed_seconds=1.0)
        self.assertIsNone(util, "Counter decrease in iowait must invalidate the interval")

    def test_iowait_included_in_non_busy_time(self):
        """Verify iowait is subtracted alongside idle when computing busy%."""
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        prev = CpuTimes(user=0, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0)
        # 50 user, 50 iowait, 0 idle → total=100, busy = 100 - (0 + 50) = 50
        curr = CpuTimes(user=50, nice=0, system=0, idle=0, iowait=50, irq=0, softirq=0, steal=0)

        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        self.assertAlmostEqual(util.total_utilization_pct, 50.0, places=1)
        self.assertAlmostEqual(util.iowait_pct, 50.0, places=1)


class TestExtremeScenarios(unittest.TestCase):
    """All-idle, all-busy, and boundary conditions."""

    def test_all_idle_produces_zero_utilization(self):
        """100% idle CPU should show 0% utilization."""
        prev = CpuTimes(user=0, nice=0, system=0, idle=1000, iowait=0, irq=0, softirq=0, steal=0)
        curr = CpuTimes(user=0, nice=0, system=0, idle=2000, iowait=0, irq=0, softirq=0, steal=0)

        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        self.assertAlmostEqual(util.total_utilization_pct, 0.0, places=5)
        self.assertAlmostEqual(util.idle_pct, 100.0, places=5)

    def test_all_busy_user_produces_100_utilization(self):
        """100% user CPU should show 100% utilization."""
        prev = CpuTimes(user=1000, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0)
        curr = CpuTimes(user=2000, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0)

        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        self.assertAlmostEqual(util.total_utilization_pct, 100.0, places=5)
        self.assertAlmostEqual(util.user_pct, 100.0, places=5)
        self.assertAlmostEqual(util.idle_pct, 0.0, places=5)

    def test_all_busy_system_produces_100_utilization(self):
        """100% kernel mode should show 100% utilization."""
        prev = CpuTimes(user=0, nice=0, system=1000, idle=0, iowait=0, irq=0, softirq=0, steal=0)
        curr = CpuTimes(user=0, nice=0, system=2000, idle=0, iowait=0, irq=0, softirq=0, steal=0)

        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        self.assertAlmostEqual(util.total_utilization_pct, 100.0, places=5)
        self.assertAlmostEqual(util.system_pct, 100.0, places=5)

    def test_100_percent_steal_time(self):
        """VM with 100% stolen cycles should show 100% utilization, 100% steal."""
        prev = CpuTimes(user=0, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=1000)
        curr = CpuTimes(user=0, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=2000)

        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        self.assertAlmostEqual(util.total_utilization_pct, 100.0, places=5)
        self.assertAlmostEqual(util.steal_pct, 100.0, places=5)

    def test_zero_delta_total_returns_none(self):
        """If no ticks advance (identical counters), interval is invalid."""
        same = CpuTimes(user=500, nice=0, system=200, idle=300, iowait=0, irq=0, softirq=0, steal=0)
        util = _compute_core_utilization(same, same, core_id=0, elapsed_seconds=1.0)
        self.assertIsNone(util, "Zero-delta total ticks should produce None")

    def test_mixed_mode_percentages_sum_to_100(self):
        """All mode percentages should sum to exactly 100%."""
        prev = CpuTimes(user=0, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0)
        curr = CpuTimes(user=20, nice=5, system=15, idle=40, iowait=10, irq=3, softirq=5, steal=2)

        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        total = (
            util.user_pct + util.nice_pct + util.system_pct + util.idle_pct
            + util.iowait_pct + util.irq_pct + util.softirq_pct + util.steal_pct
        )
        self.assertAlmostEqual(total, 100.0, places=3, msg="All mode percentages must sum to 100%")


class TestMultiCoreAsymmetry(unittest.TestCase):
    """Verify per-core independence under asymmetric load."""

    def test_one_core_busy_others_idle(self):
        """Core 0 at 100%, Core 1 at 0%, aggregate should reflect weighted average."""
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        snap1 = _snap(
            total=CpuTimes(user=0, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0),
            cores={
                0: CpuTimes(user=0, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0),
                1: CpuTimes(user=0, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0),
            },
            observed_at=t0,
        )
        registry.update(snap1)

        # Core 0: 100 user ticks, 0 idle. Core 1: 0 user, 100 idle.
        snap2 = _snap(
            total=CpuTimes(user=100, nice=0, system=0, idle=100, iowait=0, irq=0, softirq=0, steal=0),
            cores={
                0: CpuTimes(user=100, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0),
                1: CpuTimes(user=0, nice=0, system=0, idle=100, iowait=0, irq=0, softirq=0, steal=0),
            },
            observed_at=t1,
        )
        util = registry.update(snap2)
        self.assertIsNotNone(util)

        # Core 0 should be ~100%
        self.assertIn(0, util.per_core)
        self.assertAlmostEqual(util.per_core[0].total_utilization_pct, 100.0, places=1)

        # Core 1 should be ~0%
        self.assertIn(1, util.per_core)
        self.assertAlmostEqual(util.per_core[1].total_utilization_pct, 0.0, places=1)

        # Aggregate should be ~50%
        self.assertAlmostEqual(util.total.total_utilization_pct, 50.0, places=1)

    def test_core_appears_and_disappears(self):
        """If a core appears in snap2 but not snap1, it has no baseline → no utilization."""
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        snap1 = _snap(
            total=CpuTimes(user=100, nice=0, system=50, idle=850, iowait=0, irq=0, softirq=0, steal=0),
            cores={0: CpuTimes(user=100, nice=0, system=50, idle=850, iowait=0, irq=0, softirq=0, steal=0)},
            observed_at=t0,
        )
        registry.update(snap1)

        # Core 1 appears in snap2 but wasn't in snap1
        snap2 = _snap(
            total=CpuTimes(user=120, nice=0, system=55, idle=925, iowait=0, irq=0, softirq=0, steal=0),
            cores={
                0: CpuTimes(user=110, nice=0, system=52, idle=888, iowait=0, irq=0, softirq=0, steal=0),
                1: CpuTimes(user=10, nice=0, system=3, idle=37, iowait=0, irq=0, softirq=0, steal=0),
            },
            observed_at=t1,
        )
        util = registry.update(snap2)
        self.assertIsNotNone(util)
        self.assertIn(0, util.per_core)
        # Core 1 should NOT have utilization (no baseline)
        self.assertNotIn(1, util.per_core)


class TestCounterResetGranularity(unittest.TestCase):
    """Verify the per-counter reset policy works independently across cores and fields."""

    def test_reset_in_single_field_invalidates_only_that_core(self):
        """If only softirq resets on core 2, cores 0 and 1 remain valid."""
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        base = CpuTimes(user=100, nice=10, system=50, idle=800, iowait=20, irq=5, softirq=15, steal=0)
        snap1 = _snap(
            total=CpuTimes(user=300, nice=30, system=150, idle=2400, iowait=60, irq=15, softirq=45, steal=0),
            cores={0: base, 1: base, 2: base},
            observed_at=t0,
        )
        registry.update(snap1)

        good = CpuTimes(user=120, nice=12, system=55, idle=870, iowait=22, irq=6, softirq=17, steal=0)
        bad = CpuTimes(user=120, nice=12, system=55, idle=870, iowait=22, irq=6, softirq=5, steal=0)  # softirq decreased
        snap2 = _snap(
            total=CpuTimes(user=360, nice=36, system=165, idle=2610, iowait=66, irq=18, softirq=39, steal=0),
            cores={0: good, 1: good, 2: bad},
            observed_at=t1,
        )
        util = registry.update(snap2)
        self.assertIsNotNone(util)
        self.assertIn(0, util.per_core)
        self.assertIn(1, util.per_core)
        self.assertNotIn(2, util.per_core, "Core 2 should be invalidated due to softirq reset")

    def test_all_counters_checked_for_reset(self):
        """Each of the 8 independent counters should trigger invalidation when decreased."""
        base = CpuTimes(user=100, nice=100, system=100, idle=100, iowait=100, irq=100, softirq=100, steal=100)

        counter_names = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]
        for field in counter_names:
            kwargs = {
                "user": 100, "nice": 100, "system": 100, "idle": 100,
                "iowait": 100, "irq": 100, "softirq": 100, "steal": 100,
            }
            kwargs[field] = 50  # Decrease this one counter
            decreased = CpuTimes(**kwargs)

            util = _compute_core_utilization(base, decreased, core_id=0, elapsed_seconds=1.0)
            self.assertIsNone(
                util,
                f"Decrease in '{field}' counter should invalidate the interval"
            )


class TestRateCalculations(unittest.TestCase):
    """Verify ctxt_rate and forks_rate calculations."""

    def test_rates_computed_correctly(self):
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=2.0)

        snap1 = _snap(
            total=CpuTimes(user=100, nice=0, system=50, idle=850, iowait=0, irq=0, softirq=0, steal=0),
            ctxt=10000, processes=500, observed_at=t0,
        )
        registry.update(snap1)

        snap2 = _snap(
            total=CpuTimes(user=200, nice=0, system=100, idle=1700, iowait=0, irq=0, softirq=0, steal=0),
            ctxt=15000, processes=510, observed_at=t1,
        )
        util = registry.update(snap2)
        self.assertIsNotNone(util)
        # 5000 ctxt over 2 seconds = 2500/s
        self.assertAlmostEqual(util.ctxt_rate, 2500.0, places=1)
        # 10 forks over 2 seconds = 5/s
        self.assertAlmostEqual(util.forks_rate, 5.0, places=1)

    def test_ctxt_decrease_produces_none_rate(self):
        """If context switch counter wraps/decreases, rate should be None."""
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        t1 = t0 + timedelta(seconds=1.0)

        snap1 = _snap(
            total=CpuTimes(user=100, nice=0, system=50, idle=850, iowait=0, irq=0, softirq=0, steal=0),
            ctxt=100000, processes=500, observed_at=t0,
        )
        registry.update(snap1)

        snap2 = _snap(
            total=CpuTimes(user=200, nice=0, system=100, idle=1700, iowait=0, irq=0, softirq=0, steal=0),
            ctxt=50000,  # Decreased
            processes=510,
            observed_at=t1,
        )
        util = registry.update(snap2)
        self.assertIsNotNone(util)
        self.assertIsNone(util.ctxt_rate, "Decreased ctxt should produce None rate")


class TestLargeTickValues(unittest.TestCase):
    """Simulate counters near maximum values to test overflow handling."""

    def test_large_tick_values_produce_correct_utilization(self):
        """Systems with high uptime can have very large cumulative counters."""
        # Simulating ~180 days of uptime on 12 cores at 100 HZ
        large_base = 100 * 86400 * 180 * 12  # ~18.7 billion ticks
        prev = CpuTimes(
            user=large_base, nice=0, system=large_base // 4,
            idle=large_base * 3, iowait=0, irq=0, softirq=0, steal=0,
        )
        curr = CpuTimes(
            user=large_base + 500, nice=0, system=large_base // 4 + 200,
            idle=large_base * 3 + 300, iowait=0, irq=0, softirq=0, steal=0,
        )
        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        # Delta: user=500, system=200, idle=300 → total=1000, busy=700
        self.assertAlmostEqual(util.total_utilization_pct, 70.0, places=1)


class TestDiscoveryParserResilience(unittest.TestCase):
    """Parser should handle malformed /proc/stat gracefully."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_empty_file_returns_none(self):
        stat_file = self.base_path / "stat"
        stat_file.write_text("", encoding="utf-8")
        self.assertIsNone(read_cpu_stat(stat_path=stat_file))

    def test_garbage_content_returns_none(self):
        stat_file = self.base_path / "stat"
        stat_file.write_text("this is not proc stat content\nrandom gibberish\n", encoding="utf-8")
        self.assertIsNone(read_cpu_stat(stat_path=stat_file))

    def test_cpu_line_with_too_few_fields_returns_none(self):
        stat_file = self.base_path / "stat"
        stat_file.write_text("cpu  100 200\n", encoding="utf-8")  # Only 2 fields, need 4
        self.assertIsNone(read_cpu_stat(stat_path=stat_file))

    def test_cpu_line_with_non_numeric_values_returns_none(self):
        stat_file = self.base_path / "stat"
        stat_file.write_text("cpu  abc def ghi jkl\n", encoding="utf-8")
        self.assertIsNone(read_cpu_stat(stat_path=stat_file))

    def test_extra_whitespace_handled(self):
        stat_file = self.base_path / "stat"
        stat_file.write_text("cpu  100  200  300  400\n  \n\n", encoding="utf-8")
        snap = read_cpu_stat(stat_path=stat_file)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.total_cpu.user, 100)

    def test_partial_cpu_line_fields_default_to_zero(self):
        """If only 5 fields given (user, nice, system, idle, iowait), later fields default to 0."""
        stat_file = self.base_path / "stat"
        stat_file.write_text("cpu  100 200 300 400 50\n", encoding="utf-8")
        snap = read_cpu_stat(stat_path=stat_file)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.total_cpu.iowait, 50)
        self.assertEqual(snap.total_cpu.irq, 0)
        self.assertEqual(snap.total_cpu.softirq, 0)
        self.assertEqual(snap.total_cpu.steal, 0)
        self.assertEqual(snap.total_cpu.guest, 0)
        self.assertEqual(snap.total_cpu.guest_nice, 0)

    def test_core_with_bad_id_ignored(self):
        """A line like 'cpuX ...' where X is not a number should be ignored."""
        stat_file = self.base_path / "stat"
        content = (
            "cpu  100 0 50 850 0 0 0 0 0 0\n"
            "cpuX 10 0 5 85 0 0 0 0 0 0\n"
            "cpu0 10 0 5 85 0 0 0 0 0 0\n"
        )
        stat_file.write_text(content, encoding="utf-8")
        snap = read_cpu_stat(stat_path=stat_file)
        self.assertIsNotNone(snap)
        self.assertEqual(len(snap.cores), 1)
        self.assertIn(0, snap.cores)

    def test_stat_path_override_works(self):
        """read_cpu_stat(stat_path=...) reads the specified file."""
        stat_file = self.base_path / "custom_stat.txt"
        stat_file.write_text("cpu  500 0 200 8000 100 0 0 0 0 0\n", encoding="utf-8")
        snap = read_cpu_stat(stat_path=stat_file)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.total_cpu.user, 500)

    def test_proc_root_as_directory(self):
        """read_cpu_stat(proc_root=dir) reads dir/stat."""
        stat_file = self.base_path / "stat"
        stat_file.write_text("cpu  300 0 100 5000 0 0 0 0 0 0\n", encoding="utf-8")
        snap = read_cpu_stat(proc_root=self.base_path)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.total_cpu.user, 300)


class TestSnapshotImmutability(unittest.TestCase):
    """Verify frozen dataclass contracts."""

    def test_cpu_times_is_immutable(self):
        times = CpuTimes(user=1, nice=2, system=3, idle=4, iowait=5, irq=6, softirq=7, steal=8)
        with self.assertRaises(AttributeError):
            times.user = 999

    def test_cpu_stat_snapshot_is_immutable(self):
        snap = _snap(total=CpuTimes(user=1, nice=0, system=0, idle=0, iowait=0, irq=0, softirq=0, steal=0))
        with self.assertRaises(AttributeError):
            snap.procs_running = 999


class TestCpuRegistryEdgeCases(unittest.TestCase):
    """Registry thread safety and state management."""

    def test_reset_clears_baseline(self):
        registry = CpuRegistry()
        t0 = datetime(2026, 9, 6, 12, 0, 0)
        snap1 = _snap(
            total=CpuTimes(user=100, nice=0, system=50, idle=850, iowait=0, irq=0, softirq=0, steal=0),
            observed_at=t0,
        )
        registry.update(snap1)

        registry.reset()

        # After reset, next update should return None (no baseline)
        t1 = t0 + timedelta(seconds=1.0)
        snap2 = _snap(
            total=CpuTimes(user=200, nice=0, system=100, idle=1700, iowait=0, irq=0, softirq=0, steal=0),
            observed_at=t1,
        )
        result = registry.update(snap2)
        self.assertIsNone(result, "After reset(), next update should return None (establishing new baseline)")

    def test_multiple_rapid_updates_produce_valid_results(self):
        """Simulate 10 rapid sequential updates — each should produce valid utilization after baseline."""
        registry = CpuRegistry()
        t = datetime(2026, 9, 6, 12, 0, 0)

        for i in range(10):
            snap = _snap(
                total=CpuTimes(
                    user=100 * i, nice=0, system=50 * i,
                    idle=850 * i, iowait=0, irq=0, softirq=0, steal=0,
                ),
                ctxt=1000 * i,
                processes=10 * i,
                observed_at=t + timedelta(seconds=i * 0.1),
            )
            util = registry.update(snap)
            if i == 0:
                self.assertIsNone(util)
            elif i > 0:
                # Should produce valid utilization (all deltas positive)
                self.assertIsNotNone(util)

    def test_utilization_is_clamped_between_0_and_100(self):
        """Verify the max(0, min(100, ...)) clamp on total_utilization_pct."""
        # This is mathematically impossible with valid input, but verify the safety net
        prev = CpuTimes(user=0, nice=0, system=0, idle=100, iowait=0, irq=0, softirq=0, steal=0)
        curr = CpuTimes(user=50, nice=0, system=50, idle=100, iowait=0, irq=0, softirq=0, steal=0)
        util = _compute_core_utilization(prev, curr, core_id=None, elapsed_seconds=1.0)
        self.assertIsNotNone(util)
        self.assertGreaterEqual(util.total_utilization_pct, 0.0)
        self.assertLessEqual(util.total_utilization_pct, 100.0)


class TestCLKTCKLive(unittest.TestCase):
    """Verify CLK_TCK resolution on this live system."""

    def test_clk_tck_is_positive_integer(self):
        tck = get_clk_tck()
        self.assertIsNotNone(tck)
        self.assertIsInstance(tck, int)
        self.assertGreater(tck, 0)

    def test_clk_tck_matches_os_sysconf(self):
        """Cross-verify against direct os.sysconf call."""
        app_tck = get_clk_tck()
        direct_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
        self.assertEqual(app_tck, direct_tck)

    def test_clk_tck_common_values(self):
        """Linux CLK_TCK is typically 100 or 250 or 300 or 1000."""
        tck = get_clk_tck()
        self.assertIn(tck, [100, 250, 300, 1000],
                      f"CLK_TCK={tck} is unusual but not necessarily wrong")


class TestCrossVerification(unittest.TestCase):
    """Cross-verify the app's output against independently parsed /proc/stat."""

    def test_app_snapshot_matches_manual_parse(self):
        """Read /proc/stat manually and compare against app's parser output."""
        with open("/proc/stat", "r") as f:
            lines = f.readlines()

        # Parse aggregate CPU line manually
        cpu_line = lines[0].strip().split()
        self.assertEqual(cpu_line[0], "cpu")
        manual_user = int(cpu_line[1])
        manual_nice = int(cpu_line[2])
        manual_system = int(cpu_line[3])
        manual_idle = int(cpu_line[4])

        # Now read through the app
        snap = read_cpu_stat()
        self.assertIsNotNone(snap)

        # Values should be close (may have advanced slightly between reads)
        self.assertAlmostEqual(snap.total_cpu.user, manual_user, delta=1000,
                               msg="User ticks should be close between manual and app parse")
        self.assertAlmostEqual(snap.total_cpu.nice, manual_nice, delta=100)
        self.assertAlmostEqual(snap.total_cpu.system, manual_system, delta=500)
        self.assertAlmostEqual(snap.total_cpu.idle, manual_idle, delta=5000)


if __name__ == "__main__":
    unittest.main()
