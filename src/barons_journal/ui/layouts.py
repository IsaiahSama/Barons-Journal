"""The two window arrangements, built from the same panel instances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QTabWidget, QVBoxLayout, QWidget

from .panels.alchemy import AlchemyPanel
from .panels.backpack import BackpackPanel
from .panels.character import CharacterPanel
from .panels.floors import FloorsPanel
from .panels.kills import KillsPanel
from .panels.notes import NotesPanel
from .panels.scrolls import ScrollsPanel
from .settings import AppSettings, LayoutName


@dataclass
class Panels:
    character: CharacterPanel
    notes: NotesPanel
    backpack: BackpackPanel
    kills: KillsPanel
    floors: FloorsPanel
    alchemy: AlchemyPanel
    scrolls: ScrollsPanel

    def flush_notes(self) -> None:
        """Save pending edits in every note editor (Notes panel and Floors tab)."""
        self.notes.flush()
        self.floors.note_editor.flush()

    def all(self) -> list[QWidget]:
        return [
            self.character,
            self.notes,
            self.backpack,
            self.kills,
            self.floors,
            self.alchemy,
            self.scrolls,
        ]


_FOCUS_RATIO = [1000, 2500, 1100]
_DASHBOARD_RATIO = [1000, 1000, 1000]
_DASHBOARD_LEFT_RATIO = [600, 250, 150]
"""Character gets most of the left column's height."""


class LayoutManager:
    def __init__(self, host: QWidget, panels: Panels, settings: AppSettings) -> None:
        self._host = host
        self._panels = panels
        self._settings = settings
        self._box = QVBoxLayout(host)
        self._box.setContentsMargins(0, 0, 0, 0)
        self.current: LayoutName = settings.layout
        self.splitter: QSplitter
        self.tabs: QTabWidget
        self._build(self.current)

    def apply(self, name: LayoutName) -> None:
        self._panels.flush_notes()
        self.save_sizes()
        old = self.splitter
        for panel in self._panels.all():
            panel.setParent(None)
        self._box.removeWidget(old)
        old.setParent(None)
        old.deleteLater()
        self.current = name
        self._settings.layout = name
        self._build(name)

    def set_panel_visible(self, which: Literal["character", "notes"], visible: bool) -> None:
        if which == "character":
            self._settings.character_visible = visible
            self._panels.character.setVisible(visible)
        else:
            self._settings.notes_visible = visible
            self._panels.notes.setVisible(visible)

    def save_sizes(self) -> None:
        """Remember the splitter sizes, unless the window has no real size yet."""
        sizes = self.splitter.sizes()
        if all(s > 0 for s in sizes):
            self._settings.set_splitter_sizes(self.current, sizes)

    def _build(self, name: LayoutName) -> None:
        p = self._panels
        self.tabs = QTabWidget()
        if name == "focus":
            for panel, title in (
                (p.backpack, "Backpack"),
                (p.floors, "Floors"),
                (p.alchemy, "Alchemy"),
                (p.scrolls, "Scrolls"),
                (p.kills, "Kills"),
            ):
                self.tabs.addTab(panel, title)
            splitter = _splitter(Qt.Orientation.Horizontal, p.character, self.tabs, p.notes)
            ratio = _FOCUS_RATIO
        else:
            for panel, title in ((p.floors, "Floors"), (p.alchemy, "Alchemy"), (p.scrolls, "Scrolls")):
                self.tabs.addTab(panel, title)
            left = _splitter(Qt.Orientation.Vertical, p.character, p.backpack, p.kills)
            left.setSizes(_DASHBOARD_LEFT_RATIO)
            left.setStretchFactor(0, 3)
            left.setStretchFactor(1, 2)
            left.setStretchFactor(2, 1)
            splitter = _splitter(Qt.Orientation.Horizontal, left, p.notes, self.tabs)
            ratio = _DASHBOARD_RATIO
        splitter.setSizes(self._settings.splitter_sizes(name) or ratio)
        self.splitter = splitter
        self._box.addWidget(splitter)
        splitter.show()  # a widget added to an already visible host is not shown by itself
        # setParent(None) hid the panels; show the ones that sit directly in a splitter.
        for panel in (p.character, p.notes, p.backpack, p.kills):
            if panel.parent() is not None and isinstance(panel.parent(), QSplitter):
                panel.show()
        p.character.setVisible(self._settings.character_visible)
        p.notes.setVisible(self._settings.notes_visible)


def _splitter(orientation: Qt.Orientation, *children: QWidget) -> QSplitter:
    splitter = QSplitter(orientation)
    for child in children:
        splitter.addWidget(child)
        splitter.setChildrenCollapsible(False)
    return splitter
