# Linux Visual Learning Lab

An interactive, educational desktop application designed to visualize Linux operating system internals in real time.

> **Architectural North Star:**
> **Observe first. Represent the observed state exactly. Visualize it. Explain only what is directly derivable from that observed state. Never substitute an application-defined model for Linux behavior.**
> 
> The Linux kernel/OS is the absolute authority. The application displays what Linux actually reports without inventing pedagogical storytelling.

### Information Classification Rule

| Type | Examples | Policy |
|---|---|---|
| **Observed State** | `PID=1234`, `st_mode=0100644`, `/proc/<PID>/cwd`, `/proc/<PID>/stat` | ✅ **Required Authority** |
| **Directly Derived State** | `0644 → rw-r--r--`, `6 = 4(r) + 2(w)`, `PPID` tree hierarchy | ✅ **Allowed Derivation** |
| **Invented / Simulated State** | "Process is probably doing X", "File is safe", fake permissions | ❌ **Strictly Forbidden** |

### Identity Highlighting Principle

> **Visual encodings may expose relationships in observed Linux data, but must never alter, simulate, or replace that data.**
> Color is metadata about the display, never about Linux.

Identifiers (`PID`, `PPID`, `PGID`, `SID`, `TPGID`, `UID`, `GID`, `inode`, `device`) use deterministic identity highlighting:
- **Same value $\rightarrow$ Same visual token** across all panels.
- **Different value $\rightarrow$ Different visual token**.
- Underlying domain data remains unchanged (`pid = 1234`, `uid = 1000`).

---

## 1. Architectural Layers & Data Flow

```text
                         ┌─────────────────────┐
                         │       Linux         │
                         │ /proc, stat, FS     │
                         └──────────┬──────────┘
                                    │
                         REAL OBSERVATIONS ONLY
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
        Terminal Observer    Process Observer    Filesystem Observer
        /proc/<pid> (shells) /proc/<pid> (all)   watchdog + stat()
               │                    │                    │
               ▼                    ▼                    ▼
        Session Manager      Process Registry    FS State / Events
               │                    │                    │
               └────────────────────┼────────────────────┘
                                    ▼
                               SystemEvent
                                    │
                                    ▼
                                EventBus
                                    │
               ┌────────────────────┼────────────────────┐
               ▼                    ▼                    ▼
        Session Visualizer    Process & FS Labs    Activity Timeline
               │                    │                    │
               └────────────────────┼────────────────────┘
                                    ▼
                                MainWindow
```

### The 6 Conceptual Layers

```text
Layer 1 — Linux (Kernel, /proc, Filesystem, POSIX stat)
Layer 2 — Observers (Terminal Discovery, ProcessMonitor, FileSystemMonitor)
Layer 3 — State (ProcessRegistry, TerminalSessionRegistry, FocusedSession, Filesystem State)
Layer 4 — Events (EventBus, SystemEvent pub/sub)
Layer 5 — Visualizers (ProcessLabWidget, FilesystemTreeWidget, SelectedObjectInspector, ActivityTimelineWidget, TerminalSessionWidget)
Layer 6 — Application / UI (MainWindow, ContextPanel, Styles, Identity Tokens)
```

**Dependency & Data Flow Direction:**
```text
Linux → Observers → State Managers → Event Bus → Visualizers → UI / MainWindow
```

Visualizers subscribe to events and render state, completely decoupled from low-level Linux observation details.

---

## 2. Directory Structure

```text
linux-visual-lab/
├── app/
│   ├── __init__.py
│   ├── main.py                          # Application entry point
│   │
│   ├── core/                            # Layer 4 & Core Models
│   │   ├── __init__.py
│   │   ├── events.py                    # Standardized SystemEvent dataclass
│   │   ├── event_bus.py                 # Thread-safe EventBus (pub/sub)
│   │   ├── activity.py                  # Thread-safe ActivityTimeline event store
│   │   └── models.py                    # FilesystemObject (POSIX stat domain model)
│   │
│   ├── process/                         # Layer 2 & 3 Process & Terminal Subsystem
│   │   ├── __init__.py
│   │   ├── model.py                     # Canonical Process domain model
│   │   ├── discovery.py                 # /proc/<pid> parser & scanner
│   │   ├── registry.py                  # ProcessRegistry & snapshot diffing engine
│   │   ├── tree.py                      # Real PID/PPID hierarchy constructor
│   │   ├── monitor.py                   # ProcessWorker & ProcessMonitor QThread controller
│   │   ├── session.py                   # TerminalSession dataclass
│   │   ├── session_manager.py           # Shell session state-diff engine
│   │   ├── session_worker.py            # QObject worker polling shells in background
│   │   ├── session_thread.py            # QThread controller for shell sessions
│   │   ├── focused_session.py           # FocusedSession (tracks active terminal)
│   │   ├── focused_cwd.py               # FocusedSessionCwd (resolves /proc/<PID>/cwd)
│   │   └── focused_cwd_tracker.py       # FocusedCwdTracker diff & event publisher
│   │
│   ├── monitors/                        # Layer 2 Filesystem & System Observers
│   │   ├── __init__.py
│   │   └── filesystem.py                # FileSystemMonitor (watchdog + stat diff)
│   │
│   ├── visualizers/                     # Layer 5 Educational Visualizers
│   │   ├── __init__.py
│   │   ├── base.py                      # BaseVisualizer contract
│   │   ├── process_view.py              # ProcessTreeWidget & ProcessInspectorWidget
│   │   ├── session_panel.py             # TerminalSessionWidget (session list & focus)
│   │   ├── activity_timeline.py         # ActivityTimelineWidget (live educational log)
│   │   └── filesystem_view.py           # FilesystemTreeWidget & SelectedObjectInspectorWidget
│   │
│   └── ui/                              # Layer 6 UI Orchestration
│       ├── __init__.py
│       ├── main_window.py               # Thin orchestrator MainWindow with Lab Tabs
│       ├── panels.py                    # ContextPanel ("YOU ARE HERE", breadcrumbs, anatomy)
│       ├── identity.py                  # Deterministic same-value identity color token encoder
│       └── styles.py                    # QSS dark theme stylesheet
│
├── tests/                               # Comprehensive Automated Test Suite (66 tests)
│   ├── __init__.py
│   ├── test_event_bus.py
│   ├── test_filesystem_monitor.py
│   ├── test_filesystem_object.py
│   ├── test_filesystem_tree.py
│   ├── test_focused_session.py
│   ├── test_focused_cwd.py
│   ├── test_focused_cwd_tracker.py
│   ├── test_identity.py
│   ├── test_session_discovery.py
│   ├── test_session_manager.py
│   ├── test_session_worker.py
│   ├── test_session_thread.py
│   ├── test_terminal_session.py
│   ├── test_activity_timeline.py
│   ├── test_process_discovery.py
│   ├── test_process_registry.py
│   ├── test_process_tree.py
│   ├── test_process_monitor.py
│   ├── test_process_events.py
│   ├── test_process_visualizer.py
│   ├── test_process_integration.py
│   ├── test_main_window.py
│   ├── test_robustness.py
│   └── test_integration.py
│
├── requirements.txt
└── .gitignore
```

---

## 3. Standardized Event Taxonomy

Events follow `<domain>.<action>` format:

| Event Type | Description |
|---|---|
| `process.created` | A PID was newly observed in `/proc` snapshot |
| `process.removed` | A PID is no longer present in `/proc` snapshot |
| `process.state_changed` | Process scheduler state transitioned (e.g. `S → R` or `S → T`) |
| `process.cwd_changed` | Process working directory changed |
| `shell.session_created` | A new shell process was spawned |
| `shell.session_removed` | A shell process terminated |
| `shell.cwd_changed` | A shell process changed directory (`cd`) |
| `shell.focused_cwd_changed` | The currently followed shell changed directory |
| `file.created` | New file created |
| `file.modified` | Existing file content modified |
| `file.deleted` | File removed |
| `file.moved` | File renamed or moved |
| `file.permissions_changed` | Inode mode or ownership changed (`chmod`/`chown`) |
| `directory.created` | Directory created |
| `directory.deleted` | Directory deleted |

---

## 4. Key UI Components

1. **Top Context Panel (`ContextPanel`)**:
   - Live location header: `📍 CURRENT LOCATION: /home/dev/LinuxLab/project`
   - Breadcrumb navigation trail: `/ → home → dev → LinuxLab → project`
   - Path anatomy: `ROOT (/) | 1: home | 2: dev | 3: LinuxLab | 4: project`
2. **Left Panel**:
   - `TerminalSessionWidget`: Active shell sessions with focus indicators (`● FOCUSED TERMINAL` vs `○ TERMINAL`), PID, and TTY.
   - `FilesystemTreeWidget`: Hierarchy tree with real-time `🟢 📂 <directory> 👈` location marker following the focused shell.
3. **Center Panel (Tabbed Workspace)**:
   - **Tab 1: `🔬 POSIX Filesystem Lab` (`SelectedObjectInspectorWidget`)**:
     - Real POSIX Metadata (Size, Inode, Links, Timestamps).
     - Real Linux Ownership (UID / GID).
     - 3x3 Permissions Matrix (`OWNER`, `GROUP`, `OTHER` $\times$ `READ`, `WRITE`, `EXECUTE` with ✓/✗).
     - Octal Arithmetic decomposition (e.g. `644` $\rightarrow$ `6 = 4+2`, `4 = 4+0`, `4 = 4+0`).
     - Interactive DAC Kernel Access Evaluator.
   - **Tab 2: `⚡ Linux Process Lab` (`ProcessLabWidget`)**:
     - Live Process Tree & Table with `PID | PPID | PGID | SID | TPGID | STATE | TTY | USER | COMMAND`.
     - Deterministic same-value identity color tokens across PID, PPID, PGID, SID, TPGID.
     - Process Inspector detailing session leadership, process group leadership, foreground status, credentials, and full command line arguments.
4. **Right Panel (`ActivityTimelineWidget`)**:
   - Real-time educational event stream with color-coded category badges, timestamps, target descriptions, search filter, and factual Linux Kernel Insights.

---

## 5. Running & Testing

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Launching the Application
```bash
python app/main.py
```

### Running the Full Test Suite
```bash
python -m unittest discover -s tests -p "test_*.py"
```
