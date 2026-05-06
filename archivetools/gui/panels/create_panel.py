from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.workers import CreateWorker

_FORMATS = [
    ("ZIP (no password)", "zip", ".zip", False),
    ("ZIP (AES-256 encrypted)", "zip-aes", ".zip", True),
    ("7z", "7z", ".7z", True),
    ("TAR (.tar)", "tar", ".tar", False),
    ("TAR.GZ (.tar.gz)", "tar.gz", ".tar.gz", False),
    ("TAR.BZ2 (.tar.bz2)", "tar.bz2", ".tar.bz2", False),
    ("TAR.XZ (.tar.xz)", "tar.xz", ".tar.xz", False),
]

_SAVE_FILTER = (
    "ZIP archive (*.zip);;"
    "7z archive (*.7z);;"
    "TAR archive (*.tar *.tar.gz *.tar.bz2 *.tar.xz);;"
    "All files (*)"
)


class _FileList(QListWidget):
    """QListWidget that accepts file/directory drops."""

    files_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()


class CreatePanel(QWidget):
    """Archive creation UI: output picker, files list, format/options, log."""

    status_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: CreateWorker | None = None
        self._build_ui()
        self._on_format_changed(0)

    # ── UI Construction ───────────────────────────────────────────────────────

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
        outer.addWidget(self._build_output_group())
        outer.addWidget(self._build_files_group(), stretch=2)
        outer.addWidget(self._build_options_group())
        self._trash_after_create = QCheckBox(
            "Move source files/folders to trash after successful creation"
        )
        outer.addWidget(self._trash_after_create)
        outer.addWidget(self._build_create_button())
        outer.addWidget(self._build_log_group(), stretch=1)

    def _build_output_group(self) -> QGroupBox:
        box = QGroupBox("Output Archive")
        layout = QVBoxLayout(box)
        self._output_picker = ArchivePickerWidget(
            placeholder="Destination path…",
            file_filter=_SAVE_FILTER,
            save_mode=True,
        )
        layout.addWidget(self._output_picker)
        return box

    def _build_files_group(self) -> QGroupBox:
        box = QGroupBox("Files to Add  (drag & drop or use buttons below)")
        layout = QVBoxLayout(box)

        self._file_list = _FileList()
        self._file_list.files_dropped.connect(self._add_paths)
        layout.addWidget(self._file_list)

        btn_row = QHBoxLayout()
        btn_add_files = QPushButton("Add Files…")
        btn_add_folder = QPushButton("Add Folder…")
        btn_remove = QPushButton("Remove Selected")
        btn_add_files.clicked.connect(self._browse_add_files)
        btn_add_folder.clicked.connect(self._browse_add_folder)
        btn_remove.clicked.connect(self._remove_selected)
        btn_row.addWidget(btn_add_files)
        btn_row.addWidget(btn_add_folder)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    def _build_options_group(self) -> QGroupBox:
        box = QGroupBox("Options")
        form = QFormLayout(box)

        self._format_combo = QComboBox()
        for label, *_ in _FORMATS:
            self._format_combo.addItem(label)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("Format:", self._format_combo)

        # Compression slider
        slider_row = QWidget()
        slider_layout = QHBoxLayout(slider_row)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        self._compression_slider = QSlider(Qt.Orientation.Horizontal)
        self._compression_slider.setRange(0, 9)
        self._compression_slider.setValue(6)
        self._compression_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._compression_slider.setTickInterval(1)
        self._compression_lbl = QLabel("6")
        self._compression_slider.valueChanged.connect(
            lambda v: self._compression_lbl.setText(str(v))
        )
        slider_layout.addWidget(self._compression_slider)
        slider_layout.addWidget(self._compression_lbl)
        self._compression_form_label = QLabel("Compression (0–9):")
        form.addRow(self._compression_form_label, slider_row)
        self._compression_slider_row = slider_row

        # Password
        pwd_row = QWidget()
        pwd_layout = QHBoxLayout(pwd_row)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(4)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Archive password")
        self._eye_btn = QToolButton()
        self._eye_btn.setCheckable(True)
        self._eye_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
        )
        self._eye_btn.setToolTip("Show / hide password")
        self._eye_btn.toggled.connect(self._toggle_password_visibility)
        pwd_layout.addWidget(self._password_edit)
        pwd_layout.addWidget(self._eye_btn)
        self._password_form_label = QLabel("Password:")
        form.addRow(self._password_form_label, pwd_row)
        self._password_row = pwd_row

        return box

    def _build_create_button(self) -> QPushButton:
        self._create_btn = QPushButton("Create Archive")
        self._create_btn.clicked.connect(self._start_create)
        return self._create_btn

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
        _, fmt, _ext, supports_password = _FORMATS[index]
        self._password_form_label.setVisible(supports_password)
        self._password_row.setVisible(supports_password)
        # Hide compression for plain TAR (no compression parameter)
        show_compression = fmt != "tar"
        self._compression_form_label.setVisible(show_compression)
        self._compression_slider_row.setVisible(show_compression)

    def _toggle_password_visibility(self, checked: bool) -> None:
        if checked:
            self._password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._eye_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)
            )
        else:
            self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._eye_btn.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
            )

    def _browse_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Files", "", "All files (*)")
        self._add_paths(paths)

    def _browse_add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Add Folder")
        if path:
            self._add_paths([path])

    def _remove_selected(self) -> None:
        for item in self._file_list.selectedItems():
            self._file_list.takeItem(self._file_list.row(item))

    def _add_paths(self, paths: list[str]) -> None:
        existing = {
            self._file_list.item(i).text() for i in range(self._file_list.count())
        }
        for p in paths:
            if p not in existing:
                self._file_list.addItem(QListWidgetItem(p))
                existing.add(p)

    def _start_create(self) -> None:
        output = self._output_picker.path
        if not output:
            self._log("✗ Set an output path first.")
            return
        if self._file_list.count() == 0:
            self._log("✗ Add at least one file or folder.")
            return

        idx = self._format_combo.currentIndex()
        _, fmt, _ext, supports_password = _FORMATS[idx]
        password = self._password_edit.text() if supports_password else ""
        files = [self._file_list.item(i).text() for i in range(self._file_list.count())]
        level = self._compression_slider.value()

        self._log("─" * 60)
        worker = CreateWorker(output, files, fmt, password, level)
        worker.result.connect(self._on_create_finished)
        worker.error.connect(self._on_create_error)
        worker.log_message.connect(self._log)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_worker_done)
        self._worker = worker
        self._set_busy(True)
        worker.start()

    def _on_create_finished(self, ok: bool) -> None:
        self._set_busy(False)
        if ok:
            self._log(f"✓ Archive created: {self._output_picker.path}")
            self.status_changed.emit("Archive created")
            if self._trash_after_create.isChecked():
                self._trash_sources()
        else:
            self._log("✗ Archive creation failed.")
            self.status_changed.emit("Creation failed")

    def _trash_sources(self) -> None:
        from archivetools.utils.trash import trash_paths

        paths = [
            self._file_list.item(i).text()
            for i in range(self._file_list.count())
            if self._file_list.item(i)
        ]
        ok_count, failed = trash_paths(paths)
        self._log(f"  Moved {ok_count} item(s) to trash.")
        for p in failed:
            self._log(f"  ⚠ Could not trash: {p}")

    def _on_create_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Error")

    def _on_worker_done(self) -> None:
        self._worker = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def handle_drop(self, path: str) -> None:
        """Add dropped file/folder to the files list."""
        self._add_paths([path])

    def _set_busy(self, busy: bool) -> None:
        self._create_btn.setEnabled(not busy)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(1)
            self._progress_bar.setVisible(False)

    def _log(self, text: str) -> None:
        self._log_edit.appendPlainText(text)
