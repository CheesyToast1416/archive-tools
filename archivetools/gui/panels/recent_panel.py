from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
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

_CARD_W = 148  # fixed card width
_CARD_H = 110
_SPACING = 12


# ── Archive card ──────────────────────────────────────────────────────────────


class _ArchiveCard(QFrame):
    """Clickable card showing an archive's icon, name, and last-opened date."""

    clicked = Signal(str)

    def __init__(
        self, path: str, colors: ThemeColors, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._path = path
        self.setObjectName("archiveCard")
        self.setFixedSize(_CARD_W, _CARD_H)
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
        self._name_lbl.setWordWrap(True)
        layout.addWidget(self._name_lbl)

        try:
            date_str = _format_date(os.path.getmtime(self._path))
        except OSError:
            date_str = "—"

        self._date_lbl = QLabel(date_str)
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._date_lbl)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._path)
        super().mousePressEvent(event)


# ── Responsive card grid ──────────────────────────────────────────────────────


class _CardGrid(QWidget):
    """Grid widget that recalculates column count whenever its width changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[_ArchiveCard] = []
        self._cols: int = 0
        self._layout = QGridLayout(self)
        self._layout.setSpacing(_SPACING)
        self._layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

    def set_cards(self, cards: list[_ArchiveCard]) -> None:
        while self._layout.count():
            self._layout.takeAt(0)
        self._cards = cards
        self._cols = 0  # force relayout
        self._relayout()

    def theme_cards(self, c: ThemeColors) -> None:
        for card in self._cards:
            card.set_theme(c)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        # Return a single-card minimum so QScrollArea can shrink us freely
        return QSize(_CARD_W, _CARD_H)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        if not self._cards:
            return
        available = self.width() or (_CARD_W + _SPACING) * 3
        cols = max(1, available // (_CARD_W + _SPACING))
        if cols == self._cols:
            return
        self._cols = cols
        while self._layout.count():
            self._layout.takeAt(0)
        for i, card in enumerate(self._cards):
            row, col = divmod(i, cols)
            self._layout.addWidget(card, row, col)


# ── Helper ────────────────────────────────────────────────────────────────────


def _format_date(ts: float) -> str:
    dt = datetime.fromtimestamp(ts)
    now = datetime.now()
    delta = now - dt
    if delta.days == 0:
        hours = int(delta.seconds / 3600)
        if hours == 0:
            return f"{max(1, int(delta.seconds / 60))}m ago"
        return f"{hours}h ago"
    if delta.days == 1:
        return "Yesterday"
    if delta.days < 7:
        return f"{delta.days} days ago"
    return dt.strftime("%d %b %Y")


# ── Panel ─────────────────────────────────────────────────────────────────────


class RecentPanel(QWidget):
    """Landing page showing recently opened archives as responsive cards."""

    open_archive = Signal(str)
    cleared = Signal()  # emitted when the user clears the recent list
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

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._card_grid = _CardGrid()
        self._scroll.setWidget(self._card_grid)
        outer.addWidget(self._scroll, stretch=1)

        self._empty_lbl = QLabel("No recent archives.\nOpen an archive to get started.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._empty_lbl)

        btn_row = QHBoxLayout()
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self.cleared)
        open_btn = QPushButton("Open Archive…")
        open_btn.clicked.connect(self._browse_open)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(open_btn)
        outer.addLayout(btn_row)

        self.set_theme(self._colors)

    # ── Public ────────────────────────────────────────────────────────────────

    def set_theme(self, c: ThemeColors) -> None:
        self._colors = c
        self._heading_lbl.setStyleSheet(
            f"font-size:22px;font-weight:bold;color:{c['text']};"
        )
        self._empty_lbl.setStyleSheet(f"color:{c['text_secondary']};font-size:13px;")
        self._card_grid.theme_cards(c)

    def refresh(self, paths: list[str]) -> None:
        """Repopulate cards from *paths* (most-recent first)."""
        # Delete old card widgets
        for card in self._card_grid._cards:
            card.deleteLater()

        has_cards = bool(paths)
        self._scroll.setVisible(has_cards)
        self._empty_lbl.setVisible(not has_cards)
        self._clear_btn.setVisible(has_cards)

        cards = []
        for path in paths:
            card = _ArchiveCard(path, self._colors)
            card.clicked.connect(self.open_archive)
            cards.append(card)
        self._card_grid.set_cards(cards)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _browse_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Archive", "", _ARCHIVE_FILTER)
        if path:
            self.open_archive.emit(path)
