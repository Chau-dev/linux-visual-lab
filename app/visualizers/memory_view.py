from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QProgressBar,
    QScrollArea,
    QGridLayout,
    QGroupBox,
)

from app.memory.model import MemorySnapshot, SystemLoadSnapshot, format_kb


class MetricCard(QFrame):
    """Clean factual metric display card."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            """
            MetricCard {
                background-color: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 6px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        layout.addWidget(self.title_lbl)

        self.value_lbl = QLabel("Awaiting sampling...")
        self.value_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #f8fafc; font-family: monospace;")
        layout.addWidget(self.value_lbl)

        self.sub_lbl = QLabel(subtitle if subtitle else "—")
        self.sub_lbl.setStyleSheet("font-size: 10px; color: #64748b;")
        layout.addWidget(self.sub_lbl)

    def set_value(self, text: str, subtext: str | None = None):
        self.value_lbl.setText(text)
        if subtext is not None:
            self.sub_lbl.setText(subtext)


class MemoryLabWidget(QWidget):
    """
    Rich, educational Linux Memory & System Load Lab.

    Features:
      - Selected Memory Metrics Visualization (raw indicators compared to MemTotal)
      - Explicit Derived Sums (Buffers + Cached + KReclaimable, Used approximation)
      - Swap Space Breakdown (SwapTotal, SwapFree, SwapUsed, SwapCached)
      - Full Raw Linux /proc/meminfo Metrics Grid
      - System Load Averages (1m, 5m, 15m) & Runnable / Total Threads & Uptime
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Scroll Area for entire content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # ========================================================
        # 1. TOP BANNER: System Load & Uptime
        # ========================================================
        load_group = QGroupBox("⚡ SYSTEM LOAD & UPTIME (from /proc/loadavg & /proc/uptime)")
        load_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            """
        )
        load_layout = QHBoxLayout(load_group)
        load_layout.setSpacing(8)

        self.card_load1 = MetricCard("LOAD (1m)", "Active runnable tasks")
        self.card_load5 = MetricCard("LOAD (5m)", "5-min trend")
        self.card_load15 = MetricCard("LOAD (15m)", "15-min trend")
        self.card_threads = MetricCard("RUNNABLE / TOTAL", "from /proc/loadavg")
        self.card_uptime = MetricCard("SYSTEM UPTIME", "from /proc/uptime")

        load_layout.addWidget(self.card_load1)
        load_layout.addWidget(self.card_load5)
        load_layout.addWidget(self.card_load15)
        load_layout.addWidget(self.card_threads)
        load_layout.addWidget(self.card_uptime)

        content_layout.addWidget(load_group)

        # ========================================================
        # 2. SELECTED MEMORY METRICS VISUALIZATION
        # ========================================================
        metrics_group = QGroupBox("🧠 SELECTED MEMORY METRICS (Not a mathematical partition of total RAM)")
        metrics_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: #a855f7;
                border: 1px solid rgba(168, 85, 247, 0.2);
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            """
        )
        metrics_layout = QVBoxLayout(metrics_group)
        metrics_layout.setSpacing(8)

        # Summary Row (Key indicators)
        summary_row = QHBoxLayout()
        summary_row.setSpacing(8)

        self.card_total = MetricCard("MemTotal", "Total physical RAM")
        self.card_avail = MetricCard("MemAvailable", "Estimated for new apps")
        self.card_free = MetricCard("MemFree", "Unallocated pages")
        self.card_anon = MetricCard("Active(anon)", "Active anonymous pages")
        self.card_cache_sum = MetricCard("Derived sum", "Buffers + Cached + KReclaimable")

        summary_row.addWidget(self.card_total)
        summary_row.addWidget(self.card_avail)
        summary_row.addWidget(self.card_free)
        summary_row.addWidget(self.card_anon)
        summary_row.addWidget(self.card_cache_sum)

        metrics_layout.addLayout(summary_row)

        # Visual Relative Progress Bars
        bars_frame = QFrame()
        bars_frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                padding: 8px;
            }
            """
        )
        bars_layout = QVBoxLayout(bars_frame)
        bars_layout.setSpacing(6)

        self.bar_avail = self._create_metric_bar(bars_layout, "MemAvailable (% of MemTotal):", "#2ecc71")
        self.bar_free = self._create_metric_bar(bars_layout, "MemFree (% of MemTotal):", "#3498db")
        self.bar_used_approx = self._create_metric_bar(bars_layout, "Derived: Used approx (% of MemTotal):", "#f39c12")

        metrics_layout.addWidget(bars_frame)
        content_layout.addWidget(metrics_group)

        # ========================================================
        # 3. SWAP SPACE METRICS
        # ========================================================
        swap_group = QGroupBox("🔄 SWAP SPACE (from /proc/meminfo)")
        swap_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: #eab308;
                border: 1px solid rgba(234, 179, 8, 0.2);
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            """
        )
        swap_layout = QVBoxLayout(swap_group)
        swap_layout.setSpacing(6)

        swap_cards_row = QHBoxLayout()
        swap_cards_row.setSpacing(8)

        self.card_swap_total = MetricCard("SwapTotal", "Configured swap")
        self.card_swap_free = MetricCard("SwapFree", "Unallocated swap")
        self.card_swap_used = MetricCard("Derived: SwapUsed", "SwapTotal - SwapFree")
        self.card_swap_cached = MetricCard("SwapCached", "In swap & memory")

        swap_cards_row.addWidget(self.card_swap_total)
        swap_cards_row.addWidget(self.card_swap_free)
        swap_cards_row.addWidget(self.card_swap_used)
        swap_cards_row.addWidget(self.card_swap_cached)

        swap_layout.addLayout(swap_cards_row)

        self.bar_swap = self._create_metric_bar(swap_layout, "Swap Utilization (% of SwapTotal):", "#e74c3c")

        content_layout.addWidget(swap_group)

        # ========================================================
        # 4. FULL RAW LINUX /proc/meminfo METRICS GRID
        # ========================================================
        raw_group = QGroupBox("📋 RAW LINUX /proc/meminfo FIELDS")
        raw_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            """
        )
        raw_layout = QGridLayout(raw_group)
        raw_layout.setSpacing(6)

        self.raw_cards: dict[str, MetricCard] = {}
        raw_fields = [
            ("Buffers", "Raw buffer cache"),
            ("Cached", "Page cache in RAM"),
            ("Active(anon)", "Active anonymous pages"),
            ("Inactive(anon)", "Inactive anonymous pages"),
            ("Active(file)", "Active file-backed pages"),
            ("Inactive(file)", "Inactive file-backed pages"),
            ("Dirty", "Memory waiting write to disk"),
            ("Writeback", "Memory actively writing"),
            ("AnonPages", "Non-file backed pages"),
            ("Mapped", "Files mapped into memory"),
            ("Shmem", "Shared memory (tmpfs)"),
            ("Slab", "Kernel in-memory cache"),
            ("KReclaimable", "Kernel reclaimable slab"),
            ("Mlocked", "Pages locked in memory"),
        ]

        row = 0
        col = 0
        for field_name, desc in raw_fields:
            card = MetricCard(field_name, desc)
            self.raw_cards[field_name] = card
            raw_layout.addWidget(card, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        content_layout.addWidget(raw_group)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Convenient inspector references
        self.lbl_hero_total = self.card_total.value_lbl
        self.lbl_hero_avail = self.card_avail.value_lbl
        self.lbl_load_1m = self.card_load1.value_lbl
        self.lbl_load_5m = self.card_load5.value_lbl
        self.lbl_load_15m = self.card_load15.value_lbl
        self.lbl_entities = self.card_threads.value_lbl
        self.lbl_last_pid = self.card_threads.sub_lbl
        self.lbl_uptime = self.card_uptime.value_lbl

    @property
    def raw_labels(self) -> dict[str, QLabel]:
        """Provides easy dictionary access to raw labels for introspection & tests."""
        labels = {
            "MemTotal": self.card_total.sub_lbl,
            "MemAvailable": self.card_avail.sub_lbl,
            "MemFree": self.card_free.sub_lbl,
        }
        for name, card in self.raw_cards.items():
            labels[name] = card.sub_lbl
        return labels

    def _create_metric_bar(self, parent_layout: QVBoxLayout, label_text: str, color_hex: str) -> tuple[QLabel, QProgressBar]:
        row = QHBoxLayout()
        row.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 11px; color: #cbd5e1; min-width: 250px;")
        row.addWidget(lbl)

        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        pbar.setTextVisible(True)
        pbar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                height: 16px;
                text-align: center;
                font-size: 10px;
                font-weight: bold;
                color: #ffffff;
            }}
            QProgressBar::chunk {{
                background-color: {color_hex};
                border-radius: 3px;
            }}
            """
        )
        row.addWidget(pbar, 1)

        parent_layout.addLayout(row)
        return (lbl, pbar)

    def update_memory(self, memory: MemorySnapshot | None, load: SystemLoadSnapshot | None):
        """Update all memory and load indicators with fresh point-in-time snapshots."""
        if load is not None:
            self.card_load1.set_value(f"{load.load_1m:.2f}")
            self.card_load5.set_value(f"{load.load_5m:.2f}")
            self.card_load15.set_value(f"{load.load_15m:.2f}")
            self.card_threads.set_value(f"{load.runnable_entities} / {load.total_entities}", f"Last PID: {load.last_pid}")
            self.card_uptime.set_value(load.derived_formatted_uptime, f"Idle: {int(load.idle_seconds)}s")

        if memory is not None:
            # 1. Summary Cards
            self.card_total.set_value(format_kb(memory.mem_total_kb), f"{memory.mem_total_kb} kB")
            self.card_avail.set_value(format_kb(memory.mem_available_kb), f"{memory.mem_available_kb} kB")
            self.card_free.set_value(format_kb(memory.mem_free_kb), f"{memory.mem_free_kb} kB")
            self.card_anon.set_value(format_kb(memory.active_anon_kb), f"{memory.active_anon_kb or 0} kB")
            
            cache_sum = memory.derived_buffers_cached_kreclaimable_kb
            self.card_cache_sum.set_value(format_kb(cache_sum), f"{cache_sum} kB")

            # 2. Relative Bars
            avail_pct = int(memory.derived_available_percent)
            self.bar_avail[1].setValue(avail_pct)
            self.bar_avail[1].setFormat(f"{format_kb(memory.mem_available_kb)} ({avail_pct}%)")

            free_pct = int(memory.derived_free_percent)
            self.bar_free[1].setValue(free_pct)
            self.bar_free[1].setFormat(f"{format_kb(memory.mem_free_kb)} ({free_pct}%)")

            used_pct = int(memory.derived_used_percent)
            self.bar_used_approx[1].setValue(used_pct)
            self.bar_used_approx[1].setFormat(f"{format_kb(memory.derived_used_approx_kb)} ({used_pct}%)")

            # 3. Swap Cards & Bar
            self.card_swap_total.set_value(format_kb(memory.swap_total_kb), f"{memory.swap_total_kb} kB")
            self.card_swap_free.set_value(format_kb(memory.swap_free_kb), f"{memory.swap_free_kb} kB")
            self.card_swap_used.set_value(format_kb(memory.derived_swap_used_kb), f"{memory.derived_swap_used_percent:.1f}%")
            self.card_swap_cached.set_value(format_kb(memory.swap_cached_kb), f"{memory.swap_cached_kb or 0} kB")

            swap_pct = int(memory.derived_swap_used_percent)
            self.bar_swap[1].setValue(swap_pct)
            self.bar_swap[1].setFormat(f"{format_kb(memory.derived_swap_used_kb)} / {format_kb(memory.swap_total_kb)} ({swap_pct}%)")

            # 4. Raw /proc/meminfo Grid
            field_map = {
                "Buffers": memory.buffers_kb,
                "Cached": memory.cached_kb,
                "Active(anon)": memory.active_anon_kb,
                "Inactive(anon)": memory.inactive_anon_kb,
                "Active(file)": memory.active_file_kb,
                "Inactive(file)": memory.inactive_file_kb,
                "Dirty": memory.dirty_kb,
                "Writeback": memory.writeback_kb,
                "AnonPages": memory.anon_pages_kb,
                "Mapped": memory.mapped_kb,
                "Shmem": memory.shmem_kb,
                "Slab": memory.slab_kb,
                "KReclaimable": memory.kreclaimable_kb,
                "Mlocked": memory.mlocked_kb,
            }

            for name, val in field_map.items():
                if name in self.raw_cards:
                    if val is not None:
                        self.raw_cards[name].set_value(format_kb(val), f"{val} kB")
                    else:
                        self.raw_cards[name].set_value("N/A (omitted)", "Kernel omitted")
