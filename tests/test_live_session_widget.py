import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.event_bus import EventBus

from app.process.session_manager import (
    TerminalSessionManager,
)

from app.visualizers.session_panel import (
    TerminalSessionWidget,
)


class SessionWindow(QWidget):

    def handle_session_selected(
        self,
        pid
    ):

        print(
            "FOCUSED SESSION PID:",
            pid
        )

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Linux Visual Lab - Terminal Sessions"
        )

        self.resize(
            600,
            500
        )

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "🖥 TERMINAL SESSIONS"
        )

        title.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: bold;
                padding: 8px;
            }
            """
        )

        layout.addWidget(
            title
        )

        self.session_widget = (
            TerminalSessionWidget()
        )
        self.session_widget.session_selected.connect(
            self.handle_session_selected
        )

        layout.addWidget(
            self.session_widget
        )

        self.event_bus = EventBus()

        self.manager = (
            TerminalSessionManager(
                self.event_bus
            )
        )

        self.event_bus.subscribe(
            "shell.session_created",
            self.handle_session_event
        )

        self.event_bus.subscribe(
            "shell.session_removed",
            self.handle_session_event
        )

        self.event_bus.subscribe(
            "shell.cwd_changed",
            self.handle_session_event
        )

        self.refresh()

        self.timer = QTimer(
            self
        )

        self.timer.setInterval(
            500
        )

        self.timer.timeout.connect(
            self.refresh
        )

        self.timer.start()

    def handle_session_event(
        self,
        event
    ):

        self.refresh()

    def refresh(self):

        self.manager.refresh()

        sessions = (
            self.manager.sessions()
        )

        self.session_widget.update_sessions(
            sessions
        )

    def closeEvent(
        self,
        event
    ):

        self.timer.stop()

        event.accept()


def main():

    app = QApplication(
        sys.argv
    )

    window = SessionWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":

    sys.exit(
        main()
    )
