"""Read-only kill counts for the live run."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QStackedWidget, QTableView, QVBoxLayout, QWidget

from ..controller import SessionController
from ..state import ViewState

_Index = QModelIndex | QPersistentModelIndex


def _capitalise(name: str) -> str:
    return name[:1].upper() + name[1:]


class KillsModel(QAbstractTableModel):
    COLUMNS = ("Monster", "Kills")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, int]] = []

    def set_kills(self, kills: dict[str, int]) -> None:
        self.beginResetModel()
        ordered = sorted(kills.items(), key=lambda kv: (-kv[1], kv[0]))
        self._rows = [(_capitalise(name), n) for name, n in ordered]
        self.endResetModel()

    def rowCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index: _Index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        return self._rows[index.row()][index.column()]


class KillsPanel(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = KillsModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.empty_label = QLabel("No kills yet")

        content = QWidget()
        inner = QVBoxLayout(content)
        inner.addWidget(self.table)
        inner.addWidget(self.empty_label)

        self.message = QLabel()
        self.stack = QStackedWidget()
        self.stack.addWidget(content)
        self.stack.addWidget(self.message)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        controller.view_changed.connect(self.render)
        self.render(controller.view())

    def render(self, view: ViewState) -> None:
        if view.mode != "live" or view.save is None:
            self.message.setText(
                "Stats are only available for the live run" if view.mode == "past" else "No run loaded"
            )
            self.stack.setCurrentWidget(self.message)
            return
        kills = view.save.player.kills_by_monster
        self.model.set_kills(kills)
        self.empty_label.setVisible(not kills)
        self.table.setVisible(bool(kills))
        self.stack.setCurrentIndex(0)
