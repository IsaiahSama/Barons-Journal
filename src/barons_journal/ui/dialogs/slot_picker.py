"""Dialog choosing which save the app follows: the newest one, or a specific slot."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...data import InvalidSaveError, SaveSlot, load_save
from ..controller import SessionController
from ..panels._stats import ColumnsModel
from .runs_browser import format_time

AUTOMATIC = "Most recent save (automatic)"
UNREADABLE = "unreadable"


def _character_name(slot: SaveSlot) -> str:
    try:
        return load_save(slot.path).player.name
    except (InvalidSaveError, FileNotFoundError):
        return UNREADABLE


class _SlotsModel(ColumnsModel):
    COLUMNS = ("Slot", "Mode", "Modded", "Modified", "Character")

    def __init__(self, slots: list[SaveSlot]) -> None:
        super().__init__()
        self.slots = slots
        self._names = [_character_name(slot) for slot in slots]

    def _row_count(self) -> int:
        return len(self.slots) + 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        if index.row() == 0:
            return AUTOMATIC if index.column() == 0 else ""
        slot = self.slots[index.row() - 1]
        return (
            str(slot.slot),
            "Multiplayer" if slot.multiplayer else "Singleplayer",
            "Modded" if slot.modded else "",
            format_time(slot.modified),
            self._names[index.row() - 1],
        )[index.column()]


class SlotPickerDialog(QDialog):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save slot")
        self.resize(620, 300)
        self._controller = controller

        self._model = _SlotsModel(controller.saves())
        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSpan(0, 0, 1, len(_SlotsModel.COLUMNS))

        self.choose_button = QPushButton("Choose")
        self.choose_button.setDefault(True)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        close.rejected.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.choose_button)
        buttons.addWidget(close)
        box = QVBoxLayout(self)
        box.addWidget(self.table)
        box.addLayout(buttons)

        self.choose_button.clicked.connect(self._choose)
        self.table.doubleClicked.connect(lambda _index: self._choose())

        pinned = controller.following()
        paths = [slot.path for slot in self._model.slots]
        self.select_row(paths.index(pinned) + 1 if pinned in paths else 0)

    def select_row(self, row: int) -> None:
        self.table.selectRow(row)
        self.table.setCurrentIndex(self._model.index(row, 0))

    def _choose(self) -> None:
        row = self.table.currentIndex().row()
        if row <= 0:
            self._controller.follow_latest()
        else:
            self._controller.follow_path(self._model.slots[row - 1].path)
        self.accept()
