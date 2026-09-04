from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
)

from app.process.session import TerminalSession


class TerminalSessionWidget(QListWidget):
    """
    Displays currently known terminal sessions.

    The widget preserves the user's scroll position and
    selection while session information is refreshed.
    """

    session_selected = Signal(int)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWordWrap(True)
        self.setAlternatingRowColors(True)
        self.setSpacing(6)

        self.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )

        self.current_pid = None

        self.currentItemChanged.connect(
            self.handle_selection_changed
        )

    # ========================================================
    # Update sessions
    # ========================================================

    def update_sessions(
        self,
        sessions: list[TerminalSession] | dict[int, TerminalSession],
    ):
        """
        Update the displayed sessions while preserving:

        - selected PID
        - scrollbar position
        - session row order
        """

        if isinstance(sessions, dict):
            session_list = list(sessions.values())
        else:
            session_list = list(sessions)

        session_list = sorted(
            session_list,
            key=lambda session: session.pid
        )

        new_pids = [
            session.pid
            for session in session_list
        ]


        current_pids = [
            self.item(index).data(
                Qt.ItemDataRole.UserRole
            )
            for index in range(
                self.count()
            )
        ]

        # ----------------------------------------------------
        # If the set of sessions hasn't changed, don't rebuild
        # the list. Just update the text of existing rows.
        # ----------------------------------------------------

        if new_pids == current_pids:

            scrollbar = self.verticalScrollBar()

            saved_value = scrollbar.value()

            blocker = QSignalBlocker(
                self
            )

            try:

                for index, session in enumerate(
                    session_list
                ):

                    item = self.item(
                        index
                    )

                    self.update_item(
                        item,
                        session
                    )

            finally:

                del blocker

            scrollbar.setValue(
                saved_value
            )

            self.update_focus_markers()

            return

        # ----------------------------------------------------
        # Structural change: a shell was created or removed.
        # ----------------------------------------------------

        scrollbar = self.verticalScrollBar()

        saved_value = scrollbar.value()

        previous_pid = self.current_pid

        blocker = QSignalBlocker(
            self
        )

        selected_item = None

        try:

            self.clear()

            for session in session_list:

                item = self.create_item(
                    session
                )

                self.addItem(
                    item
                )


                if session.pid == previous_pid:

                    selected_item = item

        finally:

            del blocker

        # ----------------------------------------------------
        # Restore selection.
        # ----------------------------------------------------

        if selected_item is not None:

            self.setCurrentItem(
                selected_item
            )

        elif self.count() > 0:

            # If there is no current selection yet,
            # select the first session once.
            first_item = self.item(
                0
            )

            self.setCurrentItem(
                first_item
            )

        else:

            self.current_pid = None

        # ----------------------------------------------------
        # Restore approximate scroll position.
        # ----------------------------------------------------

        scrollbar.setValue(
            min(
                saved_value,
                scrollbar.maximum()
            )
        )

        self.update_focus_markers()

    # ========================================================
    # Create item
    # ========================================================

    def create_item(
        self,
        session: TerminalSession
    ):

        item = QListWidgetItem()

        item.setData(
            Qt.ItemDataRole.UserRole,
            session.pid
        )

        self.update_item(
            item,
            session
        )

        return item

    # ========================================================
    # Update item
    # ========================================================

    def update_item(
        self,
        item,
        session: TerminalSession
    ):

        tty = (
            session.tty
            if session.tty
            else "No TTY"
        )

        cwd = (
            str(session.cwd)
            if session.cwd
            else "Unknown"
        )

        # Keep the first line as the focus indicator.
        if session.pid == self.current_pid:

            focus_text = (
                "●  FOCUSED TERMINAL"
            )

        else:

            focus_text = (
                "○  TERMINAL"
            )

        text = (
            f"{focus_text}\n"
            f"    {session.command} • "
            f"PID {session.pid}\n"
            f"    {tty}\n"
            f"    {cwd}"
        )

        item.setText(
            text
        )

        item.setToolTip(
            (
                f"PID: {session.pid}\n"
                f"PPID: {session.ppid}\n"
                f"TTY: {tty}\n"
                f"CWD: {cwd}"
            )
        )

        item.setSizeHint(
            item.sizeHint()
        )

    # ========================================================
    # Selection changed
    # ========================================================

    def handle_selection_changed(
        self,
        current,
        previous
    ):

        if current is None:

            return

        pid = current.data(
            Qt.ItemDataRole.UserRole
        )

        if pid is None:

            return

        # Don't generate another event if this
        # is already the focused session.
        if pid == self.current_pid:

            return

        self.current_pid = pid

        self.update_focus_markers()

        self.session_selected.emit(
            pid
        )

    # ========================================================
    # Update focus markers
    # ========================================================

    def update_focus_markers(
        self
    ):

        blocker = QSignalBlocker(
            self
        )

        try:

            for index in range(
                self.count()
            ):

                item = self.item(
                    index
                )

                pid = item.data(
                    Qt.ItemDataRole.UserRole
                )

                lines = (
                    item.text().splitlines()
                )

                if len(lines) < 1:

                    continue

                if pid == self.current_pid:

                    lines[0] = (
                        "●  FOCUSED TERMINAL"
                    )

                else:

                    lines[0] = (
                        "○  TERMINAL"
                    )

                item.setText(
                    "\n".join(lines)
                )

        finally:

            del blocker

    # ========================================================
    # Selected PID
    # ========================================================

    def selected_pid(
        self
    ):

        item = self.currentItem()

        if item is None:

            return None

        return item.data(
            Qt.ItemDataRole.UserRole
        )
