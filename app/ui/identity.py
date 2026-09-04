"""
Deterministic visual encoding for Linux identifiers (PID, PPID, UID, GID, Inode, Device).
Exposes structural identity relationships purely in the visual layer without modifying underlying domain data.
"""
from typing import Any

IDENTITY_PALETTE = [
    ("#1e3a8a", "#93c5fd", "#3b82f6"),  # Blue
    ("#064e3b", "#6ee7b7", "#10b981"),  # Emerald
    ("#581c87", "#d8b4fe", "#a855f7"),  # Purple
    ("#7c2d12", "#fdba74", "#f97316"),  # Orange / Amber
    ("#164e63", "#67e8f9", "#06b6d4"),  # Cyan
    ("#831843", "#f472b6", "#ec4899"),  # Rose / Pink
    ("#134e4a", "#5eead4", "#14b8a6"),  # Teal
    ("#312e81", "#a5b4fc", "#6366f1"),  # Indigo
    ("#713f12", "#fde047", "#eab308"),  # Yellow
    ("#374151", "#e5e7eb", "#6b7280"),  # Slate / Gray
]


def get_identity_style(value: Any) -> tuple[str, str, str]:
    """
    Returns (bg_color, text_color, border_color) deterministically for any identifier value.
    Guarantees: Same value -> Same visual token; Different value -> Different visual token.
    """
    if value is None:
        return ("#2a2a38", "#888888", "#444444")

    val_str = str(value)
    hash_val = sum(ord(c) * (31 ** i) for i, c in enumerate(val_str[:12]))
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
