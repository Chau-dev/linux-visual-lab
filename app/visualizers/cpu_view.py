from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.cpu.model import CpuCoreUtilization, CpuStatSnapshot, CpuUtilization


class MetricCard(QFrame):
    """Clean factual metric display card matching the visual lab aesthetic."""

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

        self.value_lbl = QLabel("Awaiting baseline...")
        self.value_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #f8fafc; font-family: monospace;")
        layout.addWidget(self.value_lbl)

        self.sub_lbl = QLabel(subtitle if subtitle else "—")
        self.sub_lbl.setStyleSheet("font-size: 10px; color: #64748b;")
        self.sub_lbl.setWordWrap(True)
        layout.addWidget(self.sub_lbl)

    def set_value(self, text: str, subtext: str | None = None):
        self.value_lbl.setText(text)
        if subtext is not None:
            self.sub_lbl.setText(subtext)


class CoreMeterWidget(QFrame):
    """Mini utilization meter for an individual CPU core."""

    def __init__(self, core_id: int, parent=None):
        super().__init__(parent)
        self.core_id = core_id
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            """
            CoreMeterWidget {
                background-color: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                padding: 4px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        self.title_lbl = QLabel(f"CPU {core_id}")
        self.title_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        self.pct_lbl = QLabel("— %")
        self.pct_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #f8fafc; font-family: monospace;")
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()
        top_row.addWidget(self.pct_lbl)
        layout.addLayout(top_row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(
            """
            QProgressBar {
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 3px;
            }
            """
        )
        layout.addWidget(self.bar)

        self.caption_lbl = QLabel("Derived from /proc/stat deltas")
        self.caption_lbl.setStyleSheet("font-size: 9px; color: #64748b;")
        layout.addWidget(self.caption_lbl)

    def update_utilization(self, util: CpuCoreUtilization | None):
        if util is None:
            self.pct_lbl.setText("— %")
            self.bar.setValue(0)
            return

        pct = util.total_utilization_pct
        self.pct_lbl.setText(f"{pct:.1f}%")
        self.bar.setValue(int(pct * 10))

        # Dynamic color coding based on load
        if pct >= 85.0:
            color = "#ef4444"
        elif pct >= 60.0:
            color = "#f59e0b"
        else:
            color = "#38bdf8"

        self.bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: rgba(0, 0, 0, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
            """
        )


class CpuLabWidget(QWidget):
    """
    Rich, educational Linux CPU & Utilization Lab.

    Strict Truth & Education Separation:
      - Section 1: DERIVED CPU UTILIZATION (explicit mathematical calculations from /proc/stat deltas)
      - Section 2: RAW LINUX COUNTERS & SCHEDULER STATE (exact cumulative kernel ticks & /proc/stat state)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # ========================================================
        # 1. DERIVED CPU UTILIZATION
        # ========================================================
        derived_group = QGroupBox("⚡ DERIVED CPU UTILIZATION (Calculated from /proc/stat tick deltas)")
        derived_group.setStyleSheet(
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
        derived_layout = QVBoxLayout(derived_group)
        derived_layout.setSpacing(8)

        # Overall Banner
        banner_frame = QFrame()
        banner_frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(56, 189, 248, 0.15);
                border-radius: 6px;
                padding: 8px;
            }
            """
        )
        banner_layout = QVBoxLayout(banner_frame)
        banner_layout.setSpacing(4)

        top_banner_row = QHBoxLayout()
        title_banner = QLabel("OVERALL CPU UTILIZATION")
        title_banner.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")

        formula_tag = QLabel("[DERIVED: 1.0 - (Δidle + Δiowait) / Δtotal]")
        formula_tag.setStyleSheet("font-size: 10px; color: #38bdf8; font-family: monospace;")

        self.overall_pct_lbl = QLabel("— %")
        self.overall_pct_lbl.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #38bdf8; font-family: monospace;"
        )

        top_banner_row.addWidget(title_banner)
        top_banner_row.addWidget(formula_tag)
        top_banner_row.addStretch()
        top_banner_row.addWidget(self.overall_pct_lbl)
        banner_layout.addLayout(top_banner_row)

        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 1000)
        self.overall_bar.setValue(0)
        self.overall_bar.setTextVisible(False)
        self.overall_bar.setFixedHeight(12)
        self.overall_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 5px;
            }
            """
        )
        banner_layout.addWidget(self.overall_bar)
        derived_layout.addWidget(banner_frame)

        # Mode Breakdown Grid
        modes_title = QLabel("📊 CPU EXECUTION MODES (Percentage of total time interval)")
        modes_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #cbd5e1; margin-top: 4px;")
        derived_layout.addWidget(modes_title)

        modes_grid = QGridLayout()
        modes_grid.setSpacing(6)

        self.card_user = MetricCard("User (us)", "Application code")
        self.card_system = MetricCard("System (sy)", "Kernel execution")
        self.card_nice = MetricCard("Nice (ni)", "Low-priority user code")
        self.card_iowait = MetricCard("I/O Wait (wa)", "Linux reports iowait as a cumulative CPU-time counter")
        self.card_irq = MetricCard("Hardware IRQ (hi)", "Hardware interrupts")
        self.card_softirq = MetricCard("Software IRQ (si)", "Software interrupts")
        self.card_steal = MetricCard("Steal (st)", "Hypervisor stolen cycles")
        self.card_idle = MetricCard("Idle (id)", "CPU idle task")

        modes_grid.addWidget(self.card_user, 0, 0)
        modes_grid.addWidget(self.card_system, 0, 1)
        modes_grid.addWidget(self.card_nice, 0, 2)
        modes_grid.addWidget(self.card_iowait, 0, 3)
        modes_grid.addWidget(self.card_irq, 1, 0)
        modes_grid.addWidget(self.card_softirq, 1, 1)
        modes_grid.addWidget(self.card_steal, 1, 2)
        modes_grid.addWidget(self.card_idle, 1, 3)

        derived_layout.addLayout(modes_grid)

        # Per-Core Grid
        cores_title = QLabel("🧩 PER-CORE CPU UTILIZATION MATRIX")
        cores_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #cbd5e1; margin-top: 4px;")
        derived_layout.addWidget(cores_title)

        self.cores_grid_layout = QGridLayout()
        self.cores_grid_layout.setSpacing(6)
        self.core_widgets: dict[int, CoreMeterWidget] = {}

        derived_layout.addLayout(self.cores_grid_layout)
        content_layout.addWidget(derived_group)

        # ========================================================
        # 2. RAW LINUX COUNTERS & SCHEDULER STATE
        # ========================================================
        raw_group = QGroupBox("📋 RAW LINUX /proc/stat COUNTERS & SCHEDULER STATE")
        raw_group.setStyleSheet(
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
        raw_layout = QVBoxLayout(raw_group)
        raw_layout.setSpacing(8)

        # Scheduler State Cards
        sched_row = QHBoxLayout()
        sched_row.setSpacing(6)

        self.card_running = MetricCard("procs_running", "Processes in runnable state")
        self.card_blocked = MetricCard("procs_blocked", "Processes blocked waiting for I/O")
        self.card_ctxt_rate = MetricCard("Context Switches", "from /proc/stat ctxt")
        self.card_forks_rate = MetricCard("Process Forks", "from /proc/stat processes")
        self.card_btime = MetricCard("Boot Time (btime)", "from /proc/stat btime")

        sched_row.addWidget(self.card_running)
        sched_row.addWidget(self.card_blocked)
        sched_row.addWidget(self.card_ctxt_rate)
        sched_row.addWidget(self.card_forks_rate)
        sched_row.addWidget(self.card_btime)

        raw_layout.addLayout(sched_row)

        # Raw Cumulative Ticks Table
        table_title = QLabel("Cumulative Time Counters in Clock Ticks (USER_HZ):")
        table_title.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        raw_layout.addWidget(table_title)

        self.raw_table = QTableWidget()
        self.raw_table.setColumnCount(11)
        self.raw_table.setHorizontalHeaderLabels([
            "CPU", "user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice"
        ])
        self.raw_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.raw_table.verticalHeader().setVisible(False)
        self.raw_table.setStyleSheet(
            """
            QTableWidget {
                background-color: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                color: #f8fafc;
                font-family: monospace;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: bold;
                border: 1px solid rgba(255, 255, 255, 0.05);
                padding: 4px;
            }
            """
        )
        self.raw_table.setFixedHeight(160)
        raw_layout.addWidget(self.raw_table)

        content_layout.addWidget(raw_group)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def update_cpu(self, util: CpuUtilization | None, snapshot: CpuStatSnapshot):
        """Update CPU lab with factual raw counters and derived utilization."""
        # 1. Update Derived Overall & Modes
        if util is not None and util.total is not None:
            tot = util.total
            pct = tot.total_utilization_pct
            self.overall_pct_lbl.setText(f"{pct:.1f}%")
            self.overall_bar.setValue(int(pct * 10))

            if pct >= 85.0:
                color = "#ef4444"
            elif pct >= 60.0:
                color = "#f59e0b"
            else:
                color = "#38bdf8"

            self.overall_bar.setStyleSheet(
                f"""
                QProgressBar {{
                    background-color: rgba(0, 0, 0, 0.5);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 5px;
                }}
                """
            )

            self.card_user.set_value(f"{tot.user_pct:.1f}%", "Δuser / Δtotal")
            self.card_system.set_value(f"{tot.system_pct:.1f}%", "Δsystem / Δtotal")
            self.card_nice.set_value(f"{tot.nice_pct:.1f}%", "Δnice / Δtotal")
            self.card_iowait.set_value(f"{tot.iowait_pct:.1f}%", "Linux reports iowait as a cumulative CPU-time counter")
            self.card_irq.set_value(f"{tot.irq_pct:.1f}%", "Δirq / Δtotal")
            self.card_softirq.set_value(f"{tot.softirq_pct:.1f}%", "Δsoftirq / Δtotal")
            self.card_steal.set_value(f"{tot.steal_pct:.1f}%", "Δsteal / Δtotal")
            self.card_idle.set_value(f"{tot.idle_pct:.1f}%", "Δidle / Δtotal")
        else:
            self.overall_pct_lbl.setText("— %")
            self.overall_bar.setValue(0)

        # 2. Update Per-Core Matrix
        all_core_ids = sorted(snapshot.cores.keys())
        for core_id in all_core_ids:
            if core_id not in self.core_widgets:
                widget = CoreMeterWidget(core_id)
                self.core_widgets[core_id] = widget
                row = core_id // 4
                col = core_id % 4
                self.cores_grid_layout.addWidget(widget, row, col)

            core_util = util.per_core.get(core_id) if util is not None else None
            self.core_widgets[core_id].update_utilization(core_util)

        # 3. Update Raw Scheduler & Rates
        self.card_running.set_value(str(snapshot.procs_running), "Processes in runnable state")
        self.card_blocked.set_value(str(snapshot.procs_blocked), "Processes waiting for I/O")

        if util is not None and util.ctxt_rate is not None:
            self.card_ctxt_rate.set_value(
                f"{int(util.ctxt_rate):,} / s",
                f"Derived over {util.sample_interval_seconds:.2f}s interval",
            )
        else:
            self.card_ctxt_rate.set_value(f"{snapshot.ctxt:,}", "Total cumulative ctxt")

        if util is not None and util.forks_rate is not None:
            self.card_forks_rate.set_value(
                f"{int(util.forks_rate):,} / s",
                f"Derived over {util.sample_interval_seconds:.2f}s interval",
            )
        else:
            self.card_forks_rate.set_value(f"{snapshot.processes:,}", "Total cumulative forks")

        if snapshot.btime > 0:
            try:
                btime_dt = datetime.fromtimestamp(snapshot.btime)
                self.card_btime.set_value(btime_dt.strftime("%Y-%m-%d %H:%M:%S"), f"btime = {snapshot.btime}")
            except (ValueError, OSError):
                self.card_btime.set_value(str(snapshot.btime), "Epoch timestamp")
        else:
            self.card_btime.set_value("N/A", "btime unavailable")

        # 4. Update Raw Cumulative Ticks Table
        rows_data = [("cpu (total)", snapshot.total_cpu)]
        for core_id in all_core_ids:
            rows_data.append((f"cpu{core_id}", snapshot.cores[core_id]))

        self.raw_table.setRowCount(len(rows_data))
        for row_idx, (label, times) in enumerate(rows_data):
            items = [
                label,
                f"{times.user:,}",
                f"{times.nice:,}",
                f"{times.system:,}",
                f"{times.idle:,}",
                f"{times.iowait:,}",
                f"{times.irq:,}",
                f"{times.softirq:,}",
                f"{times.steal:,}",
                f"{times.guest:,}",
                f"{times.guest_nice:,}",
            ]
            for col_idx, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col_idx == 0 else Qt.AlignmentFlag.AlignRight)
                self.raw_table.setItem(row_idx, col_idx, item)
