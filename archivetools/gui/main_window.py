from __future__ import annotations

from typing import Optional, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
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

from archivetools.gui.workers import ExtractionWorker, ListWorker

_ENCODINGS = [
    ("Auto-detect", ""),
    ("GBK (Simplified Chinese)", "gbk"),
    ("Big5 (Traditional Chinese)", "big5"),
    ("Big5-HKSCS (Hong Kong)", "big5hkscs"),
    ("GB18030 (Mainland China)", "gb18030"),
    ("UTF-8", "utf-8"),
]

_AnyWorker = Union[ListWorker, ExtractionWorker]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ArchiveTools")
        self.setMinimumSize(700, 620)
        self.setAcceptDrops(True)

        self._worker: Optional[_AnyWorker] = None
        self._preview_valid = False

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Progress bar lives outside the splitter so it doesn't shift layout
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)

        # ── Top pane: archive path + options + preview button ─────────────────
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        top_layout.addWidget(self._build_archive_group())
        top_layout.addWidget(self._build_options_group())
        top_layout.addWidget(self._build_preview_button())
        top_layout.addStretch()

        # ── Bottom pane: contents tree + extract button + log ─────────────────
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
        layout = QHBoxLayout(box)

        self._archive_edit = QLineEdit()
        self._archive_edit.setPlaceholderText("Path to archive (or drag & drop)…")
        self._archive_edit.textChanged.connect(self._on_archive_changed)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_archive)

        layout.addWidget(self._archive_edit)
        layout.addWidget(browse_btn)
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

        # Password encoding
        self._pwd_encoding_combo = QComboBox()
        for label, codec in _ENCODINGS:
            self._pwd_encoding_combo.addItem(label, codec)
        form.addRow("Password encoding:", self._pwd_encoding_combo)

        # Filename encoding
        self._encoding_combo = QComboBox()
        for label, codec in _ENCODINGS:
            self._encoding_combo.addItem(label, codec)
        form.addRow("Filename encoding:", self._encoding_combo)

        # Output directory
        out_row = QWidget()
        out_layout = QHBoxLayout(out_row)
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.setSpacing(4)

        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("Default (next to archive)")

        out_browse_btn = QPushButton("Browse…")
        out_browse_btn.clicked.connect(self._browse_output)

        out_layout.addWidget(self._output_edit)
        out_layout.addWidget(out_browse_btn)
        form.addRow("Output directory:", out_row)

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

    def _build_extract_button(self) -> QPushButton:
        self._extract_btn = QPushButton("Extract")
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._start_extract)
        return self._extract_btn

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

    # ── Drag and Drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls() and len(mime.urls()) == 1 and mime.urls()[0].isLocalFile():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        path = event.mimeData().urls()[0].toLocalFile()
        self._archive_edit.setText(path)
        event.acceptProposedAction()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_archive_changed(self, text: str) -> None:
        has_text = bool(text.strip())
        self._preview_btn.setEnabled(has_text)
        self._preview_valid = False
        self._extract_btn.setEnabled(False)
        self._contents_tree.clear()

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

    def _browse_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Archive", "",
            "Archives (*.zip *.rar *.7z *.z01 *.r00 *.001);;All files (*)",
        )
        if path:
            self._archive_edit.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self._output_edit.setText(path)

    def _current_encoding(self) -> Optional[str]:
        codec: str = self._encoding_combo.currentData()
        return codec or None

    def _current_pwd_encoding(self) -> Optional[str]:
        codec: str = self._pwd_encoding_combo.currentData()
        return codec or None

    def _start_list(self) -> None:
        archive = self._archive_edit.text().strip()
        if not archive:
            return
        self._contents_tree.clear()
        self._preview_valid = False
        self._extract_btn.setEnabled(False)
        self._log("─" * 60)

        worker = ListWorker(
            archive, self._password_edit.text(),
            self._current_encoding(), self._current_pwd_encoding(),
        )
        worker.result.connect(self._on_list_finished)
        worker.error.connect(self._on_list_error)
        worker.log_message.connect(self._log)
        self._start_worker(worker)

    def _start_extract(self) -> None:
        archive = self._archive_edit.text().strip()
        if not archive:
            return
        self._log("─" * 60)

        worker = ExtractionWorker(
            archive,
            self._password_edit.text(),
            self._output_edit.text().strip(),
            self._current_encoding(),
            self._current_pwd_encoding(),
        )
        worker.result.connect(self._on_extract_finished)
        worker.error.connect(self._on_extract_error)
        worker.log_message.connect(self._log)
        self._start_worker(worker)

    def _start_worker(self, worker: _AnyWorker) -> None:
        self._worker = worker
        self._set_busy(True)
        # Qt's built-in QThread.finished fires after run() returns.
        # deleteLater defers C++ destruction to the event loop so the OS thread
        # fully unwinds before the QThread object is destroyed (prevents SIGABRT).
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_worker_done)
        worker.start()

    def _on_worker_done(self) -> None:
        """Clear the Python reference after Qt has scheduled safe C++ cleanup."""
        self._worker = None

    def _on_list_finished(self, ok: bool, enc: str, names: list) -> None:
        self._set_busy(False)
        if ok:
            self._populate_tree(names)
            self._preview_valid = True
            self._extract_btn.setEnabled(True)
            self._log(f"✓ Preview ready — {len(names)} entries  (encoding: {enc or 'auto'})")
        else:
            self._log("✗ Could not read archive — check the password.")

    def _on_list_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")

    def _on_extract_finished(self, ok: bool, enc: str) -> None:
        self._set_busy(False)
        if ok:
            self._log(f"✓ Extraction complete  (encoding: {enc or 'auto'})")
        else:
            self._log("✗ Extraction failed — see log above for details.")

    def _on_extract_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        has_archive = bool(self._archive_edit.text().strip())
        self._preview_btn.setEnabled(not busy and has_archive)
        self._extract_btn.setEnabled(not busy and self._preview_valid)
        if busy:
            self._progress_bar.setRange(0, 0)  # indeterminate pulse
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
