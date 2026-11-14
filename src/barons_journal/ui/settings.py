"""Persistent UI preferences."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6.QtCore import QByteArray, QSettings

from .theme import ThemeName

LayoutName = Literal["focus", "dashboard"]


class AppSettings:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            self._q = QSettings("barons-journal", "Baron's Journal")
        else:
            self._q = QSettings(str(path), QSettings.Format.IniFormat)

    def _bool(self, key: str, default: bool) -> bool:
        return self._q.value(key, default, type=bool)

    def _path(self, key: str) -> Path | None:
        value = self._q.value(key, "")
        return Path(value) if value else None

    def _set_path(self, key: str, value: Path | None) -> None:
        if value is None:
            self._q.remove(key)
        else:
            self._q.setValue(key, str(value))

    @property
    def layout(self) -> LayoutName:
        return "dashboard" if self._q.value("layout", "focus") == "dashboard" else "focus"

    @layout.setter
    def layout(self, value: LayoutName) -> None:
        self._q.setValue("layout", value)

    @property
    def theme(self) -> ThemeName:
        return "system" if self._q.value("theme", "barony") == "system" else "barony"

    @theme.setter
    def theme(self, value: ThemeName) -> None:
        self._q.setValue("theme", value)

    @property
    def save_dir(self) -> Path | None:
        return self._path("save_dir")

    @save_dir.setter
    def save_dir(self, value: Path | None) -> None:
        self._set_path("save_dir", value)

    @property
    def follow(self) -> Path | None:
        """The save to follow; None means the latest one."""
        return self._path("follow")

    @follow.setter
    def follow(self, value: Path | None) -> None:
        self._set_path("follow", value)

    @property
    def geometry(self) -> QByteArray | None:
        value = self._q.value("geometry")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    @geometry.setter
    def geometry(self, value: QByteArray | None) -> None:
        if value is None:
            self._q.remove("geometry")
        else:
            self._q.setValue("geometry", value)

    @property
    def character_visible(self) -> bool:
        return self._bool("character_visible", True)

    @character_visible.setter
    def character_visible(self, value: bool) -> None:
        self._q.setValue("character_visible", value)

    @property
    def notes_visible(self) -> bool:
        return self._bool("notes_visible", True)

    @notes_visible.setter
    def notes_visible(self, value: bool) -> None:
        self._q.setValue("notes_visible", value)

    def splitter_sizes(self, layout: LayoutName) -> list[int] | None:
        value = self._q.value(f"splitter/{layout}")
        if not value:
            return None
        if not isinstance(value, list):
            value = [value]
        try:
            return [int(v) for v in value]
        except (TypeError, ValueError):
            return None

    def set_splitter_sizes(self, layout: LayoutName, sizes: list[int]) -> None:
        self._q.setValue(f"splitter/{layout}", [int(s) for s in sizes])
