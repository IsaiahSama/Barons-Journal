"""The Qt user interface. Only this package may import Qt."""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping

from PySide6.QtWidgets import QApplication

from ..journal import Journal, default_journal_path
from .settings import AppSettings
from .theme import apply_theme


def prefer_xwayland(environ: MutableMapping[str, str], platform: str) -> None:
    """Use XWayland on Wayland: native Wayland lets no app keep its windows on top."""
    if not (platform.startswith("linux") and environ.get("WAYLAND_DISPLAY")):
        return
    # Desktops like COSMIC export "wayland;xcb" to every app, so a value made only of wayland/xcb
    # is the session's default, not a choice for this app. Anything else (e.g. offscreen) is kept.
    current = environ.get("QT_QPA_PLATFORM", "")
    if set(filter(None, current.split(";"))) <= {"wayland", "xcb"}:
        environ["QT_QPA_PLATFORM"] = "xcb;wayland"


def run() -> int:
    """Start the app and return its exit code."""
    from .controller import SessionController  # noqa: PLC0415
    from .main_window import MainWindow  # noqa: PLC0415

    prefer_xwayland(os.environ, sys.platform)
    app = QApplication(sys.argv)
    app.setApplicationName("Baron's Journal")
    app.setOrganizationName("barons-journal")
    app.setStyle("Fusion")
    settings = AppSettings()
    apply_theme(app, settings.theme)
    with Journal(default_journal_path()) as journal:
        controller = SessionController(journal, settings)
        window = MainWindow(controller, settings)
        controller.start()
        if settings.geometry is None:
            window.showMaximized()
        else:
            window.show()
        window.popouts.restore()
        return app.exec()
