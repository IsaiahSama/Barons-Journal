"""Shared base classes for the read-only stats panels."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from ...data import SaveFile
from ..controller import SessionController
from ..state import ViewState

_Index = QModelIndex | QPersistentModelIndex

PAST_MESSAGE = "Stats are only available for the live run"
EMPTY_MESSAGE = "No run loaded"


class StatsPanel(QWidget):
    """Content page for the live run; a message page otherwise.

    Subclasses build their widgets, call ``_init_stack(content)`` and implement ``_render_live``.
    """

    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

    def _init_stack(self, content: QWidget) -> None:
        self.message = QLabel()
        self.stack = QStackedWidget()
        self.stack.addWidget(content)
        self.stack.addWidget(self.message)
        QVBoxLayout(self).addWidget(self.stack)
        self._controller.view_changed.connect(self.render)
        self.render(self._controller.view())

    def render(self, view: ViewState) -> None:
        if view.mode != "live" or view.save is None:
            self.message.setText(PAST_MESSAGE if view.mode == "past" else EMPTY_MESSAGE)
            self.stack.setCurrentWidget(self.message)
            return
        self._render_live(view.save)
        self.stack.setCurrentIndex(0)

    def _render_live(self, save: SaveFile) -> None:
        raise NotImplementedError


class ColumnsModel(QAbstractTableModel):
    """Table model with fixed ``COLUMNS`` headers; subclasses supply ``_row_count`` and ``data``."""

    COLUMNS: tuple[str, ...] = ()

    def _row_count(self) -> int:
        raise NotImplementedError

    def rowCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else self._row_count()

    def columnCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None
