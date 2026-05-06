from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordStore
from archivetools.config.settings import AppSettings
from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.widgets.encoding_combo import EncodingComboBox
from archivetools.gui.widgets.password_picker_btn import PasswordPickerButton
from archivetools.gui.workers import ConvertWorker

_ARCHIVE_FILTER = (
    "Archives (*.zip *.rar *.7z *.z01 *.r00 *.001 *.tar *.tar.gz *.tgz "
    "*.tar.bz2 *.tar.xz);;"
    "All files (*)"
)
_SAVE_FILTER = (
    "ZIP archive (*.zip);;"
    "7z archive (*.7z);;"
    "TAR archive (*.tar *.tar.gz *.tar.bz2 *.tar.xz);;"
    "All files (*)"
)

_OUT_FORMATS = [
    ("ZIP (no password)", "zip", False),
    ("ZIP (AES-256 encrypted)", "zip-aes", True),
    ("7z", "7z", True),
    ("TAR (.tar)", "tar", False),
    ("TAR.GZ (.tar.gz)", "tar.gz", False),
    ("TAR.BZ2 (.tar.bz2)", "tar.bz2", False),
    ("TAR.XZ (.tar.xz)", "tar.xz", False),
]


class ConvertPanel(QWidget):
    """Re-package an archive from any format to any other supported format."""

    status_changed = Signal(str)

    def __init__(
        self,
        settings: AppSettings | None = None,
        store: PasswordStore | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._worker: ConvertWorker | None = None
        self._store = store
        self._build_ui()
        self._on_format_changed(0)
        if settings is not None:
            self.apply_settings(settings)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)

        outer.addWidget(self._progress_bar)
        outer.addWidget(self._build_source_group())
        outer.addWidget(self._build_output_group())
        outer.addWidget(self._build_convert_button())
        outer.addWidget(self._build_log_group(), stretch=1)

    def _build_source_group(self) -> QGroupBox:
        box = QGroupBox("Source Archive")
        form = QFormLayout(box)

        self._src_picker = ArchivePickerWidget(
            placeholder="Path to source archive (or drag & drop)…",
            file_filter=_ARCHIVE_FILTER,
        )
        form.addRow("Archive:", self._src_picker)

        # Password + eye
        pwd_row = QWidget()
        pwd_layout = QHBoxLayout(pwd_row)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(4)
        self._src_password = QLineEdit()
        self._src_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._src_password.setPlaceholderText("Source archive password (if any)")
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
        pwd_layout.addWidget(self._src_password)
        from archivetools.config.passwords import get_password_store

        self._src_pwd_picker = PasswordPickerButton(
            self._store if self._store is not None else get_password_store()
        )
        self._src_pwd_picker.password_selected.connect(self._src_password.setText)
        pwd_layout.addWidget(self._src_eye)
        pwd_layout.addWidget(self._src_pwd_picker)
        form.addRow("Password:", pwd_row)

        self._pwd_encoding = EncodingComboBox()
        form.addRow("Password encoding:", self._pwd_encoding)

        self._fname_encoding = EncodingComboBox()
        form.addRow("Filename encoding:", self._fname_encoding)

        return box

    def _build_output_group(self) -> QGroupBox:
        box = QGroupBox("Output Archive")
        form = QFormLayout(box)

        self._fmt_combo = QComboBox()
        for label, *_ in _OUT_FORMATS:
            self._fmt_combo.addItem(label)
        self._fmt_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("Format:", self._fmt_combo)

        self._out_picker = ArchivePickerWidget(
            placeholder="Destination path…",
            file_filter=_SAVE_FILTER,
            save_mode=True,
        )
        form.addRow("Output path:", self._out_picker)

        # Output password (for encrypted formats)
        out_pwd_row = QWidget()
        out_pwd_layout = QHBoxLayout(out_pwd_row)
        out_pwd_layout.setContentsMargins(0, 0, 0, 0)
        out_pwd_layout.setSpacing(4)
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
        out_pwd_layout.addWidget(self._out_password)
        from archivetools.config.passwords import get_password_store

        self._out_pwd_picker = PasswordPickerButton(
            self._store if self._store is not None else get_password_store()
        )
        self._out_pwd_picker.password_selected.connect(self._out_password.setText)
        out_pwd_layout.addWidget(self._out_eye)
        out_pwd_layout.addWidget(self._out_pwd_picker)
        self._out_pwd_label = QLabel("Output password:")
        form.addRow(self._out_pwd_label, out_pwd_row)
        self._out_pwd_row = out_pwd_row

        return box

    def _build_convert_button(self) -> QPushButton:
        self._convert_btn = QPushButton("Convert Archive")
        self._convert_btn.clicked.connect(self._start_convert)
        return self._convert_btn

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(2000)
        self._log_edit.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        layout.addWidget(self._log_edit)
        return box

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
        from archivetools.gui.dialogs.settings_dialog import _set_combo_codec

        _set_combo_codec(self._pwd_encoding, settings.default_password_encoding)
        _set_combo_codec(self._fname_encoding, settings.default_filename_encoding)

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
        self._log_edit.appendPlainText(text)
