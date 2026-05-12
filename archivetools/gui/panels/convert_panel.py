from __future__ import annotations

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordStore, get_or_create_store
from archivetools.config.settings import AppSettings
from archivetools.gui.constants import ARCHIVE_FILTER as _ARCHIVE_FILTER
from archivetools.gui.constants import ARCHIVE_FORMATS as _ARCHIVE_FORMATS
from archivetools.gui.theme import LIGHT, ThemeColors
from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.widgets.encoding_combo import EncodingComboBox
from archivetools.gui.widgets.log_widget import CollapsibleLog
from archivetools.gui.widgets.password_picker_btn import PasswordPickerButton
from archivetools.gui.workers import ConvertWorker
from archivetools.utils.notifications import notify as _notify

_SAVE_FILTER = (
    "ZIP archive (*.zip);;"
    "7z archive (*.7z);;"
    "TAR archive (*.tar *.tar.gz *.tar.bz2 *.tar.xz);;"
    "All files (*)"
)

_OUT_FORMATS = [(lbl, key, pwd) for lbl, key, _, pwd in _ARCHIVE_FORMATS]


class ConvertPanel(QWidget):
    """Convert an archive from any format to another — flat design, collapsible log."""

    status_changed = Signal(str)

    def __init__(
        self,
        settings: AppSettings | None = None,
        store: PasswordStore | None = None,
        colors: ThemeColors | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._colors = colors or LIGHT
        self._worker: ConvertWorker | None = None
        self._store = store
        self._section_headers: list[QLabel] = []
        self._build_ui()
        self._on_format_changed(0)
        if settings is not None:
            self.apply_settings(settings)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 12, 16, 10)
        cl.setSpacing(0)

        # ── Source ──────────────────────────────────────────────────────────
        cl.addWidget(self._section_lbl("SOURCE ARCHIVE"))
        cl.addSpacing(4)
        src_form = QFormLayout()
        src_form.setSpacing(6)
        src_form.setContentsMargins(0, 0, 0, 0)

        self._src_picker = ArchivePickerWidget(
            placeholder="Path to source archive (or drag & drop)…",
            file_filter=_ARCHIVE_FILTER,
        )
        src_form.addRow("Archive:", self._src_picker)

        src_pwd_row = QWidget()
        sp = QHBoxLayout(src_pwd_row)
        sp.setContentsMargins(0, 0, 0, 0)
        sp.setSpacing(4)
        self._src_password = QLineEdit()
        self._src_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._src_password.setPlaceholderText("Source password (if any)")
        self._src_eye = QToolButton()
        self._src_eye.setCheckable(True)
        self._src_eye.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
        )
        self._src_eye.toggled.connect(
            lambda checked: self._src_password.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        self._src_pwd_picker = PasswordPickerButton(get_or_create_store(self._store))
        self._src_pwd_picker.password_selected.connect(self._src_password.setText)
        sp.addWidget(self._src_password)
        sp.addWidget(self._src_eye)
        sp.addWidget(self._src_pwd_picker)
        src_form.addRow("Password:", src_pwd_row)

        self._pwd_encoding = EncodingComboBox()
        src_form.addRow("Password encoding:", self._pwd_encoding)

        self._fname_encoding = EncodingComboBox()
        src_form.addRow("Filename encoding:", self._fname_encoding)

        cl.addLayout(src_form)
        cl.addSpacing(10)
        cl.addWidget(self._make_sep())
        cl.addSpacing(8)

        # ── Output ──────────────────────────────────────────────────────────
        cl.addWidget(self._section_lbl("OUTPUT ARCHIVE"))
        cl.addSpacing(4)
        out_form = QFormLayout()
        out_form.setSpacing(6)
        out_form.setContentsMargins(0, 0, 0, 0)

        self._fmt_combo = QComboBox()
        for label, *_ in _OUT_FORMATS:
            self._fmt_combo.addItem(label)
        self._fmt_combo.currentIndexChanged.connect(self._on_format_changed)
        out_form.addRow("Format:", self._fmt_combo)

        self._out_picker = ArchivePickerWidget(
            placeholder="Destination path…",
            file_filter=_SAVE_FILTER,
            save_mode=True,
        )
        out_form.addRow("Output path:", self._out_picker)

        out_pwd_row = QWidget()
        op = QHBoxLayout(out_pwd_row)
        op.setContentsMargins(0, 0, 0, 0)
        op.setSpacing(4)
        self._out_password = QLineEdit()
        self._out_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._out_password.setPlaceholderText("Output archive password")
        self._out_eye = QToolButton()
        self._out_eye.setCheckable(True)
        self._out_eye.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
        )
        self._out_eye.toggled.connect(
            lambda checked: self._out_password.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        self._out_pwd_picker = PasswordPickerButton(get_or_create_store(self._store))
        self._out_pwd_picker.password_selected.connect(self._out_password.setText)
        op.addWidget(self._out_password)
        op.addWidget(self._out_eye)
        op.addWidget(self._out_pwd_picker)
        self._out_pwd_label = QLabel("Output password:")
        out_form.addRow(self._out_pwd_label, out_pwd_row)
        self._out_pwd_row = out_pwd_row

        cl.addLayout(out_form)
        cl.addSpacing(10)
        cl.addWidget(self._make_sep())
        cl.addSpacing(6)

        # ── Action bar ──────────────────────────────────────────────────────
        action = QHBoxLayout()
        action.addStretch()
        self._convert_btn = QPushButton("Convert Archive")
        self._convert_btn.clicked.connect(self._start_convert)
        action.addWidget(self._convert_btn)
        cl.addLayout(action)
        cl.addSpacing(6)

        # ── Log ─────────────────────────────────────────────────────────────
        self._log_widget = CollapsibleLog()
        cl.addWidget(self._log_widget)
        cl.addStretch()

        outer.addWidget(content)
        self.set_theme(self._colors)

    def _section_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        self._section_headers.append(lbl)
        return lbl

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        return sep

    # ── Theme ─────────────────────────────────────────────────────────────────

    def set_theme(self, c: ThemeColors) -> None:
        self._colors = c
        for lbl in self._section_headers:
            lbl.setStyleSheet(
                f"color:{c['text_dim']};font-size:10px;font-weight:bold;letter-spacing:1px;"
            )
        self._convert_btn.setStyleSheet(
            f"QPushButton{{background:{c['accent']};color:white;border:none;"
            f"border-radius:6px;padding:5px 16px;font-weight:600;}}"
            f"QPushButton:hover{{background:{c['accent_hover']};}}"
            f"QPushButton:disabled{{background:{c['accent_disabled_bg']};color:#EEEEEE;}}"
        )
        self._log_widget.set_theme(c)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_format_changed(self, index: int) -> None:
        _, _fmt, supports_password = _OUT_FORMATS[index]
        self._out_pwd_label.setVisible(supports_password)
        self._out_pwd_row.setVisible(supports_password)

    def _start_convert(self) -> None:
        src = self._src_picker.path
        dst = self._out_picker.path
        if not src:
            self._log("✗ Select a source archive first.")
            return
        if not dst:
            self._log("✗ Set an output path first.")
            return

        idx = self._fmt_combo.currentIndex()
        _, fmt, supports_password = _OUT_FORMATS[idx]
        out_pwd = self._out_password.text() if supports_password else ""

        self._log("─" * 60)
        worker = ConvertWorker(
            src,
            dst,
            fmt,
            self._src_password.text(),
            out_pwd,
            filename_encoding=self._fname_encoding.current_codec(),
            password_encoding=self._pwd_encoding.current_codec(),
        )
        worker.result.connect(self._on_convert_finished)
        worker.error.connect(self._on_convert_error)
        worker.log_message.connect(self._log)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_worker_done)
        self._worker = worker
        self._set_busy(True)
        worker.start()

    def _on_convert_finished(self, ok: bool) -> None:
        self._set_busy(False)
        if ok:
            self._log(f"✓ Conversion complete: {self._out_picker.path}")
            self.status_changed.emit("Conversion complete")
            _notify("Conversion complete", os.path.basename(self._out_picker.path))
        else:
            self._log("✗ Conversion failed.")
            self.status_changed.emit("Conversion failed")

    def _on_convert_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Error")

    def _on_worker_done(self) -> None:
        self._worker = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def apply_settings(self, settings: AppSettings) -> None:
        self._pwd_encoding.set_codec(settings.default_password_encoding)
        self._fname_encoding.set_codec(settings.default_filename_encoding)

    def refresh_password_picker(self) -> None:
        self._src_pwd_picker.refresh()
        self._out_pwd_picker.refresh()

    def handle_drop(self, path: str) -> None:
        self._src_picker.set_path(path)

    def _set_busy(self, busy: bool) -> None:
        self._convert_btn.setEnabled(not busy)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(1)
            self._progress_bar.setVisible(False)

    def _log(self, text: str) -> None:
        self._log_widget.append(text)
