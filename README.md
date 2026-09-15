# Linux Visual Learning Lab

An interactive, real-time educational desktop application designed to visualize Linux operating system internals directly from the kernel source of truth.

> **Architectural North Star:**  
> **Observe first. Represent the observed state exactly. Visualize it. Explain only what is directly derivable from that observed state. Never substitute an application-defined model for Linux behavior.**
> 
> The Linux kernel and OS subsystem interfaces (`/proc`, `/sys`, POSIX `stat()`, `inotify`) are the absolute authority. The application displays what Linux actually reports without inventing pedagogical storytelling.

---

### Information Classification Rule

| Type | Examples | Policy |
|---|---|---|
| **Observed State** | `PID=1234`, `st_mode=0100644`, `/proc/<PID>/cwd`, `/proc/<PID>/stat`, `/proc/meminfo`, `/proc/stat`, `/proc/<PID>/fd` | ✅ **Required Authority** |
| **Directly Derived State** | `0644 → rw-r--r--`, `6 = 4(r) + 2(w)`, `PPID` tree hierarchy, CPU tick deltas to %, Pipe inode matching | ✅ **Allowed Derivation** |
| **Invented / Simulated State** | "Process is doing X", "File is safe", fake permissions, mocked CPU load | ❌ **Strictly Forbidden** |

### Identity Highlighting Principle

> **Visual encodings may expose relationships in observed Linux data, but must never alter, simulate, or replace that data.**  
> *Color is metadata about the display, never about Linux.*

Identifiers (`PID`, `PPID`, `PGID`, `SID`, `TPGID`, `UID`, `GID`, `inode`, `device`) use deterministic identity highlighting:
- **Same value $\rightarrow$ Same visual token** across all tabs and panels.
- **Different value $\rightarrow$ Different visual token**.
- Underlying domain data remains unchanged (`pid = 1234`, `uid = 1000`, `inode = 78123`).

---

## 1. System Architecture & Data Flow

The application follows a strict unidirectional reactive architecture. Observers continuously sample kernel interfaces on background threads, convert raw data into immutable domain models, detect state transitions, and publish standardized `SystemEvent`s onto a central thread-safe `EventBus`. UI components and visualizers subscribe to events and render live state without ever blocking on low-level OS operations.

The application uses **two distinct signal paths** from monitors to UI, depending on the data type:

1. **Direct Telemetry Signals** — High-frequency data snapshots (`cpu_updated`, `memory_updated`, `io_updated`, `processes_updated`, `sessions_updated`) flow via Qt Signals directly from each monitor to its corresponding Lab widget or MainWindow handler. This path carries full state objects for rich visualization and avoids flooding the EventBus.

2. **EventBus Path** — Discrete state-transition events (`process.created`, `shell.cwd_changed`, `file.modified`, etc.) are published as `SystemEvent` objects onto the thread-safe `EventBus`, where the `ActivityTimelineWidget` and cross-cutting handlers subscribe.

> **Note:** The `CpuMonitor` uses the direct telemetry path exclusively — it does **not** publish to the EventBus — because CPU tick deltas are continuous samples, not discrete state transitions.

```text
                                  ┌──────────────────────────────────────────────────┐
                                  │               Linux Kernel & OS                  │
                                  │   /proc/<pid>/*   /proc/*   POSIX stat() inotify │
                                  └─────────────────────────┬────────────────────────┘
                                                            │
                                                  REAL OBSERVATIONS ONLY
                                                            │
   ┌────────────────────┬────────────────────┬──────────────┴─────┬────────────────────┬────────────────────┐
   │                    │                    │                    │                    │                    │
┌──▼───────────────┐ ┌──▼───────────────┐ ┌──▼───────────────┐ ┌──▼───────────────┐ ┌──▼───────────────┐ ┌──▼───────────────┐
│ FileSystem       │ │ TerminalSession  │ │ Process          │ │ I/O              │ │ Memory           │ │ CPU              │
│ Monitor          │ │ Thread           │ │ Monitor          │ │ Monitor          │ │ Monitor          │ │ Monitor          │
│ watchdog+stat()  │ │ SessionManager   │ │ ProcessRegistry  │ │ IoRegistry       │ │ MemoryRegistry   │ │ CpuRegistry      │
│ (stat_cache)     │ │ /proc/<pid>/cwd  │ │ /proc/<pid>/stat │ │ /proc/<pid>/fd   │ │ /proc/meminfo    │ │ /proc/stat       │
└─┬──────────────┬─┘ └─┬──────────────┬─┘ └─┬──────────────┬─┘ └─┬──────────────┬─┘ └─┬──────────────┬─┘ └─┬────────────────┘
  │              │      │              │      │              │      │              │      │              │      │ cpu_updated
  │ event_       │      │ event_       │      │ event_       │      │ event_       │      │ event_       │      │ (DIRECT ONLY)
  │ detected     │      │ detected     │      │ detected     │      │ detected     │      │ detected     │      │
  │              │      │              │      │              │      │              │      │              │      │
  │    Qt signals│      │  sessions_   │      │  processes_  │      │  io_updated  │      │  memory_     │      │
  │    (created, │      │  updated     │      │  updated     │      │  diskstats_  │      │  updated     │      │
  │    deleted,  │      │              │      │              │      │  updated     │      │              │      │
  │    moved,    │      │              │      │              │      │  locks_      │      │              │      │
  │    modified, │      │              │      │              │      │  updated     │      │              │      │
  │    perms)    │      │              │      │              │      │              │      │              │      │
  │              │      │              │      │              │      │              │      │              │      │
  │  EVENTBUS    │      │  EVENTBUS    │      │  EVENTBUS    │      │  EVENTBUS    │      │  EVENTBUS    │      │
  │  PATH:       │      │  PATH:       │      │  PATH:       │      │  PATH:       │      │  PATH:       │      │
  ▼              ▼      ▼              ▼      ▼              ▼      ▼              ▼      ▼              ▼      ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         MainWindow (Orchestrator)                                            │
│  Owns: EventBus, ActivityTimeline, FocusedSession, session_snapshot                                          │
│  Routes: event_detected → EventBus.publish()                                                                 │
│  Routes: Direct telemetry → Lab Widgets                                                                      │
│  Manages: Cross-lab synchronization (Process selection ↔ IO Lab target, Session focus ↔ ContextPanel)        │
├──────────────────────────────────────────────────────────────────────────────────────────────────┬─────────────┤
│                                          EventBus (Pub/Sub)                                     │             │
│                                 Subscriptions: handle_bus_event → ActivityTimeline.record()      │             │
│                                                handle_bus_event → TimelineWidget.add_event()     │             │
│                                                handle_shell_cwd_changed → ContextPanel + Tree    │             │
├───────────┬──────────────┬───────────────────────────────────────────────┬───────────────────────┤             │
│ Context   │ Terminal     │           Center Tabs (5 Labs)               │                       │             │
│ Panel     │ Sessions     ├───────┬───────┬───────┬───────┬──────────────┤  Activity             │             │
│ (Banner)  │ Widget +     │ 🔬 FS │ ⚡Proc│ 🗂️ I/O│ 🧠Mem │ 🔥 CPU      │  Timeline             │             │
│           │ FS Tree      │ Lab   │ Lab   │ Lab   │ Lab   │ Lab          │  Widget               │             │
│ (Top)     │ (Left)       │       │       │       │       │              │  (Right)              │             │
└───────────┴──────────────┴───────┴───────┴───────┴───────┴──────────────┴───────────────────────┘             │
```

### Signal Flow Detail Per Monitor

| Monitor | Direct Telemetry Signal → Target | EventBus Path (`event_detected`) |
|---|---|---|
| **FileSystemMonitor** | Qt signals (`created`, `deleted`, `modified`, `moved`, `permissions_changed`) → MainWindow handlers → rebuild `FilesystemTreeWidget` + refresh `SelectedObjectInspectorWidget` | `event_detected` → `EventBus.publish()` (connected via constructor `event_bus` param) |
| **TerminalSessionThread** | `sessions_updated(dict)` → MainWindow → `TerminalSessionWidget`, `ContextPanel`, `FilesystemTreeWidget` (CWD highlight) | `event_detected` → `EventBus.publish()` |
| **ProcessMonitor** | `processes_updated(dict)` → MainWindow → `ProcessLabWidget.update_processes()`, `IoLabWidget.update_process_list()` | `event_detected` → `EventBus.publish()` |
| **IoMonitor** | `io_updated(ProcessIoState)` → `IoLabWidget.update_io_state()`; `diskstats_updated` → `IoLabWidget.update_diskstats()`; `locks_updated` → `IoLabWidget.update_locks()` | `event_detected` → `EventBus.publish()` |
| **MemoryMonitor** | `memory_updated(MemorySnapshot, SystemLoadSnapshot)` → `MemoryLabWidget.update_memory()` | `event_detected` → `EventBus.publish()` |
| **CpuMonitor** | `cpu_updated(CpuUtilization, CpuStatSnapshot)` → `CpuLabWidget.update_cpu()` | ❌ **None** — no `event_detected` signal; CPU telemetry is continuous, not event-based |

> **Key Design Decision:** Registries (`ProcessRegistry`, `CpuRegistry`, `MemoryRegistry`, `IoRegistry`) are owned **inside** their respective Worker objects and operate within the worker's QThread. They are not standalone Layer 3 services — they are co-located with their observer to keep snapshot diffing and delta math in the background thread. The `FileSystemMonitor` does not use a separate registry at all; it maintains a lightweight `stat_cache` dict internally for permission-change diffing.

### The 6 Conceptual Layers

| Layer | Name | Core Responsibilities | Modules |
|---|---|---|---|
| **Layer 1** | **Linux Kernel / OS** | Absolute source of truth. Kernel interfaces, pseudo-filesystems, POSIX system calls. | `/proc`, `/sys`, `inotify`, `stat()` |
| **Layer 2 + 3** | **Observers & Registries** | Background QThread workers sampling OS state, with co-located registries performing snapshot diffing, tick-delta math, and pipe correlation inside the worker thread. | `app.monitors.filesystem` (watchdog + stat_cache), `app.process.monitor` + `registry`, `app.cpu.monitor` + `registry`, `app.memory.monitor` + `registry`, `app.io.monitor` + `registry` |
| **Layer 4** | **Event Bus & Taxonomy** | Thread-safe pub/sub event dispatch. Only discrete state-transition events flow here — not continuous telemetry. | `app.core.event_bus`, `app.core.events`, `app.core.activity` |
| **Layer 5** | **Educational Visualizers** | Rich domain-specific interactive widgets receiving data via direct signals (telemetry) and EventBus subscriptions (timeline events). | `app.visualizers.*` (`filesystem_view`, `process_view`, `io_view`, `memory_view`, `cpu_view`, `activity_timeline`, `session_panel`) |
| **Layer 6** | **Application UI & Orchestration** | `MainWindow` as central orchestrator owning `EventBus`, `FocusedSession`, `ActivityTimeline`, and coordinating cross-lab state (process selection ↔ IO target, session focus ↔ context panel). Also: deterministic color encoders and dark QSS theme. | `app.ui.main_window`, `app.ui.panels`, `app.ui.identity`, `app.ui.styles` |

### Linux OS Data Sources

| Subsystem | Linux Kernel Source | Observed Metrics / Facts |
|---|---|---|
| **Filesystem** | `watchdog` (`inotify`), POSIX `stat()` / `lstat()` | Inode, device, mode, UID, GID, file size, hard link count, `atime`, `mtime`, `ctime`. |
| **Terminal Sessions** | `/proc/<pid>/stat`, `/proc/<pid>/cmdline`, `/proc/<pid>/cwd` | Shell PID, parent PID, controlling TTY, executable name, live current working directory. |
| **Process Tree** | `/proc/[0-9]*/stat`, `/proc/[0-9]*/status`, `/proc/[0-9]*/cmdline` | PID, PPID, PGID, SID, TPGID, scheduler state (`R`, `S`, `D`, `T`, `Z`), UIDs/GIDs, full CLI arguments. |
| **File Descriptors & I/O** | `/proc/<pid>/fd/*`, `/proc/<pid>/fdinfo/*`, `/proc/<pid>/io`, `/proc/diskstats`, `/proc/locks` | Open FDs, target symlinks (regular files, sockets, pipes, ttys, anon_inodes), cursor offset (`pos`), octal flags, mount IDs, VFS syscall vs physical I/O counters, kernel file locks. |
| **Memory & Load** | `/proc/meminfo`, `/proc/loadavg`, `/proc/uptime` | `MemTotal`, `MemFree`, `MemAvailable`, `Buffers`, `Cached`, `SwapTotal`, `SwapFree`, Active/Inactive pages, Slab, 1m/5m/15m load averages, runnable threads, uptime. |
| **CPU Utilization** | `/proc/stat` | Cumulative USER_HZ clock ticks per core and aggregate: `user`, `nice`, `system`, `idle`, `iowait`, `irq`, `softirq`, `steal`, context switch count (`ctxt`), total processes spawned (`processes`), running / blocked queues. |

---

## 2. Directory Structure

```text
linux-visual-lab/
├── app/
│   ├── __init__.py
│   ├── main.py                          # Application entry point & Qt app setup
│   │
│   ├── core/                            # Layer 4: Event Engine & Core Models
│   │   ├── __init__.py
│   │   ├── events.py                    # Standardized SystemEvent dataclass & timestamps
│   │   ├── event_bus.py                 # Thread-safe EventBus (pub/sub engine)
│   │   ├── activity.py                  # Thread-safe ActivityTimeline bounded event store
│   │   └── models.py                    # FilesystemObject (POSIX stat domain model & bitmasks)
│   │
│   ├── process/                         # Layer 2 & 3: Process & Terminal Subsystem
│   │   ├── __init__.py
│   │   ├── model.py                     # Canonical Process domain model
│   │   ├── discovery.py                 # Direct /proc/<pid> parser & scanner
│   │   ├── registry.py                  # ProcessRegistry & snapshot diffing engine
│   │   ├── tree.py                      # Real PID/PPID hierarchy constructor
│   │   ├── monitor.py                   # ProcessWorker & ProcessMonitor QThread controller
│   │   ├── session.py                   # TerminalSession dataclass
│   │   ├── session_manager.py           # Shell session state-diff engine
│   │   ├── session_worker.py            # QObject worker polling shells in background
│   │   ├── session_thread.py            # QThread controller for shell sessions
│   │   ├── focused_session.py           # FocusedSession (tracks active terminal)
│   │   ├── focused_cwd.py               # FocusedSessionCwd (resolves /proc/<PID>/cwd)
│   │   ├── focused_cwd_tracker.py       # FocusedCwdTracker diff & event publisher
│   │   └── cwd.py                       # Safe CWD symlink resolution utilities
│   │
│   ├── monitors/                        # Layer 2: Filesystem Observers
│   │   ├── __init__.py
│   │   └── filesystem.py                # FileSystemMonitor (watchdog inotify + stat diffing)
│   │
│   ├── cpu/                             # Layer 2 & 3: CPU Subsystem
│   │   ├── __init__.py
│   │   ├── model.py                     # CpuTimes, CpuStatSnapshot, CpuUtilization models
│   │   ├── discovery.py                 # Direct /proc/stat parser (aggregate + per-core)
│   │   ├── registry.py                  # CpuRegistry (consecutive tick-delta math engine)
│   │   ├── monitor.py                   # CpuMonitor QThread controller
│   │   └── clock.py                     # Linux USER_HZ / clock tick resolution helper
│   │
│   ├── memory/                          # Layer 2 & 3: Memory & Load Subsystem
│   │   ├── __init__.py
│   │   ├── model.py                     # MemorySnapshot, SystemLoadSnapshot models & formatters
│   │   ├── discovery.py                 # /proc/meminfo, /proc/loadavg, /proc/uptime parsers
│   │   ├── registry.py                  # MemoryRegistry & snapshot cache
│   │   └── monitor.py                   # MemoryMonitor QThread controller
│   │
│   ├── io/                              # Layer 2 & 3: File Descriptors & I/O Subsystem
│   │   ├── __init__.py
│   │   ├── model.py                     # FileDescriptor, PipeEndpoint, ProcessIoSnapshot, DiskStat
│   │   ├── discovery.py                 # /proc/<pid>/fd, fdinfo, /proc/diskstats, /proc/locks parsers
│   │   ├── registry.py                  # ProcessIoRegistry, delta rates & inter-process pipe matcher
│   │   └── monitor.py                   # IoMonitor QThread controller
│   │
│   ├── visualizers/                     # Layer 5: Educational Visualizer Panels & Tabs
│   │   ├── __init__.py
│   │   ├── base.py                      # BaseVisualizer abstract contract
│   │   ├── filesystem_view.py           # FilesystemTreeWidget & SelectedObjectInspectorWidget
│   │   ├── process_view.py              # ProcessTreeWidget, ProcessInspector & ProcessLabWidget
│   │   ├── io_view.py                   # FdTableWidget, PipeMatrix, ProcessIoStats, IoLabWidget
│   │   ├── memory_view.py               # MemoryLabWidget (Load banner, memory gauges, swap, meminfo)
│   │   ├── cpu_view.py                  # CpuLabWidget (Aggregate, per-core meters, metric breakdown)
│   │   ├── session_panel.py             # TerminalSessionWidget (active shells & focus toggle)
│   │   └── activity_timeline.py         # ActivityTimelineWidget (live educational event stream)
│   │
│   └── ui/                              # Layer 6: UI Orchestration & Styling
│       ├── __init__.py
│       ├── main_window.py               # MainWindow orchestrator (wires Core, Observers, Visualizers)
│       ├── panels.py                    # ContextPanel ("YOU ARE HERE", breadcrumbs, path anatomy)
│       ├── identity.py                  # Deterministic same-value identity color token encoder
│       └── styles.py                    # QSS dark theme stylesheet
│
├── tests/                               # Comprehensive Automated Test Suite (220 tests, 45 suites)
│   ├── __init__.py
│   ├── test_activity_timeline.py
│   ├── test_cpu_advanced.py
│   ├── test_cpu_clock.py
│   ├── test_cpu_discovery.py
│   ├── test_cpu_model.py
│   ├── test_cpu_monitor.py
│   ├── test_cpu_registry.py
│   ├── test_cpu_visualizer.py
│   ├── test_event_bus.py
│   ├── test_filesystem_monitor.py
│   ├── test_filesystem_object.py
│   ├── test_filesystem_tree.py
│   ├── test_focused_cwd.py
│   ├── test_focused_cwd_tracker.py
│   ├── test_focused_session.py
│   ├── test_identity.py
│   ├── test_integration.py
│   ├── test_io_discovery.py
│   ├── test_io_integration.py
│   ├── test_io_model.py
│   ├── test_io_monitor.py
│   ├── test_io_registry.py
│   ├── test_io_visualizer.py
│   ├── test_live_activity_truth.py
│   ├── test_main_window.py
│   ├── test_memory_discovery.py
│   ├── test_memory_model.py
│   ├── test_memory_monitor.py
│   ├── test_memory_registry.py
│   ├── test_memory_visualizer.py
│   ├── test_process_cpu.py
│   ├── test_process_cpu_advanced.py
│   ├── test_process_discovery.py
│   ├── test_process_events.py
│   ├── test_process_integration.py
│   ├── test_process_monitor.py
│   ├── test_process_registry.py
│   ├── test_process_tree.py
│   ├── test_process_visualizer.py
│   ├── test_robustness.py
│   ├── test_session_discovery.py
│   ├── test_session_manager.py
│   ├── test_session_thread.py
│   ├── test_session_worker.py
│   └── test_terminal_session.py
│
├── LinuxLab/                            # Default monitored sandbox directory
├── requirements.txt                     # Runtime dependencies (PySide6, watchdog, psutil)
└── .gitignore
```

---

## 3. Interactive Learning Labs & Visualizer Suite

The application interface is organized into a 3-column multi-pane workspace with top contextual navigation:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 📍 CURRENT LOCATION: /home/dev/LinuxLab/project  |  / → home → dev → LinuxLab → project│
├──────────────────┬───────────────────────────────────────────────┬─────────────────────┤
│ 🖥 TERMINAL      │ [🔬 Filesystem] [⚡ Process] [🗂️ I/O & FDs]   │ 🔴 LIVE LINUX       │
│   SESSIONS       │ [🧠 Memory & Load] [🔥 CPU Lab]               │    ACTIVITY         │
│  ● bash (1234)   ├───────────────────────────────────────────────┤    TIMELINE         │
│  ○ zsh (5678)    │                                               │                     │
├──────────────────┤                                               │  [FILE.CREATED]     │
│ 📁 FILESYSTEM    │          Active Lab Workspace View            │  17:14:02.120       │
│  ▼ LinuxLab      │                                               │  touch report.txt   │
│   🟢 📂 project 👈│                                               │                     │
│    📄 file.txt   │                                               │  [SHELL.CWD_CHANGED]│
│                  │                                               │  17:14:15.890       │
│                  │                                               │  cd project         │
└──────────────────┴───────────────────────────────────────────────┴─────────────────────┘
```

### Top Context Banner (`ContextPanel`)
- **Live Location Header**: Displays real-time absolute path of the focused terminal session.
- **Breadcrumb Navigation**: Visual clickable trail of directory components from root `/` to leaf.
- **Path Anatomy**: Exploded structural view detailing root, parent depth, and active folder name.

### Left Panel: Terminal Sessions & Filesystem Hierarchy
1. **Terminal Sessions (`TerminalSessionWidget`)**:
   - Auto-discovers all active shell instances (`bash`, `zsh`, `sh`, `fish`).
   - Displays Shell Name, PID, and controlling TTY (`/dev/pts/1`).
   - Focus indicator: `● FOCUSED TERMINAL` vs `○ TERMINAL`. Selecting a session directs the live filesystem tracker to follow that shell's working directory.
2. **Filesystem Tree (`FilesystemTreeWidget`)**:
   - Recursively visualizes the directory structure of the monitored lab path (e.g. `LinuxLab`).
   - Real-time `🟢 📂 <dir> 👈` badge dynamically points to the focused shell's current working directory.
   - Immediate inotify-driven updates on creation, modification, deletion, and permission changes.

### Center Workspace: The 5 Interactive Labs

#### Tab 1: 🔬 POSIX Filesystem Lab (`SelectedObjectInspectorWidget`)
- **Real POSIX Inode Metadata**: File size (bytes + human-readable), inode number, device ID, hard link count, and high-resolution timestamps (`Access time / atime`, `Modify time / mtime`, `Change time / ctime`).
- **Linux Ownership**: Real UID and GID along with system resolved user/group names.
- **3x3 Permissions Matrix**: Interactive grid decomposing permissions across `OWNER`, `GROUP`, and `OTHER` against `READ (4)`, `WRITE (2)`, and `EXECUTE (1)` with clear status indicators (`✓` / `✗`).
- **Octal Arithmetic Decomposition**: Shows exact bitwise arithmetic (e.g., `0755 → 7(4+2+1) 5(4+0+1) 5(4+0+1)`).
- **Interactive DAC Kernel Access Evaluator**: Lets users test whether a hypothetical process (defined by UID/GID) would be granted or denied Read, Write, or Execute access according to standard Linux Discretionary Access Control rules.

#### Tab 2: ⚡ Linux Process Lab (`ProcessLabWidget`)
- **Process Hierarchy Tree & Table**: Complete snapshot view of system processes with columns: `PID`, `PPID`, `PGID`, `SID`, `TPGID`, `STATE`, `TTY`, `USER`, `COMMAND`.
- **Deterministic Identity Highlighting**: Same-value color tokens link related PIDs, PPIDs, PGIDs, and SIDs across all views.
- **Kernel Scheduler States**: Factual indicators for `R` (Running), `S` (Interruptible Sleep), `D` (Uninterruptible Disk Sleep), `T` (Stopped / Traced), `Z` (Zombie).
- **Process Inspector**: Deep-dive into session leadership, process group leadership, foreground/background status, real vs effective credentials, and complete command-line argument vector.

#### Tab 3: 🗂️ Linux File Descriptors & I/O Lab (`IoLabWidget`)
- **Live File Descriptor Table**: Lists all open descriptors (`/proc/<pid>/fd`) for the selected or focused process with type categorization:
  - `FILE`: Regular filesystem files
  - `DIR`: Open directory handles
  - `TTY`: PTY/TTY terminal streams
  - `PIPE`: Anonymous or named FIFO pipes with extracted inode
  - `SOCKET`: UNIX domain or network sockets with extracted inode
  - `ANON`: `anon_inode` targets (e.g. `eventfd`, `epoll`, `timerfd`, `signalfd`)
  - `DEV`: Character or block device nodes (`/dev/null`, `/dev/urandom`)
  - `DELETED`: Files unlinked while still held open by a process
- **Selected Descriptor Inspector**: Extracts `/proc/<pid>/fdinfo/<fd>` data including file cursor byte offset (`pos`), raw octal flags (`0200002`), decoded POSIX flags (`O_RDWR`, `O_APPEND`, `O_CLOEXEC`, `O_NONBLOCK`), mount ID, and standard stream roles (`stdin (0)`, `stdout (1)`, `stderr (2)`).
- **Inter-Process Pipe Sharing Matrix**: Automatically correlates pipe inodes across the system, pairing the write-end process (`O_WRONLY`) with the read-end process (`O_RDONLY`).
- **Process I/O Telemetry & Rates**: Separates VFS system call counters (`rchar`, `wchar`, `syscr`, `syscw`) from physical block storage counters (`read_bytes`, `write_bytes`, `cancelled_write_bytes`) with live delta rates (`KB/s`, `ops/s`).
- **System Telemetry**: Real-time block device statistics from `/proc/diskstats` and active kernel file locks from `/proc/locks` (`POSIX`, `FLOCK`, `OFD`).
- **Process Picker & Follow Mode**: Pin the view to any specific process or toggle "Follow Focused Terminal" to automatically inspect whatever command is running in your shell.

#### Tab 4: 🧠 Linux Memory Lab (`MemoryLabWidget`)
- **System Load & Uptime Banner**: Real-time 1-minute, 5-minute, and 15-minute load averages, runnable vs total thread entities from `/proc/loadavg`, and human-formatted uptime from `/proc/uptime`.
- **Visual Memory Metrics**: Proportional visual meters comparing `MemTotal`, `MemFree`, `MemAvailable`, `Buffers`, and `Cached`.
- **Derived Estimations & Explanations**: Clarifies the vital distinction between `MemFree` (completely unallocated pages) and `MemAvailable` (memory reclaimable without swapping), plus explicit sums for `Buffers + Cached + KReclaimable` and estimated used memory.
- **Swap Space Breakdown**: Factual breakdown of `SwapTotal`, `SwapFree`, `SwapUsed`, and `SwapCached`.
- **Comprehensive `/proc/meminfo` Grid**: Raw integer metrics covering Active/Inactive Anon/File memory, Unevictable, Mlocked, Dirty, Writeback, Slab (SReclaimable, SUnreclaim), KernelStack, PageTables, Committed_AS, and CommitLimit.

#### Tab 5: 🔥 Linux CPU Lab (`CpuLabWidget`)
- **Aggregate CPU Utilization**: System-wide CPU load calculated from consecutive `/proc/stat` USER_HZ tick deltas.
- **Per-Core Utilization Meter Grid**: Live utilization bars and percentages for every individual CPU core (`cpu0`, `cpu1`, ... `cpuN`).
- **Detailed Time Breakdown**: Factual breakdown across all 8 Linux CPU time states: `User %`, `System %`, `Nice %`, `Idle %`, `I/O Wait %`, `IRQ %`, `SoftIRQ %`, and `Steal %`.
- **Scheduler & Kernel Rates**: Live rates for Context Switches per second (`ctxt/s`), Fork / Process Creation Rate per second (`forks/s`), and counts of processes currently runnable vs blocked waiting on I/O.
- **Raw `/proc/stat` Snapshot Viewer**: Point-in-time raw tick counts and kernel parameters.

### Right Panel: Live Activity Timeline (`ActivityTimelineWidget`)
- **Real-Time Streaming Event Log**: Continuously captures and displays every filesystem, process, shell, memory, and I/O event.
- **Visual Categorization**: Distinct color badges for each event domain with millisecond-accurate timestamps (`HH:MM:SS.mmm`).
- **Factual Linux Insights**: Includes kernel explanations for observed actions (e.g. explaining inotify event triggers, fork/exec mechanics, or file unlinking with open descriptors).
- **Interactive Controls**: Live keyword search filter, clear log button, and pause/resume stream toggle.

---

## 4. Standardized Event Taxonomy

All events flowing through the `EventBus` adhere to a `<domain>.<action>` hierarchy:

| Event Type | Source / Mechanism | Description |
|---|---|---|
| `file.created` | `watchdog` (inotify) | New regular file or special node created |
| `file.modified` | `watchdog` (inotify) | File content modified |
| `file.deleted` | `watchdog` (inotify) | File removed or unlinked |
| `file.moved` | `watchdog` (inotify) | File renamed or moved |
| `file.permissions_changed` | `stat()` polling | Inode mode or ownership changed (`chmod` / `chown`) |
| `directory.created` | `watchdog` (inotify) | New directory created |
| `directory.deleted` | `watchdog` (inotify) | Directory removed |
| `shell.session_created` | `/proc` shell scan | New shell process spawned |
| `shell.session_removed` | `/proc` shell scan | Shell process terminated |
| `shell.cwd_changed` | `/proc/<pid>/cwd` | Shell executed directory change (`cd`) |
| `shell.focused_cwd_changed` | `FocusedCwdTracker` | The currently followed shell changed directory |
| `process.created` | `/proc` snapshot diff | New PID observed in `/proc` |
| `process.removed` | `/proc` snapshot diff | PID exited and reaped |
| `process.state_changed` | `/proc/<pid>/stat` | Scheduler state changed (e.g. `S → R` or `S → T`) |
| `process.cwd_changed` | `/proc/<pid>/cwd` | Process changed working directory |
| `memory.swap_usage_changed`| `/proc/meminfo` | Swap space consumption increased or decreased |
| `io.fd_appeared` | `/proc/<pid>/fd` | Process opened a new file descriptor |
| `io.fd_disappeared` | `/proc/<pid>/fd` | Process closed a file descriptor |
| `io.pipe_shared` | `ProcessIoRegistry` | Inter-process pipe detected connecting two processes |

---

## 5. Installation & Getting Started

### Prerequisites

- **Operating System:** Linux (Ubuntu 20.04+, Debian 11+, Fedora 36+, Arch Linux, or WSL2 on Windows with GUI support).
- **Python Version:** Python 3.10, 3.11, or 3.12+.
- **System Libraries (for Qt GUI on Debian/Ubuntu):**
  ```bash
  sudo apt update
  sudo apt install -y python3-venv python3-pip libgl1-mesa-glx libxkbcommon-x11-0 libegl1
  ```

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/linux-visual-lab.git
cd linux-visual-lab
```

### Step 2: Set Up Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Launch the Application
```bash
python app/main.py
```
*(Or launch directly with the virtualenv binary: `.venv/bin/python app/main.py`)*

---

## 6. Hands-On Interactive Experiments

To get the most out of the Linux Visual Learning Lab, open a terminal window side-by-side with the application and execute these guided experiments.

### Experiment 1: The "You Are Here" Filesystem & Terminal Sync
1. Open a terminal. In the app's left **Terminal Sessions** panel, note that your shell (`bash` or `zsh`) is listed and marked as `● FOCUSED TERMINAL`.
2. In your terminal, navigate into the lab directory:
   ```bash
   cd LinuxLab
   mkdir experiment_1
   cd experiment_1
   touch hello_linux.txt
   ```
3. **Observe:**
   - The top **Context Panel** updates instantly: `📍 CURRENT LOCATION: /.../LinuxLab/experiment_1`.
   - The **Filesystem Tree** adds the directory and moves the green marker `🟢 📂 experiment_1 👈` in real time.
   - The right **Activity Timeline** records `directory.created`, `shell.cwd_changed`, and `file.created` events with microsecond timestamps.

---

### Experiment 2: POSIX Permission Bitmasks & Octal Arithmetic
1. In your terminal, create a test script with restrictive permissions:
   ```bash
   echo '#!/bin/bash' > LinuxLab/experiment_1/script.sh
   chmod 600 LinuxLab/experiment_1/script.sh
   ```
2. Click `script.sh` in the app's **Filesystem Tree** and open **Tab 1: 🔬 POSIX Filesystem Lab**.
3. **Observe:**
   - **Mode:** `0600` (`-rw-------`).
   - **Permissions Matrix:** Owner has Read (`✓`) and Write (`✓`); Group and Other are completely denied (`✗`).
   - **Arithmetic Breakdown:** `6 = 4+2+0`, `0 = 0+0+0`, `0 = 0+0+0`.
4. Now change the permissions in your terminal:
   ```bash
   chmod 755 LinuxLab/experiment_1/script.sh
   ```
5. **Observe:**
   - The inspector instantly updates to `0755` (`-rwxr-xr-x`).
   - The 3x3 matrix reflects Execute permissions for Owner, Group, and Other.
   - Use the **Kernel Access Evaluator** at the bottom of the tab to test access for different UIDs/GIDs.

---

### Experiment 3: Process Hierarchy, Subshells & Identity Highlighting
1. In your terminal, spawn a subshell and run a background task:
   ```bash
   bash
   sleep 300 &
   ```
2. Switch to **Tab 2: ⚡ Linux Process Lab**.
3. In the search filter, type `sleep` or find your shell PID.
4. **Observe:**
   - The tree displays the parent-child nesting: Parent Shell $\rightarrow$ Subshell $\rightarrow$ `sleep 300`.
   - The `PID`, `PPID`, and `PGID` columns display **identical visual color tokens** matching parent and child.
   - The `STATE` column shows `S` (Interruptible Sleep) for `sleep 300`.
   - In your terminal, suspend a job with `Ctrl+Z` or send `kill -STOP <PID>` and watch the state transition to `T` (Stopped).

---

### Experiment 4: File Descriptors, Redirection & Pipe Tracing
1. In your terminal, create a running pipeline between two processes:
   ```bash
   yes "LinuxLab" | grep "LinuxLab" > /dev/null &
   ```
2. Switch to **Tab 3: 🗂️ Linux File Descriptors & I/O Lab**.
3. Click on the `yes` process in the Process Picker:
   - Examine FD `1` (`stdout`): Its target is `pipe:[<inode_num>]` with access mode `O_WRONLY` (Write end).
4. Click on the `grep` process in the Process Picker:
   - Examine FD `0` (`stdin`): Its target is `pipe:[<inode_num>]` with access mode `O_RDONLY` (Read end).
   - Examine FD `1` (`stdout`): Its target points to `/dev/null` (`DEV`).
5. **Observe:**
   - The **Inter-Process Pipe Sharing Matrix** matches the exact same pipe inode between `yes` (Writer) and `grep` (Reader).
   - In the **Process I/O Stats** card, observe live `rchar` / `wchar` syscall counters incrementing rapidly.
6. Clean up the background job:
   ```bash
   killall yes grep
   ```

---

### Experiment 5: Linux Memory, Buffers & Cache
1. Switch to **Tab 4: 🧠 Linux Memory Lab**.
2. Examine the **System Load & Uptime** banner at the top (`loadavg` 1m, 5m, 15m and running/total threads).
3. In your terminal, allocate a temporary 150 MB memory buffer in Python:
   ```bash
   python3 -c "import time; data = bytearray(150 * 1024 * 1024); time.sleep(15)"
   ```
4. **Observe:**
   - `MemAvailable` and `MemFree` decrease during the allocation.
   - The visual memory gauge updates in real time.
   - Contrast `MemFree` with `MemAvailable` and inspect `Buffers + Cached` memory.

---

### Experiment 6: Multi-Core CPU Utilization & Context Switches
1. Switch to **Tab 5: 🔥 Linux CPU Lab**.
2. Note the baseline CPU utilization, per-core meters, and context switch rate (`ctxt/s`).
3. In your terminal, run a brief CPU load across 2 cores:
   ```bash
   python3 -c "import multiprocessing as mp; [mp.Process(target=lambda: [i*i for i in range(20000000)]).start() for _ in range(2)]"
   ```
4. **Observe:**
   - Individual CPU core meters spike corresponding to the active cores.
   - The **Time Breakdown** card shows a spike in `User %` time.
   - The **Scheduler Rates** card reflects an increase in process creation forks and context switches.

---

## 7. Running the Automated Test Suite

The project includes an extensive test suite with **220 tests across 45 test files**, verifying all observers, parsers, mathematical engines, event buses, and Qt visualizer widgets.

### Run All Tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### Run Tests in Headless / CI Mode (Offscreen)
If running on a headless server or CI environment without an active display server:
```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -p "test_*.py"
```

### Run Specific Test Modules
```bash
# Test CPU subsystem and delta math
python -m unittest tests/test_cpu_registry.py tests/test_cpu_visualizer.py

# Test File Descriptors, Pipes, and I/O
python -m unittest tests/test_io_discovery.py tests/test_io_registry.py tests/test_io_visualizer.py

# Test Memory and Loadavg
python -m unittest tests/test_memory_discovery.py tests/test_memory_visualizer.py

# Test Process hierarchy & Terminal Session tracking
python -m unittest tests/test_process_tree.py tests/test_focused_cwd_tracker.py

# Test Filesystem Monitor & Inode Models
python -m unittest tests/test_filesystem_monitor.py tests/test_filesystem_object.py
```

---

## 8. Troubleshooting & FAQ

### 1. `ModuleNotFoundError: No module named 'PySide6'`
Ensure you have activated your virtual environment where dependencies were installed:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Qt Platform Plugin Error (`Could not load the Qt platform plugin "xcb"`)
On minimal Linux installations (e.g. fresh Ubuntu/Debian or Docker), some X11/xcb libraries may be missing. Install the required system packages:
```bash
sudo apt update
sudo apt install -y libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
                    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0 \
                    libxcb-xinerama0 libxcb-xinput0 libxkbcommon-x11-0 libegl1
```

### 3. Running under Windows Subsystem for Linux (WSL2)
- **WSL2 on Windows 11**: Includes built-in WSLg. GUI windows will appear automatically without any extra configuration.
- **WSL2 on Windows 10**: Ensure you have an X Server running (such as VcXsrv or Xming) and set your display variable:
  ```bash
  export DISPLAY=$(ip route | grep default | awk '{print $3}'):0
  ```

### 4. Running Without a Monitor / Headless Testing
Use the offscreen Qt platform plugin:
```bash
export QT_QPA_PLATFORM=offscreen
python -m unittest discover -s tests -p "test_*.py"
```

---

## 9. License

This project is developed for educational and systems programming laboratory learning. Licensed under the MIT License.
