from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.widgets.encoding_combo import EncodingComboBox
from archivetools.gui.widgets.progress_dialog import ExtractionProgressDialog
from archivetools.gui.workers import BatchExtractionWorker

_ARCHIVE_FILTER = (
    "Archives (*.zip *.rar *.7z *.z01 *.r00 *.001 *.tar *.tar.gz *.tgz "
    "*.tar.bz2 *.tar.xz);;"
    "All files (*)"
)

_COL_ARCHIVE = 0
_COL_STATUS = 1
_COL_DETAIL = 2

_STATUS_PENDING = "Pending"
_STATUS_RUNNING = "Extracting…"
_STATUS_OK = "✓ Done"
_STATUS_FAIL = "✗ Failed"


class _QueueTable(QTableWidget):
    """Table that accepts dropped archive files."""

    paths_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 3, parent)
        self.setAcceptDrops(True)
        self.setHorizontalHeaderLabels(["Archive", "Status", "Details"])
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        h = self.horizontalHeader()
        h.setSectionResizeMode(_COL_ARCHIVE, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(_COL_DETAIL, QHeaderView.ResizeMode.ResizeToContents)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.paths_dropped.emit(paths)
        event.acceptProposedAction()


class BatchPanel(QWidget):
    """Batch extraction: queue multiple archives, extract with shared settings."""

    status_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: BatchExtractionWorker | None = None
        self._progress_dialog: ExtractionProgressDialog | None = None
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
        outer.addWidget(self._build_queue_group(), stretch=3)
        outer.addWidget(self._build_options_group())
        outer.addWidget(self._build_run_row())
        outer.addWidget(self._build_log_group(), stretch=1)

    def _build_queue_group(self) -> QGroupBox:
        box = QGroupBox("Queue  (drag & drop archives or use buttons)")
        layout = QVBoxLayout(box)

        self._table = _QueueTable()
        self._table.paths_dropped.connect(self._add_paths)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add Archives…")
        btn_remove = QPushButton("Remove Selected")
        btn_clear = QPushButton("Clear All")
        btn_add.clicked.connect(self._browse_add)
        btn_remove.clicked.connect(self._remove_selected)
        btn_clear.clicked.connect(self._clear_all)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    def _build_options_group(self) -> QGroupBox:
        box = QGroupBox("Shared Options")
        form = QFormLayout(box)

        # Password + eye
        pwd_row = QWidget()
        pwd_layout = QHBoxLayout(pwd_row)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(4)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password for all archives")
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

        self._pwd_encoding = EncodingComboBox()
        form.addRow("Password encoding:", self._pwd_encoding)

        self._fname_encoding = EncodingComboBox()
        form.addRow("Filename encoding:", self._fname_encoding)

        self._output_picker = ArchivePickerWidget(
            placeholder="Default (next to each archive)",
            file_filter="",
        )
        # Hijack browse button to open directory dialog
        browse_btn = self._output_picker.findChild(QPushButton)
        if browse_btn:
            browse_btn.clicked.disconnect()
            browse_btn.clicked.connect(self._browse_output)
        form.addRow("Output directory:", self._output_picker)

        return box

    def _build_run_row(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._trash_after_batch = QCheckBox(
            "Move archives to trash after successful extraction"
        )
        outer.addWidget(self._trash_after_batch)

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self._overall_lbl = QLabel("")
        self._extract_btn = QPushButton("Extract All")
        self._extract_btn.clicked.connect(self._start_batch)
        layout.addWidget(self._overall_lbl, stretch=1)
        layout.addWidget(self._extract_btn)
        outer.addWidget(row)
        return container

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(4000)
        self._log_edit.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        layout.addWidget(self._log_edit)
        return box

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _browse_add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Archives", "", _ARCHIVE_FILTER
        )
        self._add_paths(paths)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self._output_picker.set_path(path)

    def _remove_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()}, reverse=True
        )
        for r in rows:
            self._table.removeRow(r)

    def _clear_all(self) -> None:
        self._table.setRowCount(0)

    def _toggle_password_visibility(self, checked: bool) -> None:
        self._password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self._eye_btn.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogYesButton
                if checked
                else QStyle.StandardPixmap.SP_DialogNoButton
            )
        )

    def _add_paths(self, paths: list[str]) -> None:
        existing = {
            self._table.item(r, _COL_ARCHIVE).text()
            for r in range(self._table.rowCount())
            if self._table.item(r, _COL_ARCHIVE)
        }
        for p in paths:
            if p not in existing:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._table.setItem(row, _COL_ARCHIVE, QTableWidgetItem(p))
                status_item = QTableWidgetItem(_STATUS_PENDING)
                status_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self._table.setItem(row, _COL_STATUS, status_item)
                self._table.setItem(row, _COL_DETAIL, QTableWidgetItem(""))
                existing.add(p)

    def _start_batch(self) -> None:
        n = self._table.rowCount()
        if n == 0:
            self._log("✗ Queue is empty — add archives first.")
            return

        archives = [
            self._table.item(r, _COL_ARCHIVE).text()
            for r in range(n)
            if self._table.item(r, _COL_ARCHIVE)
        ]

        # Reset status column
        for r in range(n):
            self._set_row_status(r, _STATUS_PENDING, "")

        self._overall_lbl.setText(f"0 / {n}")
        self._log("─" * 60)

        # Show progress popup for the current archive
        self._progress_dialog = ExtractionProgressDialog(
            "Batch extraction", self.window()
        )
        self._progress_dialog.show()

        worker = BatchExtractionWorker(
            archives,
            self._output_picker.path,
            self._password_edit.text(),
            self._fname_encoding.current_codec(),
            self._pwd_encoding.current_codec(),
        )
        worker.archive_started.connect(self._on_archive_started)
        worker.archive_done.connect(self._on_archive_done)
        worker.file_progress.connect(self._on_file_progress)
        worker.bytes_progress.connect(
            lambda d, s: self._progress_dialog.update_bytes_progress(d, s)
            if self._progress_dialog
            else None
        )
        worker.result.connect(self._on_batch_finished)
        worker.error.connect(self._on_batch_error)
        worker.log_message.connect(self._log)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_worker_done)
        self._worker = worker
        self._set_busy(True)
        worker.start()

    def _on_archive_started(self, index: int) -> None:
        self._set_row_status(index, _STATUS_RUNNING, "")
        self._table.scrollToItem(self._table.item(index, _COL_STATUS))
        archive = self._table.item(index, _COL_ARCHIVE)
        name = os.path.basename(archive.text()) if archive else f"#{index + 1}"
        if self._progress_dialog:
            self._progress_dialog.setWindowTitle(f"Extracting: {name}")
        n = self._table.rowCount()
        self._overall_lbl.setText(f"{index} / {n}")
        self._log(f"[{index + 1}/{n}] {name}")

    def _on_archive_done(self, index: int, ok: bool, detail: str) -> None:
        status = _STATUS_OK if ok else _STATUS_FAIL
        self._set_row_status(index, status, detail)
        n = self._table.rowCount()
        done = sum(
            1
            for r in range(n)
            if self._table.item(r, _COL_STATUS)
            and self._table.item(r, _COL_STATUS).text() in (_STATUS_OK, _STATUS_FAIL)
        )
        self._overall_lbl.setText(f"{done} / {n}")

    def _on_file_progress(self, current: int, total: int, filename: str) -> None:
        if self._progress_dialog:
            self._progress_dialog.update_file_progress(current, total, filename)

    def _on_batch_finished(self, ok_count: int, fail_count: int) -> None:
        self._set_busy(False)
        if self._progress_dialog:
            self._progress_dialog.set_done()
            self._progress_dialog.hide()
            self._progress_dialog = None
        total = ok_count + fail_count
        self._overall_lbl.setText(f"{total} / {total}")
        self._log(f"✓ Batch complete — {ok_count} succeeded, {fail_count} failed.")
        self.status_changed.emit(f"Batch: {ok_count}/{total} succeeded")
        if self._trash_after_batch.isChecked() and ok_count > 0:
            self._trash_successful_archives()

    def _on_batch_error(self, msg: str) -> None:
        self._set_busy(False)
        if self._progress_dialog:
            self._progress_dialog.hide()
            self._progress_dialog = None
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Batch error")

    def _on_worker_done(self) -> None:
        self._worker = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def handle_drop(self, path: str) -> None:
        self._add_paths([path])

    def _trash_successful_archives(self) -> None:
        from archivetools.utils.trash import move_to_trash

        n = self._table.rowCount()
        for r in range(n):
            status_item = self._table.item(r, _COL_STATUS)
            if status_item and status_item.text() == _STATUS_OK:
                archive_item = self._table.item(r, _COL_ARCHIVE)
                if archive_item:
                    path = archive_item.text()
                    if move_to_trash(path):
                        self._log(f"  Moved to trash: {os.path.basename(path)}")
                    else:
                        self._log(f"  ⚠ Could not trash: {path}")

    def _set_busy(self, busy: bool) -> None:
        self._extract_btn.setEnabled(not busy)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(1)
            self._progress_bar.setVisible(False)

    def _set_row_status(self, row: int, status: str, detail: str) -> None:
        if status_item := self._table.item(row, _COL_STATUS):
            status_item.setText(status)
        if detail_item := self._table.item(row, _COL_DETAIL):
            detail_item.setText(detail)

    def _log(self, text: str) -> None:
        self._log_edit.appendPlainText(text)
