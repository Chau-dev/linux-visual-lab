"""
UI styling tokens and dark theme stylesheet for Linux Visual Learning Lab.
"""

DARK_THEME_QSS = """
QMainWindow, QWidget {
    background-color: #1a1a22;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

/* -----------------------------------------------------------
   Frames & Panels
   ----------------------------------------------------------- */
QFrame[frameShape="1"], QFrame[frameShape="6"] {
    background-color: #22222c;
    border: 1px solid #2e2e3e;
    border-radius: 6px;
}

QGroupBox {
    background-color: #22222c;
    border: 1px solid #2e2e3e;
    border-radius: 6px;
    margin-top: 24px;
    font-weight: bold;
    padding-top: 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #60a5fa;
    background-color: #2a2a38;
    border: 1px solid #3b3b4f;
    border-radius: 4px;
    margin-left: 8px;
}

/* -----------------------------------------------------------
   Lists and Trees
   ----------------------------------------------------------- */
QListWidget, QTreeWidget {
    background-color: #1e1e28;
    border: 1px solid #2d2d3d;
    border-radius: 6px;
    padding: 4px;
    color: #f1f5f9;
}

QListWidget::item, QTreeWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
    margin-bottom: 2px;
}

QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {
    background-color: #282836;
}

QListWidget::item:selected, QTreeWidget::item:selected,
QListWidget::item:selected:!active, QTreeWidget::item:selected:!active {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    outline: none;
}

QHeaderView::section {
    background-color: #22222c;
    color: #94a3b8;
    font-weight: bold;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #2e2e3e;
}

/* -----------------------------------------------------------
   Scrollbars
   ----------------------------------------------------------- */
QScrollBar:vertical {
    background: #1a1a22;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #374151;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #4b5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #1a1a22;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #374151;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* -----------------------------------------------------------
   Buttons & Inputs
   ----------------------------------------------------------- */
QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: bold;
    padding: 6px 14px;
    border-radius: 4px;
    border: none;
}

QPushButton:hover {
    background-color: #1d4ed8;
}

QPushButton:pressed {
    background-color: #1e40af;
}

QSpinBox, QLineEdit {
    background-color: #1e1e28;
    color: #ffffff;
    border: 1px solid #3b3b4f;
    border-radius: 4px;
    padding: 4px 8px;
}

QSpinBox:focus, QLineEdit:focus {
    border: 1px solid #3b82f6;
}

/* -----------------------------------------------------------
   Tabs
   ----------------------------------------------------------- */
QTabWidget::pane {
    border: 1px solid #2e2e3e;
    border-radius: 6px;
    background-color: #22222c;
    top: -1px;
}

QTabBar::tab {
    background-color: #1e1e28;
    color: #94a3b8;
    font-weight: bold;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #2e2e3e;
    margin-right: 4px;
}

QTabBar::tab:hover {
    background-color: #2a2a38;
    color: #ffffff;
}

QTabBar::tab:selected {
    background-color: #22222c;
    color: #60a5fa;
    border-bottom: 2px solid #3b82f6;
}
"""
