from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from archivetools.gui.theme import LIGHT, ThemeColors

_NAV_ITEMS = ["Recent", "Extract", "Create", "Batch", "Convert"]


class Sidebar(QWidget):
    """Left navigation sidebar with exclusive nav buttons and a settings gear."""

    page_changed = Signal(int)
    settings_clicked = Signal()
    theme_toggled = Signal()

    def __init__(
        self,
        colors: ThemeColors | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._build_ui()
        self.set_theme(colors or LIGHT)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 14, 8, 10)
        layout.setSpacing(2)

        self._title = QLabel("ARCHIVETOOLS")
        self._title.setObjectName("sidebarTitle")
        layout.addWidget(self._title)
        layout.addSpacing(10)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        for i, label in enumerate(_NAV_ITEMS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFlat(True)
            self._buttons.append(btn)
            self._group.addButton(btn, i)
            layout.addWidget(btn)

        self._buttons[1].setChecked(True)
        self._group.idClicked.connect(self.page_changed)

        layout.addStretch()

        # Footer row: Settings + theme toggle
        footer = QHBoxLayout()
        footer.setSpacing(4)

        self._settings_btn = QPushButton("⚙  Settings")
        self._settings_btn.setFlat(True)
        self._settings_btn.clicked.connect(self.settings_clicked)
        footer.addWidget(self._settings_btn, stretch=1)

        self._theme_btn = QPushButton()
        self._theme_btn.setFlat(True)
        self._theme_btn.setFixedWidth(28)
        self._theme_btn.clicked.connect(self.theme_toggled)
        footer.addWidget(self._theme_btn)

        layout.addLayout(footer)

    def set_theme(self, colors: ThemeColors) -> None:
        c = colors
        is_dark = c.get("is_dark", False)

        # Update theme toggle icon
        self._theme_btn.setText("☀" if is_dark else "☾")
        self._theme_btn.setToolTip(
            "Switch to light theme" if is_dark else "Switch to dark theme"
        )

        nav_style = (
            f"QPushButton{{"
            f"  border:none; border-radius:6px; padding:8px 12px;"
            f"  text-align:left; font-size:13px;"
            f"  color:{c['sidebar_text']}; background:transparent;"
            f"}}"
            f"QPushButton:checked{{"
            f"  background:{c['sidebar_selected']}; font-weight:bold;"
            f"}}"
            f"QPushButton:hover:!checked{{"
            f"  background:{c['sidebar_hover']};"
            f"}}"
        )
        for btn in self._buttons:
            btn.setStyleSheet(nav_style)

        footer_style = (
            f"QPushButton{{"
            f"  border:none; border-radius:6px; padding:6px 8px;"
            f"  font-size:12px; color:{c['text_secondary']}; background:transparent;"
            f"}}"
            f"QPushButton:hover{{background:{c['sidebar_hover']};}}"
        )
        self._settings_btn.setStyleSheet(footer_style)
        self._theme_btn.setStyleSheet(footer_style)

        self._title.setStyleSheet(
            f"color:{c['sidebar_title']}; font-size:10px;"
            f"font-weight:bold; padding:0 4px;"
        )

        self.setStyleSheet(
            f"QWidget#Sidebar{{"
            f"  background:{c['sidebar_bg']};"
            f"  border-right:1px solid {c['border']};"
            f"}}"
        )

    def set_active(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def current_index(self) -> int:
        return self._group.checkedId()
