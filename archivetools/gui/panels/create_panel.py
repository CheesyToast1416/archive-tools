from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSlider,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordStore, get_password_store
from archivetools.config.settings import AppSettings
from archivetools.gui.theme import LIGHT, ThemeColors
from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.widgets.log_widget import CollapsibleLog
from archivetools.gui.widgets.password_picker_btn import PasswordPickerButton
from archivetools.gui.workers import CreateWorker
from archivetools.utils.notifications import notify as _notify
from archivetools.utils.trash import trash_paths

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
    """Archive creation panel — flat design, collapsible log."""

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
        self._worker: CreateWorker | None = None
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

        # ── Output ─────────────────────────────────────────────────────────
        cl.addWidget(self._section_lbl("OUTPUT"))
        cl.addSpacing(4)
        self._output_picker = ArchivePickerWidget(
            placeholder="Destination path…",
            file_filter=_SAVE_FILTER,
            save_mode=True,
        )
        cl.addWidget(self._output_picker)
        cl.addSpacing(10)
        cl.addWidget(self._make_sep())
        cl.addSpacing(8)

        # ── Files ───────────────────────────────────────────────────────────
        cl.addWidget(self._section_lbl("FILES  —  drag & drop or use buttons"))
        cl.addSpacing(4)
        self._file_list = _FileList()
        self._file_list.files_dropped.connect(self._add_paths)
        cl.addWidget(self._file_list, stretch=2)
        cl.addSpacing(4)

        file_btns = QHBoxLayout()
        file_btns.setSpacing(6)
        btn_add_files = QPushButton("Add Files…")
        btn_add_folder = QPushButton("Add Folder…")
        btn_remove = QPushButton("Remove Selected")
        btn_add_files.clicked.connect(self._browse_add_files)
        btn_add_folder.clicked.connect(self._browse_add_folder)
        btn_remove.clicked.connect(self._remove_selected)
        file_btns.addWidget(btn_add_files)
        file_btns.addWidget(btn_add_folder)
        file_btns.addWidget(btn_remove)
        file_btns.addStretch()
        cl.addLayout(file_btns)
        cl.addSpacing(10)
        cl.addWidget(self._make_sep())
        cl.addSpacing(8)

        # ── Options ─────────────────────────────────────────────────────────
        cl.addWidget(self._section_lbl("OPTIONS"))
        cl.addSpacing(4)
        form = QFormLayout()
        form.setSpacing(6)
        form.setContentsMargins(0, 0, 0, 0)

        self._format_combo = QComboBox()
        for label, *_ in _FORMATS:
            self._format_combo.addItem(label)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("Format:", self._format_combo)

        slider_row = QWidget()
        sl = QHBoxLayout(slider_row)
        sl.setContentsMargins(0, 0, 0, 0)
        self._compression_slider = QSlider(Qt.Orientation.Horizontal)
        self._compression_slider.setRange(0, 9)
        self._compression_slider.setValue(6)
        self._compression_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._compression_slider.setTickInterval(1)
        self._compression_lbl = QLabel("6")
        self._compression_slider.valueChanged.connect(
            lambda v: self._compression_lbl.setText(str(v))
        )
        sl.addWidget(self._compression_slider)
        sl.addWidget(self._compression_lbl)
        self._compression_form_label = QLabel("Compression (0–9):")
        form.addRow(self._compression_form_label, slider_row)
        self._compression_slider_row = slider_row

        pwd_row = QWidget()
        pl = QHBoxLayout(pwd_row)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(4)
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

        self._pwd_picker = PasswordPickerButton(
            self._store if self._store is not None else get_password_store()
        )
        self._pwd_picker.password_selected.connect(self._password_edit.setText)
        pl.addWidget(self._password_edit)
        pl.addWidget(self._eye_btn)
        pl.addWidget(self._pwd_picker)
        self._password_form_label = QLabel("Password:")
        form.addRow(self._password_form_label, pwd_row)
        self._password_row = pwd_row

        cl.addLayout(form)
        cl.addSpacing(10)
        cl.addWidget(self._make_sep())
        cl.addSpacing(6)

        # ── Action bar ──────────────────────────────────────────────────────
        action = QHBoxLayout()
        action.setSpacing(8)
        self._trash_after_create = QCheckBox("Move sources to trash after creation")
        action.addWidget(self._trash_after_create)
        action.addStretch()
        self._create_btn = QPushButton("Create Archive")
        self._create_btn.clicked.connect(self._start_create)
        action.addWidget(self._create_btn)
        cl.addLayout(action)
        cl.addSpacing(6)

        # ── Log ─────────────────────────────────────────────────────────────
        self._log_widget = CollapsibleLog()
        cl.addWidget(self._log_widget)

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
        self._create_btn.setStyleSheet(
            f"QPushButton{{background:{c['accent']};color:white;border:none;"
            f"border-radius:6px;padding:5px 16px;font-weight:600;}}"
            f"QPushButton:hover{{background:{c['accent_hover']};}}"
            f"QPushButton:disabled{{background:{c['accent_disabled_bg']};color:#EEEEEE;}}"
        )
        self._log_widget.set_theme(c)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_format_changed(self, index: int) -> None:
        _, fmt, _ext, supports_password = _FORMATS[index]
        self._password_form_label.setVisible(supports_password)
        self._password_row.setVisible(supports_password)
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

            _notify("Archive created", os.path.basename(self._output_picker.path))
        else:
            self._log("✗ Archive creation failed.")
            self.status_changed.emit("Creation failed")

    def _trash_sources(self) -> None:
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

    def apply_settings(self, settings: AppSettings) -> None:
        self._trash_after_create.setChecked(settings.trash_after_create)

    def refresh_password_picker(self) -> None:
        self._pwd_picker.refresh()

    def handle_drop(self, path: str) -> None:
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
        self._log_widget.append(text)
