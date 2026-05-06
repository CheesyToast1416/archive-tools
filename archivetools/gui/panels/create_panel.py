from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CreatePanel(QWidget):
    """Placeholder panel — archive creation coming in the next release."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lbl = QLabel(
            "<b>Archive Creation</b><br><br>"
            "Coming in the next release.<br>"
            "Planned formats: ZIP, ZIP-AES, 7z, TAR family."
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        QVBoxLayout(self).addWidget(lbl)
