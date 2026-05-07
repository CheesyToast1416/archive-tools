from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.formats.base import ArchiveInfo
from archivetools.gui.constants import ARCHIVE_FILTER as _ARCHIVE_FILTER
from archivetools.gui.theme import LIGHT, ThemeColors
from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.widgets.log_widget import CollapsibleLog
from archivetools.gui.workers import InfoWorker


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
    """Displays archive metadata — flat design, collapsible log."""

    status_changed = Signal(str)

    def __init__(self, colors: ThemeColors | None = None, parent=None) -> None:
        super().__init__(parent)
        self._colors = colors or LIGHT
        self._worker: InfoWorker | None = None
        self._section_headers: list[QLabel] = []
        self._build_ui()

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

        # ── Archive picker ───────────────────────────────────────────────────
        cl.addWidget(self._section_lbl("ARCHIVE"))
        cl.addSpacing(4)
        self._archive_picker = ArchivePickerWidget(
            placeholder="Path to archive (or drag & drop)…",
            file_filter=_ARCHIVE_FILTER,
        )
        self._archive_picker.path_changed.connect(self._on_archive_changed)
        cl.addWidget(self._archive_picker)
        cl.addSpacing(6)

        action = QHBoxLayout()
        action.addStretch()
        self._load_btn = QPushButton("Load Info")
        self._load_btn.setEnabled(False)
        self._load_btn.clicked.connect(self._start_load)
        action.addWidget(self._load_btn)
        cl.addLayout(action)
        cl.addSpacing(10)
        cl.addWidget(self._make_sep())
        cl.addSpacing(8)

        # ── Details ─────────────────────────────────────────────────────────
        cl.addWidget(self._section_lbl("ARCHIVE DETAILS"))
        cl.addSpacing(4)

        form = QFormLayout()
        form.setSpacing(6)
        form.setContentsMargins(0, 0, 0, 0)

        self._lbl_format = QLabel("—")
        self._lbl_count = QLabel("—")
        self._lbl_compressed = QLabel("—")
        self._lbl_uncompressed = QLabel("—")
        self._lbl_ratio = QLabel("—")
        self._lbl_encrypted = QLabel("—")
        self._lbl_comment = QLabel("—")

        for row_text, val_lbl in [
            ("Format:", self._lbl_format),
            ("Files:", self._lbl_count),
            ("Compressed:", self._lbl_compressed),
            ("Uncompressed:", self._lbl_uncompressed),
            ("Ratio:", self._lbl_ratio),
            ("Encrypted:", self._lbl_encrypted),
            ("Comment:", self._lbl_comment),
        ]:
            form.addRow(row_text, val_lbl)

        cl.addLayout(form)
        cl.addSpacing(10)
        cl.addWidget(self._make_sep())
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
        self._load_btn.setStyleSheet(
            f"QPushButton{{background:{c['accent']};color:white;border:none;"
            f"border-radius:6px;padding:5px 16px;font-weight:600;}}"
            f"QPushButton:hover{{background:{c['accent_hover']};}}"
            f"QPushButton:disabled{{background:{c['accent_disabled_bg']};color:#EEEEEE;}}"
        )
        self._log_widget.set_theme(c)

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
        self._log_widget.append(f"✗ {msg}")
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
