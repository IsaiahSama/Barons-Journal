"""App-wide look: a dark Barony-style theme, or the plain system one."""

from __future__ import annotations

from typing import Literal

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ThemeName = Literal["barony", "system"]
THEMES: tuple[tuple[ThemeName, str], ...] = (("barony", "Barony"), ("system", "System"))

# Stone, wood, bronze trim, parchment text and gold accents, as in the game's menus.
STONE = "#1b1714"
WOOD = "#2a221c"
WOOD_ALT = "#312820"
PAGE = "#221c17"
RAISED = "#3a2e24"
BRONZE = "#6b5434"
PARCHMENT = "#e6d8b8"
FADED = "#8a7c64"
GOLD = "#e0a33a"
GOLD_DARK = "#8c5f1c"
HP_RED = "#c0392b"
MP_BLUE = "#3b6fd1"


def _palette() -> QPalette:
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: STONE,
        QPalette.ColorRole.WindowText: PARCHMENT,
        QPalette.ColorRole.Base: WOOD,
        QPalette.ColorRole.AlternateBase: WOOD_ALT,
        QPalette.ColorRole.Text: PARCHMENT,
        QPalette.ColorRole.PlaceholderText: FADED,
        QPalette.ColorRole.Button: RAISED,
        QPalette.ColorRole.ButtonText: PARCHMENT,
        QPalette.ColorRole.BrightText: GOLD,
        QPalette.ColorRole.Highlight: GOLD_DARK,
        QPalette.ColorRole.HighlightedText: "#fff4dc",
        QPalette.ColorRole.ToolTipBase: RAISED,
        QPalette.ColorRole.ToolTipText: PARCHMENT,
        QPalette.ColorRole.Link: GOLD,
        QPalette.ColorRole.LinkVisited: GOLD_DARK,
        QPalette.ColorRole.Light: "#5a4630",
        QPalette.ColorRole.Midlight: "#4a3a2a",
        QPalette.ColorRole.Mid: BRONZE,
        QPalette.ColorRole.Dark: "#120f0d",
        QPalette.ColorRole.Shadow: "#000000",
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    disabled = QPalette.ColorGroup.Disabled
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(disabled, role, QColor(FADED))
    return p


STYLESHEET = f"""
QMenuBar {{ background: {WOOD}; border-bottom: 1px solid {BRONZE}; }}
QMenuBar::item:selected {{ background: {RAISED}; color: {GOLD}; }}
QMenu {{ background: {WOOD}; border: 1px solid {BRONZE}; }}
QMenu::item:selected {{ background: {RAISED}; color: {GOLD}; }}
QMenu::separator {{ height: 1px; background: {BRONZE}; margin: 4px 8px; }}

QTabWidget::pane {{ border: 1px solid {BRONZE}; top: -1px; }}
QTabBar::tab {{
    background: {WOOD}; color: {FADED};
    border: 1px solid {BRONZE}; border-bottom: none;
    padding: 5px 14px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {RAISED}; color: {GOLD}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ color: {PARCHMENT}; }}

QHeaderView::section {{
    background: {RAISED}; color: {GOLD};
    border: none; border-right: 1px solid {BRONZE}; border-bottom: 1px solid {BRONZE};
    padding: 3px 6px; font-weight: bold;
}}
QTableView, QTableWidget, QListView, QTreeView {{
    border: 1px solid {BRONZE}; gridline-color: #3d3126;
}}
QPlainTextEdit, QTextEdit, QLineEdit {{
    background: {PAGE}; border: 1px solid {BRONZE}; padding: 2px;
    selection-background-color: {GOLD_DARK};
}}
QPlainTextEdit:focus, QTextEdit:focus, QLineEdit:focus, QComboBox:focus {{ border-color: {GOLD}; }}

QPushButton {{
    background: {RAISED}; border: 1px solid {BRONZE}; border-radius: 3px; padding: 4px 12px;
}}
QPushButton:hover {{ border-color: {GOLD}; color: {GOLD}; }}
QPushButton:pressed {{ background: {WOOD}; }}
QComboBox {{ background: {RAISED}; border: 1px solid {BRONZE}; border-radius: 3px; padding: 2px 6px; }}

QSplitter::handle {{ background: {BRONZE}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}

QScrollBar:vertical {{ background: {STONE}; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: {STONE}; height: 12px; margin: 0; }}
QScrollBar::handle {{ background: {BRONZE}; border-radius: 4px; margin: 2px; }}
QScrollBar::handle:vertical {{ min-height: 24px; }}
QScrollBar::handle:horizontal {{ min-width: 24px; }}
QScrollBar::handle:hover {{ background: {GOLD_DARK}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QProgressBar {{
    background: #120f0d; border: 1px solid {BRONZE}; border-radius: 3px;
    text-align: center; color: #fff4dc; font-weight: bold; min-height: 16px;
}}
QProgressBar::chunk {{ border-radius: 2px; }}
QProgressBar#hpBar::chunk {{ background: {HP_RED}; }}
QProgressBar#mpBar::chunk {{ background: {MP_BLUE}; }}

QLabel#runTitle {{ color: {GOLD}; font-size: 14pt; font-weight: bold; }}
QLabel[role="section"] {{ color: {GOLD}; font-weight: bold; padding-top: 6px; }}
QLabel[role="muted"] {{ color: {FADED}; }}
QToolTip {{ background: {RAISED}; color: {PARCHMENT}; border: 1px solid {BRONZE}; }}
"""


def apply_theme(app: QApplication, name: ThemeName) -> None:
    """Restyle the whole app; safe to call again to switch themes live."""
    if name == "barony":
        app.setPalette(_palette())
        app.setStyleSheet(STYLESHEET)
    else:
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet("")
