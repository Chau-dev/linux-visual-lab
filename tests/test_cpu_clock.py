from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.cpu.clock import get_clk_tck


class TestCpuClock(unittest.TestCase):
    def test_get_clk_tck_override_positive(self):
        self.assertEqual(get_clk_tck(override_clk_tck=100), 100)
        self.assertEqual(get_clk_tck(override_clk_tck=250), 250)

    def test_get_clk_tck_override_invalid(self):
        self.assertIsNone(get_clk_tck(override_clk_tck=0))
        self.assertIsNone(get_clk_tck(override_clk_tck=-100))

    def test_get_clk_tck_runtime(self):
        # On Linux, SC_CLK_TCK is typically 100
        tck = get_clk_tck()
        self.assertIsNotNone(tck)
        self.assertIsInstance(tck, int)
        self.assertGreater(tck, 0)

    def test_get_clk_tck_missing_returns_none(self):
        with patch.object(os, "sysconf", side_effect=ValueError("Unsupported")):
            with patch.object(os, "sysconf_names", {}):
                self.assertIsNone(get_clk_tck())
