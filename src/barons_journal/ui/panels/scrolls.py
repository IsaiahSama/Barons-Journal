"""Scroll identification: one row per unidentified label, plus what each scroll can still be."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...journal import JournalError
from ...reference import SCROLL_LABELS
from ..controller import SessionController
from ..state import ViewState

PLACEHOLDER = "Pick…"


class ScrollsPanel(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._gamekey: int | None = None
        self._rows: dict[str, tuple[QComboBox | None, QPushButton | None]] = {}

        self.empty_label = QLabel("No run loaded")
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.remaining_list = QListWidget()

        self._content = QWidget()
        self._grid = QGridLayout(self._content)
        self._grid.setColumnStretch(2, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._content)

        self._body = QWidget()
        body = QHBoxLayout(self._body)
        body.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        left.addWidget(self.error_label)
        left.addWidget(scroll, 1)
        body.addLayout(left, 3)
        body.addWidget(self.remaining_list, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.empty_label)
        layout.addWidget(self._body, 1)

        controller.view_changed.connect(self._on_view_changed)
        controller.scrolls_changed.connect(self._on_scrolls_changed)
        self.render(controller.view())

    def row_widgets(self, label: str) -> tuple[QComboBox | None, QPushButton | None]:
        return self._rows.get(label, (None, None))

    def _on_view_changed(self, view: ViewState) -> None:
        self.error_label.hide()
        self.render(view)

    def _on_scrolls_changed(self, gamekey: int) -> None:
        if gamekey == self._gamekey:
            self.render(self._controller.view())

    def render(self, view: ViewState) -> None:
        self._clear()
        run = view.run
        self._gamekey = run.gamekey if run is not None else None
        self.empty_label.setVisible(run is None)
        self._body.setVisible(run is not None)
        if run is None:
            return
        progress = self._controller.scroll_progress(run.gamekey)
        for row, label in enumerate(SCROLL_LABELS):
            self._grid.addWidget(QLabel(label), row, 0)
            scroll = progress.identified.get(label)
            if scroll is not None:
                undo = QPushButton("Undo")
                undo.setEnabled(view.editable)
                undo.clicked.connect(lambda _=False, lb=label: self._undo(lb))
                self._grid.addWidget(QLabel(scroll.name), row, 1)
                self._grid.addWidget(QLabel(scroll.effect), row, 2)
                self._grid.addWidget(undo, row, 3)
                self._rows[label] = (None, undo)
            else:
                combo = QComboBox()
                combo.addItem(PLACEHOLDER)
                for candidate in progress.candidates(label):
                    combo.addItem(candidate.name, candidate.item_id)
                combo.setEnabled(view.editable)
                combo.activated.connect(lambda i, lb=label, cb=combo: self._picked(lb, cb, i))
                self._grid.addWidget(combo, row, 1)
                self._rows[label] = (combo, None)
        for scroll, n in progress.remaining.items():
            self.remaining_list.addItem(f"{scroll.name}: {n} label{'s' if n != 1 else ''} left")

    def _clear(self) -> None:
        while (item := self._grid.takeAt(0)) is not None:
            if item.widget() is not None:
                item.widget().deleteLater()
        self._rows = {}
        self.remaining_list.clear()

    def _picked(self, label: str, combo: QComboBox, index: int) -> None:
        item_id = combo.itemData(index)
        if index <= 0 or item_id is None or self._gamekey is None:
            return
        try:
            self._controller.identify_scroll(self._gamekey, label, item_id)
        except JournalError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            combo.setCurrentIndex(0)
            return
        self.error_label.hide()

    def _undo(self, label: str) -> None:
        if self._gamekey is None:
            return
        try:
            self._controller.forget_scroll(self._gamekey, label)
        except JournalError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return
        self.error_label.hide()
