from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class InfoPanel(QWidget):
    """Placeholder panel — archive info/metadata coming in the next release."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lbl = QLabel(
            "<b>Archive Info</b><br><br>"
            "Coming in the next release.<br>"
            "Will show: file count, compressed/uncompressed size, "
            "compression ratio, format details, encryption status."
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        QVBoxLayout(self).addWidget(lbl)
