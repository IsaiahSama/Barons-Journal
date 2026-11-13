"""Read-only backpack and learned spells for the live run."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...data import SaveFile
from ...data.models import Item
from ._stats import ColumnsModel, StatsPanel

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


class BackpackModel(ColumnsModel):
    COLUMNS = ("Item", "Count", "Condition", "Blessing")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[Item] = []

    def set_items(self, items: list[Item]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def _row_count(self) -> int:
        return len(self._items)

    def data(self, index: _Index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        item = self._items[index.row()]
        return (item.name, item.count, item.status_name, blessing_text(item))[index.column()]


class BackpackPanel(StatsPanel):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(controller, parent)
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

        self._init_stack(content)

    def _render_live(self, save: SaveFile) -> None:
        inventory = save.player.inventory
        rows = [i for i in inventory if not i.equipped and not i.is_spell]
        self.model.set_items(rows)
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.spells.clear()
        self.spells.addItems([i.name for i in inventory if i.is_spell])
