"""Alchemy reference: the base x secondary mixing grid and a reverse recipe lookup."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QComboBox, QHeaderView, QListWidget, QTableView, QVBoxLayout, QWidget

from ...data.ids import ITEMS
from ...reference import BASE_INGREDIENTS, RECIPES, SECONDARY_INGREDIENTS, mix, recipes_making

_Index = QModelIndex | QPersistentModelIndex


def _capitalise(text: str) -> str:
    return text[:1].upper() + text[1:]


def _cell_text(base: int, secondary: int) -> str:
    result = mix(base, secondary)
    match result.kind:
        case "potion":
            return ITEMS.label(result.potion)
        case "duplicate":
            return f"×2 {ITEMS.label(result.potion)}"
        case _:
            return result.kind


class AlchemyModel(QAbstractTableModel):
    """Rows are base ingredients, columns are secondary ingredients."""

    def rowCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(BASE_INGREDIENTS)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(SECONDARY_INGREDIENTS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and index.isValid():
            return _cell_text(BASE_INGREDIENTS[index.row()], SECONDARY_INGREDIENTS[index.column()])
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        ids = SECONDARY_INGREDIENTS if orientation == Qt.Orientation.Horizontal else BASE_INGREDIENTS
        return _capitalise(ITEMS.label(ids[section]))


class AlchemyPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.grid = QTableView()
        self.grid.setModel(AlchemyModel())
        self.grid.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.grid.setWordWrap(True)

        self.result_combo = QComboBox()
        results = {r.result_name: r.result for r in RECIPES}
        self._result_ids = results
        for name in sorted(results):
            self.result_combo.addItem(name, results[name])
        self.recipes_list = QListWidget()
        self.result_combo.currentTextChanged.connect(self._show_recipes)

        layout = QVBoxLayout(self)
        layout.addWidget(self.grid, 3)
        layout.addWidget(self.result_combo)
        layout.addWidget(self.recipes_list, 1)
        self._show_recipes(self.result_combo.currentText())

    def _show_recipes(self, result_name: str) -> None:
        self.recipes_list.clear()
        for recipe in recipes_making(self._result_ids[result_name]):
            self.recipes_list.addItem(f"{recipe.base_name} + {recipe.secondary_name}")
