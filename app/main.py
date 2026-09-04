import sys
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.styles import DARK_THEME_QSS


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
