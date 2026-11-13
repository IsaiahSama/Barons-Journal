import os
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTabBar,
    QWidget,
)

from barons_journal.data import load_save  # noqa: E402
from barons_journal.ui.settings import AppSettings  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return AppSettings(tmp_path / "settings.ini")


@pytest.fixture
def journal_path(tmp_path):
    return tmp_path / "journal.sqlite3"


@pytest.fixture
def save_dir(tmp_path, sample_save_path):
    folder = tmp_path / "saves"
    folder.mkdir()
    shutil.copy(sample_save_path, folder / "savegame0.baronysave")
    return folder


@pytest.fixture
def secret_save(secret_save_path):
    return load_save(secret_save_path)


def _model_text(view: QAbstractItemView) -> list[str]:
    out: list[str] = []
    model = view.model()
    if model is None:
        return out
    roles = (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole)
    for section in range(model.columnCount()):
        for role in roles:
            out.append(str(model.headerData(section, Qt.Orientation.Horizontal, role) or ""))
    for section in range(model.rowCount()):
        for role in roles:
            out.append(str(model.headerData(section, Qt.Orientation.Vertical, role) or ""))
    for row in range(model.rowCount()):
        for col in range(model.columnCount()):
            index = model.index(row, col)
            for role in roles:
                out.append(str(model.data(index, role) or ""))
    return out


@pytest.fixture
def all_visible_text():
    """Return a function joining all user-visible text under a widget."""

    def collect(widget: QWidget) -> str:
        parts: list[str] = []
        for w in [widget, *widget.findChildren(QWidget)]:
            parts.append(w.toolTip())
            if isinstance(w, QLabel):
                parts.append(w.text())
            if isinstance(w, QAbstractButton):
                parts.append(w.text())
            if isinstance(w, QLineEdit):
                parts.append(w.text())
            if isinstance(w, QPlainTextEdit):
                parts.append(w.toPlainText())
            if isinstance(w, QComboBox):
                parts.extend(w.itemText(i) for i in range(w.count()))
            if isinstance(w, QTabBar):
                parts.extend(w.tabText(i) for i in range(w.count()))
            if isinstance(w, QAbstractItemView):
                parts.extend(_model_text(w))
        return "\n".join(p for p in parts if p)

    return collect
