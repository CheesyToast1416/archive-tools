from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_APP_NAME = "ArchiveTools"
_VERSION = "0.2.0"
_COPYRIGHT = "Copyright © 2025–2026 CheesyToast1416"
_LICENSE_SPDX = "GNU General Public License v3.0"
_DESCRIPTION = (
    "An encoding-aware archive manager for ZIP, RAR, 7z, and TAR archives.<br>"
    "Supports filename-encoding auto-detection, encrypted archives,"
    "multi-volume sets, and in-app file preview."
)


def _find_file(name: str) -> str:
    """Walk up from this file's location to find a named text file."""
    for parent in Path(__file__).parents:
        candidate = parent / name
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return f"{name} not found."


class _TextViewerDialog(QDialog):
    """Generic scrollable plain-text viewer dialog."""

    def __init__(self, title: str, content: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 520)
        self.resize(700, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        text = QPlainTextEdit(content)
        text.setReadOnly(True)
        text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout.addWidget(text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        layout.addWidget(btns)


# Keep the old name as an alias so main_window.py still imports it
def _LicenseDialog(parent: QWidget | None = None) -> _TextViewerDialog:
    return _TextViewerDialog(
        f"License — {_LICENSE_SPDX}", _find_file("LICENSE.txt"), parent
    )


class AboutDialog(QDialog):
    """Help > About dialog: app info, copyright, license summary."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {_APP_NAME}")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 16)
        layout.setSpacing(6)

        # ── App name + version ────────────────────────────────────────────────
        name_lbl = QLabel(f"<b style='font-size:20px'>{_APP_NAME}</b>")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_lbl)

        ver_lbl = QLabel(f"Version {_VERSION}")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_lbl)

        layout.addSpacing(8)

        # ── Description ───────────────────────────────────────────────────────
        desc_lbl = QLabel(_DESCRIPTION)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        layout.addSpacing(12)

        # ── Copyright + license ───────────────────────────────────────────────
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#CCCCCC;")
        layout.addWidget(sep)

        layout.addSpacing(8)

        copy_lbl = QLabel(_COPYRIGHT)
        copy_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copy_lbl)

        lic_lbl = QLabel(
            f"Released under the <b>{_LICENSE_SPDX}</b>.<br>"
            "This program comes with <b>absolutely no warranty</b>.<br>"
            "You are free to redistribute it under the terms of the GPL."
        )
        lic_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lic_lbl.setWordWrap(True)
        layout.addWidget(lic_lbl)

        layout.addSpacing(12)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        license_btn = QPushButton("License…")
        license_btn.clicked.connect(self._show_license)

        notices_btn = QPushButton("Third-Party Notices…")
        notices_btn.clicked.connect(self._show_notices)

        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(license_btn)
        btn_row.addWidget(notices_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _show_license(self) -> None:
        _LicenseDialog(self).exec()

    def _show_notices(self) -> None:
        _TextViewerDialog(
            "Third-Party Notices",
            _find_file("THIRD_PARTY_NOTICES.txt"),
            self,
        ).exec()
