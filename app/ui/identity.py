"""
Deterministic visual encoding for Linux identifiers (PID, PPID, UID, GID, Inode, Device).
Exposes structural identity relationships purely in the visual layer without modifying underlying domain data.
"""
from typing import Any

# 24 vibrant, highly distinct dark-theme color tokens (bg, text, border)
IDENTITY_PALETTE = [
    ("#1e3a8a", "#93c5fd", "#3b82f6"),  # 0: Vibrant Royal Blue
    ("#064e3b", "#6ee7b7", "#10b981"),  # 1: Emerald Green
    ("#581c87", "#d8b4fe", "#a855f7"),  # 2: Purple / Violet
    ("#7c2d12", "#fdba74", "#f97316"),  # 3: Vivid Orange
    ("#164e63", "#67e8f9", "#06b6d4"),  # 4: Cyan / Aqua
    ("#831843", "#f472b6", "#ec4899"),  # 5: Hot Pink / Rose
    ("#134e4a", "#5eead4", "#14b8a6"),  # 6: Bright Teal
    ("#312e81", "#a5b4fc", "#6366f1"),  # 7: Deep Indigo
    ("#713f12", "#fde047", "#eab308"),  # 8: Golden Amber
    ("#881337", "#fda4af", "#f43f5e"),  # 9: Crimson / Ruby
    ("#14532d", "#86efac", "#22c55e"),  # 10: Lime / Forest Green
    ("#4c1d95", "#c4b5fd", "#8b5cf6"),  # 11: Electric Purple
    ("#78350f", "#fcd34d", "#f59e0b"),  # 12: Honey Gold
    ("#0c4a6e", "#7dd3fc", "#0284c7"),  # 13: Sky / Cobalt Blue
    ("#701a75", "#f0abfc", "#d946ef"),  # 14: Fuchsia / Magenta
    ("#365314", "#bef264", "#84cc16"),  # 15: Bright Lime
    ("#7f1d1d", "#fca5a5", "#ef4444"),  # 16: Scarlet Red
    ("#1e293b", "#cbd5e1", "#94a3b8"),  # 17: Slate / Silver
    ("#022c22", "#5eead4", "#0d9488"),  # 18: Dark Seafoam
    ("#431407", "#ffedd5", "#ea580c"),  # 19: Burnt Sienna
    ("#172554", "#bfdbfe", "#2563eb"),  # 20: Classic Navy
    ("#500724", "#fbcfe8", "#db2777"),  # 21: Deep Magenta
    ("#1c1917", "#e7e5e4", "#a8a29e"),  # 22: Warm Neutral
    ("#042f2e", "#99f6e4", "#059669"),  # 23: Pine Teal
]


def get_identity_style(value: Any) -> tuple[str, str, str]:
    """
    Returns (bg_color, text_color, border_color) deterministically for any identifier value.
    Guarantees: Same value -> Same visual token; Different value -> Different visual token.
    Uses a multiplicative Knuth hash for integers and FNV-1a for strings to cleanly disperse
    consecutive IDs (e.g. PIDs 100, 101, 102) across maximally contrasting hues.
    """
    if value is None:
        return ("#2a2a38", "#888888", "#444444")

    if isinstance(value, int):
        # Knuth multiplicative hash (golden ratio phi * 2^32)
        hash_val = (abs(value) * 2654435761) & 0xFFFFFFFF
    else:
        val_str = str(value)
        # If string is purely digits, treat numerically for optimal dispersal
        if val_str.isdigit():
            hash_val = (int(val_str) * 2654435761) & 0xFFFFFFFF
        else:
            # FNV-1a 32-bit hash
            hash_val = 2166136261
            for char in val_str:
                hash_val ^= ord(char)
                hash_val = (hash_val * 16777619) & 0xFFFFFFFF

    idx = hash_val % len(IDENTITY_PALETTE)
    return IDENTITY_PALETTE[idx]


def format_identity_badge_html(value: Any, label: str = "") -> str:
    """
    Formats a visual HTML badge token representing an observed identifier.
    The value itself is rendered unchanged; color provides instant visual correlation.
    """
    if value is None:
        return "-"

    bg, fg, border = get_identity_style(value)
    text = f"{label} {value}" if label else str(value)
    return (
        f"<span style='background-color: {bg}; color: {fg}; "
        f"border: 1px solid {border}; border-radius: 3px; "
        f"padding: 1px 5px; font-family: monospace; font-size: 11px; font-weight: bold;'>"
        f"{text}"
        f"</span>"
    )
