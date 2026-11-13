"""The main window: menus, run header, and the switchable panel layouts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .controller import SessionController
from .dialogs.runs_browser import RunsBrowserDialog
from .dialogs.slot_picker import SlotPickerDialog
from .layouts import LayoutManager, Panels
from .panels.alchemy import AlchemyPanel
from .panels.backpack import BackpackPanel
from .panels.character import CharacterPanel
from .panels.floors import FloorsPanel
from .panels.header import HeaderPanel
from .panels.kills import KillsPanel
from .panels.notes import NotesPanel
from .panels.scrolls import ScrollsPanel
from .settings import AppSettings
from .state import ViewState


class MainWindow(QMainWindow):
    def __init__(self, controller: SessionController, settings: AppSettings) -> None:
        super().__init__()
        self.setWindowTitle("Baron's Journal")
        self._controller = controller
        self._settings = settings

        self.header = HeaderPanel(controller)
        self.panels = Panels(
            character=CharacterPanel(controller),
            notes=NotesPanel(controller),
            backpack=BackpackPanel(controller),
            kills=KillsPanel(controller),
            floors=FloorsPanel(controller),
            alchemy=AlchemyPanel(),
            scrolls=ScrollsPanel(controller),
        )

        empty = QWidget()
        empty_box = QVBoxLayout(empty)
        empty_box.addStretch(1)
        title = QLabel("No Barony saves found")
        title_font = title.font()
        title_font.setPointSize(title_font.pointSize() + 4)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.choose_folder_button = QPushButton("Choose save folder…")
        empty_box.addWidget(title)
        empty_box.addWidget(self.choose_folder_button, 0, Qt.AlignmentFlag.AlignCenter)
        empty_box.addStretch(1)

        layout_host = QWidget()
        self.layouts = LayoutManager(layout_host, self.panels, settings)
        main = QWidget()
        main_box = QVBoxLayout(main)
        main_box.setContentsMargins(0, 0, 0, 0)
        main_box.addWidget(self.header)
        main_box.addWidget(layout_host, 1)

        self.stack = QStackedWidget()
        self.stack.addWidget(empty)
        self.stack.addWidget(main)
        self.setCentralWidget(self.stack)

        self.actions: dict[str, QAction] = {}
        self._build_menus()

        self.choose_folder_button.clicked.connect(self._choose_folder)
        controller.view_changed.connect(self._on_view)
        self._on_view(controller.view())

        geometry = settings.geometry
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _action(self, key: str, text: str, slot=None, *, checkable: bool = False) -> QAction:
        action = QAction(text, self)
        action.setCheckable(checkable)
        if slot is not None:
            action.triggered.connect(slot)
        self.actions[key] = action
        return action

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._action("choose_folder", "Choose save folder…", self._choose_folder))
        quit_action = self._action("quit", "Quit", self.close)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        file_menu.addAction(quit_action)

        runs_menu = bar.addMenu("&Runs")
        runs_menu.addAction(self._action("switch_run", "Switch run…", self._switch_run))
        runs_menu.addAction(self._action("save_slot", "Save slot…", self._pick_slot))
        back = self._action("back_to_live", "Back to live run", self._controller.back_to_live)
        back.setEnabled(False)
        runs_menu.addAction(back)

        view_menu = bar.addMenu("&View")
        layout_menu = view_menu.addMenu("Layout")
        group = QActionGroup(self)
        group.setExclusive(True)
        for key, text, name in (
            ("layout_focus", "Focus", "focus"),
            ("layout_dashboard", "Dashboard", "dashboard"),
        ):
            action = self._action(key, text, checkable=True)
            action.setChecked(self.layouts.current == name)
            action.triggered.connect(lambda _checked=False, n=name: self._apply_layout(n))
            group.addAction(action)
            layout_menu.addAction(action)
        for key, text, which, visible in (
            ("show_character", "Show Character panel", "character", self._settings.character_visible),
            ("show_notes", "Show Notes panel", "notes", self._settings.notes_visible),
        ):
            action = self._action(key, text, checkable=True)
            action.setChecked(visible)
            action.toggled.connect(lambda on, w=which: self.layouts.set_panel_visible(w, on))
            view_menu.addAction(action)

    def _apply_layout(self, name) -> None:
        if name != self.layouts.current:
            self.layouts.apply(name)

    def _on_view(self, view: ViewState) -> None:
        self.stack.setCurrentIndex(0 if view.mode == "empty" else 1)
        self.actions["back_to_live"].setEnabled(view.mode == "past")

    def _ask_for_folder(self) -> Path | None:
        start = self._settings.save_dir
        folder = QFileDialog.getExistingDirectory(
            self, "Choose Barony save folder", str(start) if start else ""
        )
        return Path(folder) if folder else None

    def _switch_run(self) -> None:
        RunsBrowserDialog(self._controller, self).exec()

    def _pick_slot(self) -> None:
        SlotPickerDialog(self._controller, self).exec()

    def _choose_folder(self) -> None:
        folder = self._ask_for_folder()
        if folder is not None:
            self._controller.set_save_dir(folder)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.panels.flush_notes()
        self._settings.geometry = self.saveGeometry()
        self.layouts.save_sizes()
        event.accept()
