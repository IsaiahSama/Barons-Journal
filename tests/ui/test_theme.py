import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from barons_journal.ui import theme
from barons_journal.ui.main_window import MainWindow
from barons_journal.ui.settings import AppSettings


@pytest.fixture
def app(qapp):
    yield qapp
    theme.apply_theme(qapp, "system")


def test_default_theme_is_barony(settings):
    assert settings.theme == "barony"


def test_theme_round_trip(tmp_path):
    path = tmp_path / "settings.ini"
    AppSettings(path).theme = "system"
    assert AppSettings(path).theme == "system"


def test_barony_theme_sets_palette_and_stylesheet(app):
    theme.apply_theme(app, "barony")
    assert app.palette().color(QPalette.ColorRole.Window) == QColor(theme.STONE)
    assert app.palette().color(QPalette.ColorRole.Text) == QColor(theme.PARCHMENT)
    assert "hpBar" in app.styleSheet()
    assert "QProgressBar#hungerBar::chunk" in app.styleSheet()
    assert "QProgressBar#goldBar::chunk" in app.styleSheet()


def test_system_theme_clears_stylesheet(app):
    theme.apply_theme(app, "barony")
    theme.apply_theme(app, "system")
    assert app.styleSheet() == ""
    assert app.palette() == app.style().standardPalette()


def test_theme_menu_switches_and_persists(app, controller, settings, qtbot):
    controller.start()
    window = MainWindow(controller, settings)
    qtbot.addWidget(window)
    assert window.actions["theme_barony"].isChecked()
    window.actions["theme_system"].trigger()
    assert settings.theme == "system"
    assert QApplication.instance().styleSheet() == ""
    window.actions["theme_barony"].trigger()
    assert settings.theme == "barony"
    assert QApplication.instance().styleSheet() == theme.STYLESHEET


def test_hp_and_mp_bars_are_named_for_the_stylesheet(app, controller, settings, qtbot):
    controller.start()
    window = MainWindow(controller, settings)
    qtbot.addWidget(window)
    assert window.panels.character.hp_bar.objectName() == "hpBar"
    assert window.panels.character.mp_bar.objectName() == "mpBar"
