"""The always-visible strip: which run and floor, plus the one banner."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..controller import SessionController
from ..location import location_label, snapshot_caption
from ..state import Banner, ViewState

_BUTTON_TEXT = {"new_run": "View live run", "past": "Back to live run"}


class HeaderPanel(QWidget):
    def __init__(self, controller: SessionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        self.title = QLabel()
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.caption = QLabel()
        self.banner_label = QLabel()
        self.banner_label.setWordWrap(True)
        self.banner_button = QPushButton()
        self.banner = QFrame()
        self.banner.setFrameShape(QFrame.Shape.StyledPanel)
        row = QHBoxLayout(self.banner)
        row.addWidget(self.banner_label, 1)
        row.addWidget(self.banner_button)
        self.banner.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.caption)
        layout.addWidget(self.banner)

        self.banner_button.clicked.connect(controller.back_to_live)
        controller.view_changed.connect(self.render)
        controller.banner_changed.connect(self.show_banner)
        self.render(controller.view())
        self.show_banner(controller.banner())

    def render(self, view: ViewState) -> None:
        if view.mode == "live" and view.save is not None and view.location is not None:
            save = view.save
            player = save.player
            self.title.setText(
                f"{player.name} · {player.race_name} {player.class_name}"
                f" · Lv {player.stats.level} · {location_label(view.location)}"
            )
            self.caption.setText(snapshot_caption(save))
        elif view.mode == "past" and view.run is not None and view.location is not None:
            run = view.run
            self.title.setText(
                f"{run.character_name} · {run.race_name} {run.class_name}"
                f" · {location_label(view.location)}"
            )
            self.caption.setText(f"Last seen {run.last_seen:%Y-%m-%d %H:%M}")
        else:
            self.title.setText("No run loaded")
            self.caption.setText("")

    def show_banner(self, banner: Banner | None) -> None:
        if banner is None:
            self.banner.hide()
            return
        self.banner_label.setText(banner.text)
        text = _BUTTON_TEXT.get(banner.kind)
        if text is None:
            self.banner_button.hide()
        else:
            self.banner_button.setText(text)
            self.banner_button.show()
        self.banner.show()
