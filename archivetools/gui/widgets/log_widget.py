from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.gui.theme import LIGHT, ThemeColors


class CollapsibleLog(QWidget):
    """Collapsible log pane: shows a ▸ Log header with last-message preview.

    Auto-expands when an error line (starting with ✗) is appended.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self._toggle_btn = QPushButton("▸  Log")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        self._last_lbl = QLabel("")
        header_row.addWidget(self._toggle_btn)
        header_row.addWidget(self._last_lbl, stretch=1)
        layout.addLayout(header_row)

        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(2000)
        self._log_edit.setFixedHeight(110)
        self._log_edit.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self._log_edit.setVisible(False)
        layout.addWidget(self._log_edit)

        self.set_theme(LIGHT)

    # ── Public API ────────────────────────────────────────────────────────────

    def append(self, text: str) -> None:
        self._log_edit.appendPlainText(text)
        self._last_lbl.setText(text[:70])
        if text.startswith("✗") and not self._log_edit.isVisible():
            self._toggle()

    def clear(self) -> None:
        self._log_edit.clear()
        self._last_lbl.clear()

    def set_theme(self, c: ThemeColors) -> None:
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{text-align:left;color:{c['text_secondary']};font-size:12px;"
            f"padding:3px 0;border:none;}}"
            f"QPushButton:hover{{color:{c['text']};}}"
        )
        self._last_lbl.setStyleSheet(f"color:{c['text_dim']};font-size:11px;")

    # ── Private ───────────────────────────────────────────────────────────────

    def _toggle(self) -> None:
        visible = not self._log_edit.isVisible()
        self._log_edit.setVisible(visible)
        self._toggle_btn.setText("▾  Log" if visible else "▸  Log")
