from __future__ import annotations

import os


def get_clk_tck(override_clk_tck: int | None = None) -> int | None:
    """
    Dynamically resolve the system clock tick rate (USER_HZ) at runtime.

    On Linux, this corresponds to sysconf(_SC_CLK_TCK).
    Returns a strictly positive integer if resolved, or None if the
    runtime environment does not report a valid CLK_TCK.

    Args:
        override_clk_tck: Optional explicit clock tick value for controlled testing.
    """
    if override_clk_tck is not None:
        return override_clk_tck if override_clk_tck > 0 else None

    try:
        if hasattr(os, "sysconf_names") and "SC_CLK_TCK" in os.sysconf_names:
            tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
            if isinstance(tck, int) and tck > 0:
                return tck
        elif hasattr(os, "sysconf"):
            tck = os.sysconf("SC_CLK_TCK")
            if isinstance(tck, int) and tck > 0:
                return tck
    except (ValueError, OSError, AttributeError):
        pass

    return None
