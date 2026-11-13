"""Read-only kill counts for the live run."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableView, QVBoxLayout, QWidget

from ...data import SaveFile
from ._stats import ColumnsModel, StatsPanel

_Index = QModelIndex | QPersistentModelIndex


def _capitalise(name: str) -> str:
    return name[:1].upper() + name[1:]


class KillsModel(ColumnsModel):
    COLUMNS = ("Monster", "Kills")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, int]] = []

    def set_kills(self, kills: dict[str, int]) -> None:
        self.beginResetModel()
        ordered = sorted(kills.items(), key=lambda kv: (-kv[1], kv[0]))
        self._rows = [(_capitalise(name), n) for name, n in ordered]
        self.endResetModel()

    def _row_count(self) -> int:
        return len(self._rows)

    def data(self, index: _Index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        return self._rows[index.row()][index.column()]


class KillsPanel(StatsPanel):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(controller, parent)
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

        self._init_stack(content)

    def _render_live(self, save: SaveFile) -> None:
        kills = save.player.kills_by_monster
        self.model.set_kills(kills)
        self.empty_label.setVisible(not kills)
        self.table.setVisible(bool(kills))
