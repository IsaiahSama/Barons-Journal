"""The Qt user interface. Only this package may import Qt."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ..journal import Journal, default_journal_path
from .settings import AppSettings


def run() -> int:
    """Start the app and return its exit code."""
    from .controller import SessionController  # noqa: PLC0415 (built in a later task)
    from .main_window import MainWindow  # noqa: PLC0415 (built in a later task)

    app = QApplication(sys.argv)
    app.setApplicationName("Baron's Journal")
    app.setOrganizationName("barons-journal")
    app.setStyle("Fusion")
    settings = AppSettings()
    with Journal(default_journal_path()) as journal:
        controller = SessionController(journal, settings)
        window = MainWindow(controller, settings)
        window.show()
        return app.exec()
