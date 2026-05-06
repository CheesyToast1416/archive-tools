from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.formats.base import ArchiveInfo
from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.workers import InfoWorker

_ARCHIVE_FILTER = (
    "Archives (*.zip *.rar *.7z *.z01 *.r00 *.001 *.tar *.tar.gz *.tgz "
    "*.tar.bz2 *.tar.xz);;"
    "All files (*)"
)


def _fmt_size(n: int) -> str:
    if n < 0:
        return "—"
    if n == 0:
        return "0 B"
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024:
            return f"{v:.0f} {unit}" if unit == "B" else f"{v:.2f} {unit}"
        v /= 1024
    return f"{v:.2f} PB"


class InfoPanel(QWidget):
    """Displays archive metadata: format, file count, sizes, encryption status."""

    status_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: InfoWorker | None = None
        self._build_ui()

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
        outer.addWidget(self._build_archive_group())
        outer.addWidget(self._build_details_group())
        outer.addWidget(self._build_log_group())
        outer.addStretch()

    def _build_archive_group(self) -> QGroupBox:
        box = QGroupBox("Archive")
        layout = QVBoxLayout(box)
        self._archive_picker = ArchivePickerWidget(
            placeholder="Path to archive (or drag & drop)…",
            file_filter=_ARCHIVE_FILTER,
        )
        self._archive_picker.path_changed.connect(self._on_archive_changed)

        self._load_btn = QPushButton("Load Info")
        self._load_btn.setEnabled(False)
        self._load_btn.clicked.connect(self._start_load)

        layout.addWidget(self._archive_picker)
        layout.addWidget(self._load_btn)
        return box

    def _build_details_group(self) -> QGroupBox:
        box = QGroupBox("Archive Details")
        form = QFormLayout(box)

        self._lbl_format = QLabel("—")
        self._lbl_count = QLabel("—")
        self._lbl_compressed = QLabel("—")
        self._lbl_uncompressed = QLabel("—")
        self._lbl_ratio = QLabel("—")
        self._lbl_encrypted = QLabel("—")
        self._lbl_comment = QLabel("—")

        form.addRow("Format:", self._lbl_format)
        form.addRow("Files:", self._lbl_count)
        form.addRow("Compressed:", self._lbl_compressed)
        form.addRow("Uncompressed:", self._lbl_uncompressed)
        form.addRow("Ratio:", self._lbl_ratio)
        form.addRow("Encrypted:", self._lbl_encrypted)
        form.addRow("Comment:", self._lbl_comment)
        return box

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(500)
        self._log_edit.setFixedHeight(80)
        layout.addWidget(self._log_edit)
        return box

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_archive_changed(self, text: str) -> None:
        self._load_btn.setEnabled(bool(text.strip()))
        self._clear_details()

    def _start_load(self) -> None:
        path = self._archive_picker.path
        if not path:
            return
        self._clear_details()
        self._set_busy(True)
        worker = InfoWorker(path)
        worker.result.connect(self._on_info_ready)
        worker.error.connect(self._on_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_worker_done)
        self._worker = worker
        worker.start()

    def _on_info_ready(self, info: ArchiveInfo) -> None:
        self._set_busy(False)
        self._populate(info)
        self.status_changed.emit(f"Info: {info.format_name}, {info.file_count} files")

    def _on_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log_edit.appendPlainText(f"✗ {msg}")
        self.status_changed.emit("Error loading info")

    def _on_worker_done(self) -> None:
        self._worker = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def handle_drop(self, path: str) -> None:
        self._archive_picker.set_path(path)

    def _set_busy(self, busy: bool) -> None:
        self._load_btn.setEnabled(not busy and bool(self._archive_picker.path))
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(1)
            self._progress_bar.setVisible(False)

    def _clear_details(self) -> None:
        for lbl in (
            self._lbl_format,
            self._lbl_count,
            self._lbl_compressed,
            self._lbl_uncompressed,
            self._lbl_ratio,
            self._lbl_encrypted,
            self._lbl_comment,
        ):
            lbl.setText("—")
        self._log_edit.clear()

    def _populate(self, info: ArchiveInfo) -> None:
        self._lbl_format.setText(info.format_name)
        self._lbl_count.setText(str(info.file_count) if info.file_count >= 0 else "—")
        self._lbl_compressed.setText(_fmt_size(info.compressed_size))
        self._lbl_uncompressed.setText(_fmt_size(info.uncompressed_size))

        if info.compressed_size > 0 and info.uncompressed_size > 0:
            ratio = 100.0 * (1 - info.compressed_size / info.uncompressed_size)
            self._lbl_ratio.setText(f"{ratio:.1f}% saved")
        else:
            self._lbl_ratio.setText("—")

        self._lbl_encrypted.setText("Yes" if info.is_encrypted else "No")
        self._lbl_comment.setText(info.comment or "—")
