from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from archivetools.gui.constants import ARCHIVE_FILTER as _ARCHIVE_FILTER
from archivetools.gui.theme import LIGHT, ThemeColors

_COLS = 3


class _ArchiveCard(QFrame):
    """Clickable card showing an archive's icon, name, and last-opened date."""

    clicked = Signal(str)

    def __init__(self, path: str, colors: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = path
        self.setObjectName("archiveCard")
        self.setFixedSize(148, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(path)
        self._build_ui()
        self.set_theme(colors)

    def set_theme(self, c: ThemeColors) -> None:
        bg, border, hover, hover_border = (
            c["card_bg"],
            c["card_border"],
            c["card_hover_bg"],
            c["border"],
        )
        self.setStyleSheet(
            f"QFrame#archiveCard{{background:{bg};border:1px solid {border};"
            f"border-radius:8px;}}"
            f"QFrame#archiveCard:hover{{background:{hover};border-color:{hover_border};}}"
        )
        self._name_lbl.setStyleSheet(f"font-size:12px;color:{c['text']};")
        self._date_lbl.setStyleSheet(f"font-size:10px;color:{c['text_secondary']};")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        icon_lbl.setPixmap(icon.pixmap(32, 32))
        layout.addWidget(icon_lbl)

        self._name_lbl = QLabel(os.path.basename(self._path))
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl = self._name_lbl
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

        try:
            mtime = os.path.getmtime(self._path)
            date_str = _format_date(mtime)
        except OSError:
            date_str = "—"

        self._date_lbl = QLabel(date_str)
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._date_lbl)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._path)
        super().mousePressEvent(event)


def _format_date(ts: float) -> str:
    dt = datetime.fromtimestamp(ts)
    now = datetime.now()
    delta = now - dt
    if delta.days == 0:
        hours = int(delta.seconds / 3600)
        if hours == 0:
            mins = max(1, int(delta.seconds / 60))
            return f"{mins}m ago"
        return f"{hours}h ago"
    if delta.days == 1:
        return "Yesterday"
    if delta.days < 7:
        return f"{delta.days} days ago"
    return dt.strftime("%d %b %Y")


class RecentPanel(QWidget):
    """Landing page showing recently opened archives as clickable cards."""

    open_archive = Signal(str)  # emitted with path when a card or Open… is clicked
    status_changed = Signal(str)

    def __init__(
        self, colors: ThemeColors | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._colors: ThemeColors = colors or LIGHT
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(12)

        self._heading_lbl = QLabel("Recent")
        outer.addWidget(self._heading_lbl)

        # Scroll area for cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._cards_widget = QWidget()
        self._grid = QGridLayout(self._cards_widget)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._cards_widget)
        outer.addWidget(self._scroll, stretch=1)

        # Empty state label (shown when no recents)
        self._empty_lbl = QLabel("No recent archives.\nOpen an archive to get started.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._empty_lbl)

        # Bottom row
        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Archive…")
        open_btn.setFixedHeight(32)
        open_btn.clicked.connect(self._browse_open)
        btn_row.addStretch()
        btn_row.addWidget(open_btn)
        outer.addLayout(btn_row)

    # ── Public ────────────────────────────────────────────────────────────────

    def set_theme(self, c: ThemeColors) -> None:
        self._colors = c
        self._heading_lbl.setStyleSheet(
            f"font-size:22px;font-weight:bold;color:{c['text']};"
        )
        self._empty_lbl.setStyleSheet(f"color:{c['text_secondary']};font-size:13px;")
        # Re-theme existing cards
        root = self._grid
        for i in range(root.count()):
            item = root.itemAt(i)
            if item and isinstance(item.widget(), _ArchiveCard):
                item.widget().set_theme(c)

    def refresh(self, paths: list[str]) -> None:
        """Repopulate the card grid from *paths* (most-recent first)."""
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_cards = bool(paths)
        self._scroll.setVisible(has_cards)
        self._empty_lbl.setVisible(not has_cards)

        for i, path in enumerate(paths):
            card = _ArchiveCard(path, self._colors)
            card.clicked.connect(self.open_archive)
            row, col = divmod(i, _COLS)
            self._grid.addWidget(card, row, col)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _browse_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Archive", "", _ARCHIVE_FILTER)
        if path:
            self.open_archive.emit(path)
