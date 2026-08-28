import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.process.session import TerminalSession
from app.visualizers.session_panel import (
    TerminalSessionWidget,
)


app = QApplication(
    sys.argv
)


sessions = [
    TerminalSession(
        pid=8798,
        ppid=8786,
        command="bash",
        tty="/dev/pts/0",
        cwd=Path(
            "/home/dev/LinuxLab/project"
        ),
    ),
    TerminalSession(
        pid=19691,
        ppid=8786,
        command="bash",
        tty="/dev/pts/1",
        cwd=Path(
            "/home/dev/LinuxLab/permissions_demo"
        ),
    ),
]


widget = TerminalSessionWidget()

widget.update_sessions(
    sessions
)

widget.resize(
    500,
    300
)

widget.show()

sys.exit(
    app.exec()
)
