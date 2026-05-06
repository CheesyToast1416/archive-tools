from __future__ import annotations

from typing import Optional, Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from archivetools.encoding.detect import (
    detect_rar_filename_encoding,
    detect_zip_filename_encoding,
)
from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.widgets.encoding_combo import EncodingComboBox
from archivetools.gui.workers import ExtractionWorker, ListWorker, TestWorker

_AnyWorker = Union[ListWorker, ExtractionWorker, TestWorker]

_ARCHIVE_FILTER = (
    "Archives (*.zip *.rar *.7z *.z01 *.r00 *.001 *.tar *.tar.gz *.tgz "
    "*.tar.bz2 *.tar.xz);;"
    "All files (*)"
)


class ExtractPanel(QWidget):
    """Full extraction UI: archive picker, options, contents preview, log."""

    status_changed = Signal(str)  # for MainWindow status bar

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: Optional[_AnyWorker] = None
        self._preview_valid = False
        self._build_ui()

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

        # Top pane: archive + options + preview button
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        top_layout.addWidget(self._build_archive_group())
        top_layout.addWidget(self._build_options_group())
        top_layout.addWidget(self._build_preview_button())
        top_layout.addStretch()

        # Bottom pane: contents tree + extract + log
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)
        bottom_layout.addWidget(self._build_contents_group(), stretch=2)
        bottom_layout.addWidget(self._build_extract_button())
        bottom_layout.addWidget(self._build_log_group(), stretch=3)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 40)
        splitter.setStretchFactor(1, 60)

        outer.addWidget(self._progress_bar)
        outer.addWidget(splitter)

    def _build_archive_group(self) -> QGroupBox:
        box = QGroupBox("Archive")
        layout = QVBoxLayout(box)
        self._archive_picker = ArchivePickerWidget(
            placeholder="Path to archive (or drag & drop)…",
            file_filter=_ARCHIVE_FILTER,
        )
        self._archive_picker.path_changed.connect(self._on_archive_changed)
        layout.addWidget(self._archive_picker)
        return box

    def _build_options_group(self) -> QGroupBox:
        box = QGroupBox("Options")
        form = QFormLayout(box)

        # Password + eye-toggle
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
        form.addRow("Password:", pwd_row)

        self._pwd_encoding_combo = EncodingComboBox()
        form.addRow("Password encoding:", self._pwd_encoding_combo)

        self._filename_encoding_combo = EncodingComboBox()
        form.addRow("Filename encoding:", self._filename_encoding_combo)

        # Output directory
        self._output_picker = ArchivePickerWidget(
            placeholder="Default (next to archive)",
            file_filter="",
        )
        # Hijack browse to open a directory dialog instead
        self._output_picker._save_mode = False
        self._output_picker.findChild(QPushButton).clicked.disconnect()
        self._output_picker.findChild(QPushButton).clicked.connect(self._browse_output)
        form.addRow("Output directory:", self._output_picker)

        return box

    def _build_preview_button(self) -> QPushButton:
        self._preview_btn = QPushButton("Preview Contents")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._start_list)
        return self._preview_btn

    def _build_contents_group(self) -> QGroupBox:
        box = QGroupBox("Contents Preview")
        layout = QVBoxLayout(box)

        self._contents_tree = QTreeWidget()
        self._contents_tree.setColumnCount(2)
        self._contents_tree.setHeaderLabels(["Name", "Type"])
        self._contents_tree.setRootIsDecorated(False)
        self._contents_tree.setSortingEnabled(True)

        header = self._contents_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._contents_tree)
        return box

    def _build_extract_button(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._test_btn = QPushButton("Test Archive")
        self._test_btn.setEnabled(False)
        self._test_btn.clicked.connect(self._start_test)

        self._extract_btn = QPushButton("Extract")
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._start_extract)

        layout.addWidget(self._test_btn)
        layout.addWidget(self._extract_btn)
        return row

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

    def _on_archive_changed(self, text: str) -> None:
        has_text = bool(text.strip())
        self._preview_btn.setEnabled(has_text)
        self._test_btn.setEnabled(has_text)
        self._preview_valid = False
        self._extract_btn.setEnabled(False)
        self._contents_tree.clear()
        self._filename_encoding_combo.reset_detected()

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

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self._output_picker.set_path(path)

    def _start_list(self) -> None:
        archive = self._archive_picker.path
        if not archive:
            return
        self._contents_tree.clear()
        self._preview_valid = False
        self._extract_btn.setEnabled(False)
        self._log("─" * 60)

        worker = ListWorker(
            archive,
            self._password_edit.text(),
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
        )
        worker.result.connect(self._on_list_finished)
        worker.error.connect(self._on_list_error)
        worker.log_message.connect(self._log)
        self._start_worker(worker)

    def _start_test(self) -> None:
        archive = self._archive_picker.path
        if not archive:
            return
        self._log("─" * 60)
        self._log("Testing archive integrity…")
        worker = TestWorker(
            archive,
            self._password_edit.text(),
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
        )
        worker.result.connect(self._on_test_finished)
        worker.error.connect(self._on_test_error)
        worker.log_message.connect(self._log)
        self._start_worker(worker)

    def _start_extract(self) -> None:
        archive = self._archive_picker.path
        if not archive:
            return
        self._log("─" * 60)

        worker = ExtractionWorker(
            archive,
            self._password_edit.text(),
            self._output_picker.path,
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
        )
        worker.result.connect(self._on_extract_finished)
        worker.error.connect(self._on_extract_error)
        worker.log_message.connect(self._log)
        worker.file_progress.connect(self._on_file_progress)
        self._start_worker(worker)

    def _start_worker(self, worker: _AnyWorker) -> None:
        self._worker = worker
        self._set_busy(True)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_worker_done)
        worker.start()

    def _on_worker_done(self) -> None:
        self._worker = None

    def _on_list_finished(self, ok: bool, enc: str, names: list) -> None:
        self._set_busy(False)
        if ok:
            self._populate_tree(names)
            self._preview_valid = True
            self._extract_btn.setEnabled(True)
            self._log(
                f"✓ Preview ready — {len(names)} entries  (encoding: {enc or 'auto'})"
            )
            self.status_changed.emit(f"Preview: {len(names)} entries")
            # Run auto-detection for filename encoding
            self._run_filename_detection()
        else:
            self._log("✗ Could not read archive — check the password.")
            self.status_changed.emit("Preview failed")

    def _on_list_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Error")

    def _on_extract_finished(self, ok: bool, enc: str) -> None:
        self._set_busy(False)
        if ok:
            self._log(f"✓ Extraction complete  (encoding: {enc or 'auto'})")
            self.status_changed.emit("Extraction complete")
        else:
            self._log("✗ Extraction failed — see log above for details.")
            self.status_changed.emit("Extraction failed")

    def _on_test_finished(self, ok: bool, failed: list) -> None:
        self._set_busy(False)
        if ok:
            self._log("✓ All entries passed integrity check.")
            self.status_changed.emit("Test passed")
        else:
            self._log(f"✗ Test failed — {len(failed)} bad entries:")
            for name in failed[:20]:
                self._log(f"  • {name}")
            if len(failed) > 20:
                self._log(f"  … and {len(failed) - 20} more")
            self.status_changed.emit(f"Test failed: {len(failed)} bad entries")

    def _on_test_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Error")

    def _on_extract_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Error")

    def _on_file_progress(self, current: int, total: int, filename: str) -> None:
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
            self.status_changed.emit(f"Extracting {current}/{total}: {filename}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        has_archive = bool(self._archive_picker.path)
        self._preview_btn.setEnabled(not busy and has_archive)
        self._test_btn.setEnabled(not busy and has_archive)
        self._extract_btn.setEnabled(not busy and self._preview_valid)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(1)
            self._progress_bar.setVisible(False)

    def _log(self, text: str) -> None:
        self._log_edit.appendPlainText(text)

    def _populate_tree(self, names: list[str]) -> None:
        self._contents_tree.clear()
        dir_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        for name in names:
            is_dir = name.endswith("/")
            item = QTreeWidgetItem([name, "directory" if is_dir else "file"])
            item.setIcon(0, dir_icon if is_dir else file_icon)
            self._contents_tree.addTopLevelItem(item)

    def handle_drop(self, path: str) -> None:
        self._archive_picker.set_path(path)

    def _run_filename_detection(self) -> None:
        """Run charset-normalizer on the archive and update the filename encoding combo."""
        from pathlib import Path

        archive = self._archive_picker.path
        if not archive:
            return
        low = archive.lower()
        if low.endswith((".zip", ".z01")):
            codec, confidence = detect_zip_filename_encoding(Path(archive))
        elif low.endswith((".rar", ".r00", ".r01")):
            codec, confidence = detect_rar_filename_encoding(Path(archive))
        else:
            return
        if codec and confidence >= 0.5:
            self._filename_encoding_combo.set_detected(codec, confidence)
            self._log(
                f"  filename encoding detected: {codec.upper()} ({confidence:.0%} confidence)"
            )
