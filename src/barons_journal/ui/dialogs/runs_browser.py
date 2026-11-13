"""Dialog listing every run in the journal: open a past run or delete one."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...journal import Run
from ..controller import SessionController
from ..location import Location, location_label
from ..panels._stats import ColumnsModel

DATE_FORMAT = "%Y-%m-%d %H:%M"


def format_time(when: datetime) -> str:
    return when.strftime(DATE_FORMAT)


class _RunsModel(ColumnsModel):
    COLUMNS = ("Character", "Class", "Race", "Last floor", "First seen", "Last seen")

    def __init__(self) -> None:
        super().__init__()
        self._runs: list[Run] = []
        self._live: int | None = None

    def set_runs(self, runs: list[Run], live: int | None) -> None:
        self.beginResetModel()
        self._runs = runs
        self._live = live
        self.endResetModel()

    def run_at(self, row: int) -> Run:
        return self._runs[row]

    def _row_count(self) -> int:
        return len(self._runs)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or not index.isValid():
            return None
        run = self._runs[index.row()]
        return (
            run.character_name + (" (live)" if run.gamekey == self._live else ""),
            run.class_name,
            run.race_name,
            location_label(Location.of_run(run)),
            format_time(run.first_seen),
            format_time(run.last_seen),
        )[index.column()]


def _ask_yes_no(parent: QWidget, message: str) -> bool:
    answer = QMessageBox.question(
        parent,
        "Delete run",
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes


class RunsBrowserDialog(QDialog):
    def __init__(
        self,
        controller: SessionController,
        parent: QWidget | None = None,
        *,
        confirm: Callable[[str], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Runs")
        self.resize(760, 360)
        self._controller = controller
        self._confirm = confirm or (lambda message: _ask_yes_no(self, message))

        self._model = _RunsModel()
        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)

        self.open_button = QPushButton("Open")
        self.delete_button = QPushButton("Delete")
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        buttons.addWidget(close)
        box = QVBoxLayout(self)
        box.addWidget(self.table)
        box.addLayout(buttons)

        self.table.selectionModel().currentRowChanged.connect(self._update_buttons)
        self.table.doubleClicked.connect(lambda _index: self._open())
        self.open_button.clicked.connect(self._open)
        self.delete_button.clicked.connect(self._delete)
        self._refresh()

    def _refresh(self) -> None:
        self._model.set_runs(self._controller.journal.runs(), self._controller.live_gamekey())
        if self._model.rowCount():
            self.table.selectRow(0)
        self._update_buttons()

    def _selected(self) -> Run | None:
        row = self.table.currentIndex().row()
        return self._model.run_at(row) if 0 <= row < self._model.rowCount() else None

    def _update_buttons(self, *_args) -> None:
        run = self._selected()
        self.open_button.setEnabled(run is not None)
        self.delete_button.setEnabled(
            run is not None and run.gamekey != self._controller.live_gamekey()
        )

    def select_gamekey(self, gamekey: int) -> None:
        for row in range(self._model.rowCount()):
            if self._model.run_at(row).gamekey == gamekey:
                self.table.selectRow(row)
                self._update_buttons()
                return
        raise ValueError(f"No such run: {gamekey}")

    def _open(self) -> None:
        run = self._selected()
        if run is None:
            return
        self._controller.open_run(run.gamekey)
        self.accept()

    def _delete(self) -> None:
        run = self._selected()
        if run is None or run.gamekey == self._controller.live_gamekey():
            return
        if self._confirm(f"Delete {run.character_name}'s run and all its notes?"):
            self._controller.delete_run(run.gamekey)
            self._refresh()
