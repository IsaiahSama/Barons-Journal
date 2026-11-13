"""Read-only backpack and learned spells for the live run."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...data.models import Item
from ..controller import SessionController
from ..state import ViewState

_Index = QModelIndex | QPersistentModelIndex


def blessing_text(item: Item) -> str:
    """Blessing and curse are only known once the item is identified."""
    if not item.identified:
        return ""
    b = item.beatitude
    if b > 0:
        return f"+{b} blessed"
    if b < 0:
        return f"{b} cursed"
    return "uncursed"


class BackpackModel(QAbstractTableModel):
    COLUMNS = ("Item", "Count", "Condition", "Blessing")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[Item] = []

    def set_items(self, items: list[Item]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def rowCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index: _Index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        item = self._items[index.row()]
        return (item.name, item.count, item.status_name, blessing_text(item))[index.column()]


class BackpackPanel(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = BackpackModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.empty_label = QLabel("Backpack is empty")
        self.spells = QListWidget()

        content = QWidget()
        inner = QVBoxLayout(content)
        inner.addWidget(self.table)
        inner.addWidget(self.empty_label)
        inner.addWidget(QLabel("Spells"))
        inner.addWidget(self.spells)

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
        inventory = view.save.player.inventory
        rows = [i for i in inventory if not i.equipped and not i.is_spell]
        self.model.set_items(rows)
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.spells.clear()
        self.spells.addItems([i.name for i in inventory if i.is_spell])
        self.stack.setCurrentIndex(0)
