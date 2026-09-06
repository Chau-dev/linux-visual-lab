from __future__ import annotations

import unittest
from app.memory.model import MemorySnapshot, SystemLoadSnapshot
from app.memory.registry import MemoryRegistry, diff_memory_snapshots


class TestMemoryRegistry(unittest.TestCase):
    def test_no_event_when_memory_state_has_not_changed(self):
        prev = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=4000,
            mem_available_kb=10000,
            buffers_kb=1000,
            cached_kb=3000,
            swap_total_kb=4000,
            swap_free_kb=2000,  # swap_used = 2000
        )
        curr = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=3500,  # MemFree changed
            mem_available_kb=9500,  # MemAvailable changed
            buffers_kb=1000,
            cached_kb=3500,  # Cached changed
            swap_total_kb=4000,
            swap_free_kb=2000,  # swap_used unchanged (2000)
        )

        # Normal 1s RAM fluctuations do NOT generate noisy timeline events
        events = diff_memory_snapshots(prev, curr)
        self.assertEqual(len(events), 0)

    def test_swap_usage_changed_emits_factual_event_with_provenance(self):
        prev = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=4000,
            mem_available_kb=10000,
            buffers_kb=1000,
            cached_kb=3000,
            swap_total_kb=4000,
            swap_free_kb=3000,  # swap_used = 1000
        )
        curr = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=3800,
            mem_available_kb=9800,
            buffers_kb=1000,
            cached_kb=3200,
            swap_total_kb=4000,
            swap_free_kb=1500,  # swap_used = 2500
        )

        events = diff_memory_snapshots(prev, curr)
        self.assertEqual(len(events), 1)

        ev = events[0]
        self.assertEqual(ev.event_type, "memory.swap_usage_changed")
        self.assertEqual(ev.source, "Linux /proc/meminfo snapshot")
        self.assertEqual(ev.data.get("old_swap_used_kb"), 1000)
        self.assertEqual(ev.data.get("new_swap_used_kb"), 2500)
        self.assertEqual(ev.data.get("delta_swap_used_kb"), 1500)
        self.assertEqual(ev.data.get("swap_total_kb"), 4000)
        self.assertEqual(ev.data.get("mechanism"), "/proc/meminfo")
        # Ensure no speculative cause is asserted in data
        self.assertNotIn("cause", ev.data)
        self.assertNotIn("reason", ev.data)

    def test_memory_registry_update(self):
        reg = MemoryRegistry()
        self.assertIsNone(reg.get_latest_memory())
        self.assertIsNone(reg.get_latest_load())

        snap1 = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=4000,
            mem_available_kb=10000,
            buffers_kb=1000,
            cached_kb=3000,
            swap_total_kb=4000,
            swap_free_kb=3000,
        )
        load1 = SystemLoadSnapshot(
            load_1m=0.1,
            load_5m=0.2,
            load_15m=0.3,
            runnable_entities=1,
            total_entities=100,
            last_pid=500,
            uptime_seconds=100.0,
            idle_seconds=200.0,
        )

        events1 = reg.update(snap1, load1)
        self.assertEqual(len(events1), 0)  # first snapshot: baseline, no diff
        self.assertEqual(reg.get_latest_memory(), snap1)
        self.assertEqual(reg.get_latest_load(), load1)

        # Second snapshot with swap change
        snap2 = MemorySnapshot(
            mem_total_kb=16000,
            mem_free_kb=4000,
            mem_available_kb=10000,
            buffers_kb=1000,
            cached_kb=3000,
            swap_total_kb=4000,
            swap_free_kb=1000,  # swap_used = 3000
        )
        events2 = reg.update(snap2, load1)
        self.assertEqual(len(events2), 1)
        self.assertEqual(events2[0].event_type, "memory.swap_usage_changed")
        self.assertEqual(reg.get_latest_memory(), snap2)


if __name__ == "__main__":
    unittest.main()
