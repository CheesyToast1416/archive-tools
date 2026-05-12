from __future__ import annotations

import os
import shutil

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordStore, get_or_create_store
from archivetools.config.settings import AppSettings
from archivetools.gui.constants import ARCHIVE_FILTER as _ARCHIVE_FILTER
from archivetools.gui.dialogs.password_prompt_dialog import PasswordPromptDialog
from archivetools.gui.theme import LIGHT, ThemeColors
from archivetools.gui.widgets.archive_tree import ArchiveTreeWidget
from archivetools.gui.widgets.encoding_combo import EncodingComboBox
from archivetools.gui.widgets.password_picker_btn import PasswordPickerButton
from archivetools.gui.widgets.preview_pane import PreviewPane
from archivetools.gui.widgets.progress_dialog import ExtractionProgressDialog
from archivetools.gui.workers import (
    ExtractionWorker,
    InfoWorker,
    ListWorker,
    PreviewWorker,
    TestWorker,
    UpdateWorker,
)
from archivetools.operations import detect_archive_encoding
from archivetools.utils.notifications import notify as _notify
from archivetools.utils.trash import move_to_trash

_MainWorker = ListWorker | ExtractionWorker | TestWorker


# ── Drop-zone widget ──────────────────────────────────────────────────────────


class _DropZone(QFrame):
    """Dashed-border drop target shown when no archive is loaded."""

    file_dropped = Signal(str)
    browse_clicked = Signal()

    def __init__(self, colors: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._c: ThemeColors = colors
        self.setAcceptDrops(True)
        self.setFixedHeight(86)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("📦")
        icon_lbl.setStyleSheet("font-size: 26px;")

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._title_lbl = QLabel("Drop archive here")
        self._or_lbl = QLabel("or")
        sub_row = QHBoxLayout()
        sub_row.setSpacing(4)
        sub_row.addWidget(self._or_lbl)
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setFlat(True)
        self._browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._browse_btn.clicked.connect(self.browse_clicked)
        sub_row.addWidget(self._browse_btn)
        sub_row.addStretch()
        text_col.addWidget(self._title_lbl)
        text_col.addLayout(sub_row)

        layout.addWidget(icon_lbl)
        layout.addLayout(text_col)

        self.set_theme(colors)

    def set_theme(self, c: ThemeColors) -> None:
        self._c = c
        self._title_lbl.setStyleSheet(
            f"font-size:13px;font-weight:600;color:{c['text']};"
        )
        self._or_lbl.setStyleSheet(f"color:{c['text_secondary']};")
        self._browse_btn.setStyleSheet(
            f"QPushButton{{color:{c['accent']};font-weight:600;border:none;padding:0;}}"
            f"QPushButton:hover{{color:{c['accent_hover']};}}"
        )
        self._apply_idle()

    def _apply_idle(self) -> None:
        c = self._c
        self.setStyleSheet(
            f"QFrame{{border:none;border-radius:10px;background:{c['surface']};}}"
        )

    def _apply_hover(self) -> None:
        c = self._c
        self.setStyleSheet(
            f"QFrame{{border:none;border-radius:10px;background:{c['drop_zone_hover_bg']};}}"
        )

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(
            u.isLocalFile() for u in event.mimeData().urls()
        ):
            self._apply_hover()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._apply_idle()

    def dropEvent(self, event) -> None:  # noqa: N802
        self._apply_idle()
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.file_dropped.emit(urls[0].toLocalFile())
        event.acceptProposedAction()


# ── Extract panel ─────────────────────────────────────────────────────────────


class ExtractPanel(QWidget):
    """Extraction panel: drop-zone, compact options, tree view, preview/info pane."""

    status_changed = Signal(str)
    archive_opened = Signal(str)
    # Emitted whenever the (has_archive, contents_ready) state changes
    archive_state_changed = Signal(bool, bool)

    def __init__(
        self,
        settings: AppSettings | None = None,
        store: PasswordStore | None = None,
        colors: ThemeColors | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._colors: ThemeColors = colors or LIGHT
        self._worker: _MainWorker | None = None
        self._preview_token: int = 0
        self._active_preview_workers: set = set()
        self._inspector_worker: InfoWorker | None = None
        self._update_worker: UpdateWorker | None = None
        self._preview_valid = False
        self._preview_names: list[str] = []
        self._preview_tmpdir: str | None = None
        self._progress_dialog: ExtractionProgressDialog | None = None
        self._current_path: str = ""
        self._op_password: str = ""  # password used when the current op was started
        self._store = store
        self._option_labels: list[QLabel] = []
        self._build_ui()
        if settings is not None:
            self.apply_settings(settings)

    # ── UI construction ───────────────────────────────────────────────────────

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

        # ── Zone 1: identify the archive ─────────────────────────────────────
        self._archive_section = QStackedWidget()
        self._drop_zone = _DropZone(self._colors)
        self._drop_zone.file_dropped.connect(self._set_archive_path)
        self._drop_zone.browse_clicked.connect(self._browse_archive)
        self._archive_section.addWidget(self._drop_zone)  # 0
        self._archive_section.addWidget(self._build_archive_bar())  # 1
        cl.addWidget(self._archive_section)
        cl.addSpacing(8)
        cl.addWidget(self._make_sep())
        cl.addSpacing(8)

        # ── Zone 2: explore (tree | preview) — takes all available height ────
        self._tree_widget = ArchiveTreeWidget(self._colors)
        self._tree_widget.entry_selected.connect(self._on_entry_selected)
        self._tree_widget.edit_mode_changed.connect(self._on_edit_mode_changed)
        self._tree_widget.entries_modified.connect(self._on_entries_modified)
        self._tree_widget.status_message.connect(self._log)

        self._preview_pane = PreviewPane(self._colors)
        self._preview_pane.info_requested.connect(self._on_info_requested)
        self._preview_pane.preview_requested.connect(self._start_preview)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree_widget)
        splitter.addWidget(self._preview_pane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([370, 240])
        cl.addWidget(splitter, stretch=1)

        cl.addSpacing(8)
        cl.addWidget(self._make_sep())
        cl.addSpacing(6)

        # ── Zone 3: configure & act ───────────────────────────────────────────
        cl.addWidget(self._build_bottom_strip())
        cl.addSpacing(4)
        cl.addWidget(self._build_log_section())

        outer.addWidget(content)

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_archive_bar(self) -> QWidget:
        """Compact bar shown once an archive path is set."""
        bar = QWidget()
        bar.setFixedHeight(44)
        self._archive_bar_bg = bar  # stored for theme updates
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        file_icon = QLabel()
        file_icon.setPixmap(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon).pixmap(18, 18)
        )
        self._archive_name_lbl = QLabel()
        self._archive_name_lbl.setStyleSheet("font-weight:600;font-size:13px;")
        self._archive_dir_lbl = QLabel()
        self._archive_dir_lbl.setStyleSheet("color:#888888;font-size:11px;")

        clear_btn = QToolButton()
        clear_btn.setText("✕")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QToolButton{border:none;color:#888888;font-size:14px;padding:2px 4px;}"
            "QToolButton:hover{color:#333333;}"
        )
        clear_btn.clicked.connect(self._clear_archive)

        layout.addWidget(file_icon)
        layout.addWidget(self._archive_name_lbl)
        layout.addWidget(self._archive_dir_lbl, stretch=1)
        layout.addWidget(clear_btn)
        return bar

    def _build_bottom_strip(self) -> QWidget:
        """Password + output options, collapsible encodings, and action buttons."""
        strip = QWidget()
        vbox = QVBoxLayout(strip)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        def _lbl(text: str) -> QLabel:
            lbl = QLabel(text)
            self._option_labels.append(lbl)
            return lbl

        def _form() -> QFormLayout:
            f = QFormLayout()
            f.setContentsMargins(0, 0, 0, 0)
            f.setSpacing(6)
            f.setHorizontalSpacing(8)
            f.setLabelAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            return f

        # ── Password ─────────────────────────────────────────────────────────
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password")
        self._eye_btn = QToolButton()
        self._eye_btn.setCheckable(True)
        self._eye_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
        )
        self._eye_btn.setToolTip("Show / hide password")
        self._eye_btn.toggled.connect(self._toggle_password_visibility)
        self._pwd_picker = PasswordPickerButton(get_or_create_store(self._store))
        self._pwd_picker.password_selected.connect(self._password_edit.setText)

        pwd_widget = QWidget()
        pl = QHBoxLayout(pwd_widget)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(4)
        pl.addWidget(self._password_edit)
        pl.addWidget(self._eye_btn)
        pl.addWidget(self._pwd_picker)

        # ── Output + trash ────────────────────────────────────────────────────
        self._output_path_edit = QLineEdit()
        self._output_path_edit.setPlaceholderText("Default (next to archive)")
        output_browse = QToolButton()
        output_browse.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        output_browse.setToolTip("Choose output directory")
        output_browse.clicked.connect(self._browse_output)
        self._trash_after_extract = QCheckBox("Move to trash after extraction")

        out_widget = QWidget()
        ol = QHBoxLayout(out_widget)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(4)
        ol.addWidget(self._output_path_edit)
        ol.addWidget(output_browse)
        ol.addSpacing(8)
        ol.addWidget(self._trash_after_extract)

        main_form = _form()
        main_form.addRow(_lbl("Password:"), pwd_widget)
        main_form.addRow(_lbl("Output:"), out_widget)
        vbox.addLayout(main_form)

        # ── Advanced (encodings, collapsed by default) ────────────────────────
        self._advanced_toggle = QPushButton("▸  Advanced")
        self._advanced_toggle.setFlat(True)
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._advanced_toggle.toggled.connect(self._toggle_advanced)
        vbox.addWidget(self._advanced_toggle)

        self._advanced_widget = QWidget()
        self._filename_encoding_combo = EncodingComboBox()
        self._pwd_encoding_combo = EncodingComboBox()
        adv_form = _form()
        adv_form.addRow(_lbl("Filename enc:"), self._filename_encoding_combo)
        adv_form.addRow(_lbl("Password enc:"), self._pwd_encoding_combo)
        self._advanced_widget.setLayout(adv_form)
        self._advanced_widget.setVisible(False)
        vbox.addWidget(self._advanced_widget)

        # ── Action bar ────────────────────────────────────────────────────────
        action = QHBoxLayout()
        action.setSpacing(6)

        self._test_btn = QPushButton("Test")
        self._test_btn.setEnabled(False)
        self._test_btn.clicked.connect(self._start_test)

        self._edit_archive_btn = QPushButton("Edit Archive")
        self._edit_archive_btn.setEnabled(False)
        self._edit_archive_btn.clicked.connect(self._tree_widget.enter_edit_mode)

        self._extract_btn = QPushButton("Extract")
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._start_extract)

        self._edit_add_btn = QPushButton("Add Files…")
        self._edit_add_btn.clicked.connect(self._tree_widget.browse_add)
        self._edit_add_btn.setVisible(False)

        self._edit_cancel_btn = QPushButton("Cancel")
        self._edit_cancel_btn.clicked.connect(self._tree_widget.exit_edit_mode)
        self._edit_cancel_btn.setVisible(False)

        self._edit_save_btn = QPushButton("Save")
        self._edit_save_btn.clicked.connect(self._tree_widget.save_edits)
        self._edit_save_btn.setVisible(False)

        action.addWidget(self._test_btn)
        action.addWidget(self._edit_archive_btn)
        action.addWidget(self._edit_add_btn)
        action.addStretch()
        action.addWidget(self._edit_cancel_btn)
        action.addWidget(self._edit_save_btn)
        action.addWidget(self._extract_btn)
        vbox.addLayout(action)

        return strip

    def _build_log_section(self) -> QWidget:
        section = QWidget()
        vbox = QVBoxLayout(section)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._log_toggle_btn = QPushButton("▸  Log")
        self._log_toggle_btn.setFlat(True)
        self._log_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._log_toggle_btn.setStyleSheet(
            "QPushButton{text-align:left;color:#888888;font-size:12px;"
            "padding:3px 0;border:none;}"
            "QPushButton:hover{color:#1C1C1E;}"
        )
        self._log_toggle_btn.clicked.connect(self._toggle_log)
        self._log_last_lbl = QLabel("")
        self._log_last_lbl.setStyleSheet("color:#AAAAAA;font-size:11px;")
        header.addWidget(self._log_toggle_btn)
        header.addWidget(self._log_last_lbl, stretch=1)
        vbox.addLayout(header)

        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumBlockCount(2000)
        self._log_edit.setFixedHeight(110)
        self._log_edit.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self._log_edit.setVisible(False)
        vbox.addWidget(self._log_edit)
        return section

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        return sep

    # ── Theme ─────────────────────────────────────────────────────────────────

    def set_theme(self, c: ThemeColors) -> None:
        self._colors = c
        # Drop zone
        self._drop_zone.set_theme(c)
        # Archive bar background
        self._archive_bar_bg.setStyleSheet(
            f"background:{c['surface']};border-radius:8px;"
        )
        self._archive_name_lbl.setStyleSheet(
            f"font-weight:600;font-size:13px;color:{c['text']};"
        )
        self._archive_dir_lbl.setStyleSheet(
            f"color:{c['text_secondary']};font-size:11px;"
        )
        # Option/form labels
        for lbl in self._option_labels:
            lbl.setStyleSheet(f"color:{c['text_secondary']};font-size:12px;")
        # Trash checkbox
        self._trash_after_extract.setStyleSheet(
            f"font-size:12px;color:{c['text_secondary']};"
        )
        # Advanced toggle
        self._advanced_toggle.setStyleSheet(
            f"QPushButton{{text-align:left;color:{c['text_secondary']};"
            f"font-size:12px;padding:2px 0;border:none;}}"
            f"QPushButton:hover{{color:{c['text']};}}"
        )
        # Tree widget + preview pane
        self._tree_widget.set_theme(c)
        self._preview_pane.set_theme(c)
        # Extract (primary) button
        self._extract_btn.setStyleSheet(
            f"QPushButton{{background:{c['accent']};color:white;border:none;"
            f"border-radius:6px;padding:5px 16px;font-weight:600;}}"
            f"QPushButton:hover{{background:{c['accent_hover']};}}"
            f"QPushButton:disabled{{background:{c['accent_disabled_bg']};color:#EEEEEE;}}"
        )
        # Log
        self._log_toggle_btn.setStyleSheet(
            f"QPushButton{{text-align:left;color:{c['text_secondary']};font-size:12px;"
            f"padding:3px 0;border:none;}}"
            f"QPushButton:hover{{color:{c['text']};}}"
        )
        self._log_last_lbl.setStyleSheet(f"color:{c['text_dim']};font-size:11px;")

    # ── Archive path management ───────────────────────────────────────────────

    def _set_archive_path(self, path: str) -> None:
        path = path.strip()
        if path == self._current_path:
            return
        self._current_path = path
        if path:
            self._archive_name_lbl.setText(os.path.basename(path))
            self._archive_dir_lbl.setText(os.path.dirname(path))
            self._archive_section.setCurrentIndex(1)
        else:
            self._archive_section.setCurrentIndex(0)
        self._on_archive_changed()

    def _clear_archive(self) -> None:
        self._set_archive_path("")

    def _browse_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Archive", "", _ARCHIVE_FILTER)
        if path:
            self._set_archive_path(path)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_archive_changed(self) -> None:
        self._preview_pane.stop_media()
        self._preview_token += 1  # discard any in-flight preview results
        has_path = bool(self._current_path)
        self._test_btn.setEnabled(False)
        self._extract_btn.setEnabled(False)
        self._edit_archive_btn.setEnabled(False)
        self._preview_valid = False
        self._preview_names = []
        self._tree_widget.clear()
        self._filename_encoding_combo.reset_detected()
        self._preview_pane.clear()
        self._cleanup_preview_tmpdir()
        self.archive_state_changed.emit(has_path, False)
        if has_path:
            self.archive_opened.emit(self._current_path)
            self._start_list()  # auto-list contents immediately

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
            self._output_path_edit.setText(path)

    def _start_list(self) -> None:
        if not self._current_path:
            return
        self._op_password = self._password_edit.text()
        self._tree_widget.clear()
        self._preview_valid = False
        self._extract_btn.setEnabled(False)
        self._log("─" * 60)

        worker = ListWorker(
            self._current_path,
            self._password_edit.text(),
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
        )
        worker.result.connect(self._on_list_finished)
        worker.error.connect(self._on_list_error)
        worker.log_message.connect(self._log)
        self._start_worker(worker)

    def _start_test(self) -> None:
        if not self._current_path:
            return
        self._log("─" * 60)
        self._log("Testing archive integrity…")
        worker = TestWorker(
            self._current_path,
            self._password_edit.text(),
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
        )
        worker.result.connect(self._on_test_finished)
        worker.error.connect(self._on_test_error)
        worker.log_message.connect(self._log)
        self._start_worker(worker)

    def _start_extract(self) -> None:
        if not self._current_path:
            return
        self._op_password = self._password_edit.text()
        self._log("─" * 60)

        archive_name = os.path.basename(self._current_path)
        self._progress_dialog = ExtractionProgressDialog(
            archive_name, parent=self.window()
        )
        self._progress_dialog.show()

        worker = ExtractionWorker(
            self._current_path,
            self._password_edit.text(),
            self._output_path_edit.text().strip(),
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
            names=self._preview_names or None,
        )
        worker.result.connect(self._on_extract_finished)
        worker.error.connect(self._on_extract_error)
        worker.log_message.connect(self._log)
        worker.file_progress.connect(self._on_file_progress)
        worker.file_progress.connect(
            lambda c, t, f: self._progress_dialog.update_file_progress(c, t, f)
            if self._progress_dialog
            else None
        )
        worker.bytes_progress.connect(
            lambda d, s: self._progress_dialog.update_bytes_progress(d, s)
            if self._progress_dialog
            else None
        )
        self._start_worker(worker)

    def _start_worker(self, worker: _MainWorker) -> None:
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
            self._tree_widget.populate(names)
            self._preview_valid = True
            self._preview_names = list(names)
            self._extract_btn.setEnabled(True)
            self._edit_archive_btn.setEnabled(True)
            self._log(
                f"✓ Preview ready — {len(names)} entries  (encoding: {enc or 'auto'})"
            )
            self.status_changed.emit(f"Preview: {len(names)} entries")
            self.archive_state_changed.emit(True, True)
            self._run_filename_detection()
        else:
            had_pwd = bool(self._op_password)
            if had_pwd:
                self._log("✗ Wrong password — could not read archive.")
                self.status_changed.emit("Wrong password")
            msg = (
                "Incorrect password.\nEnter the correct password to try again."
                if had_pwd
                else "This archive is password-protected.\n"
                "Enter the password to load its contents."
            )
            password = self._prompt_for_password(msg)
            if password is not None:
                self._password_edit.setText(password)
                self._start_list()
            elif not had_pwd:
                self._log("✗ Archive requires a password.")
                self.status_changed.emit("Password required")

    def _on_list_error(self, msg: str) -> None:
        self._set_busy(False)
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Error")

    def _on_extract_finished(self, ok: bool, enc: str) -> None:
        self._set_busy(False)
        if self._progress_dialog:
            if ok:
                self._progress_dialog.set_done()
            self._progress_dialog.hide()
            self._progress_dialog = None
        if ok:
            self._log(f"✓ Extraction complete  (encoding: {enc or 'auto'})")
            self.status_changed.emit("Extraction complete")
            if self._trash_after_extract.isChecked():
                self._trash_archive()
            _notify("Extraction complete", os.path.basename(self._current_path))
        else:
            had_pwd = bool(self._op_password)
            if had_pwd:
                self._log("✗ Wrong password — extraction failed.")
                self.status_changed.emit("Wrong password")
            msg = (
                "Incorrect password.\nEnter the correct password to try again."
                if had_pwd
                else "This archive is password-protected.\n"
                "Enter the password to extract."
            )
            password = self._prompt_for_password(msg)
            if password is not None:
                self._password_edit.setText(password)
                self._start_extract()
            elif not had_pwd:
                self._log("✗ Archive requires a password.")
                self.status_changed.emit("Password required")

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
        if self._progress_dialog:
            self._progress_dialog.hide()
            self._progress_dialog = None
        self._log(f"✗ Error: {msg}")
        self.status_changed.emit("Error")

    def _on_file_progress(self, current: int, total: int, filename: str) -> None:
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
            self.status_changed.emit(f"Extracting {current}/{total}: {filename}")

    # ── Tree selection → right pane ───────────────────────────────────────────

    def _on_entry_selected(self, full_path: str) -> None:
        self._preview_pane.set_entry(full_path)
        if not full_path or full_path.endswith("/"):
            if self._preview_pane.is_preview_mode():
                self._preview_pane.show_placeholder()
            return
        if self._preview_pane.is_preview_mode() and self._worker is None:
            self._start_preview(full_path)

    def _on_edit_mode_changed(self, entering: bool) -> None:
        self._test_btn.setVisible(not entering)
        self._extract_btn.setVisible(not entering)
        self._edit_archive_btn.setVisible(not entering)
        self._edit_add_btn.setVisible(entering)
        self._edit_cancel_btn.setVisible(entering)
        self._edit_save_btn.setVisible(entering)

    def _on_entries_modified(self, files_to_add: list, paths_to_remove: list) -> None:
        self._start_update(files_to_add, paths_to_remove)

    def _on_info_requested(self) -> None:
        if not self._current_path or self._inspector_worker is not None:
            return
        self._inspector_worker = InfoWorker(self._current_path)
        self._inspector_worker.result.connect(self._preview_pane.show_info)
        self._inspector_worker.error.connect(self._preview_pane.show_info_error)
        self._inspector_worker.finished.connect(self._inspector_worker.deleteLater)
        self._inspector_worker.finished.connect(
            lambda: setattr(self, "_inspector_worker", None)
        )
        self._inspector_worker.start()

    def _start_preview(self, entry_name: str) -> None:
        self._preview_pane.stop_media()
        self._op_password = self._password_edit.text()
        self._preview_token += 1
        token = self._preview_token
        self._preview_pane.show_loading_preview()

        worker = PreviewWorker(
            self._current_path,
            entry_name,
            self._password_edit.text(),
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
        )
        self._active_preview_workers.add(worker)

        def _on_result(tmpdir: str, file_path: str) -> None:
            if token == self._preview_token:
                self._cleanup_preview_tmpdir()
                self._on_preview_result(tmpdir, file_path)
            else:
                shutil.rmtree(tmpdir, ignore_errors=True)

        def _on_error(msg: str) -> None:
            if token == self._preview_token:
                self._on_preview_error(msg)

        def _on_done() -> None:
            self._active_preview_workers.discard(worker)

        worker.result.connect(_on_result)
        worker.error.connect(_on_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(_on_done)
        worker.start()

    def _on_preview_result(self, tmpdir: str, file_path: str) -> None:
        self._preview_tmpdir = tmpdir
        self._preview_pane.show_file(file_path)

    def _on_preview_error(self, _msg: str) -> None:
        self._preview_pane.show_unsupported()
        had_pwd = bool(self._op_password)
        msg = (
            "Incorrect password — could not extract the file for preview.\n"
            "Enter the correct password to try again."
            if had_pwd
            else "This archive encrypts file contents.\n"
            "Enter the password to preview files."
        )
        password = self._prompt_for_password(msg)
        if password is not None:
            self._password_edit.setText(password)
            entry = self._tree_widget.current_entry()
            if entry and not entry.endswith("/"):
                self._start_preview(entry)

    # ── Edit mode (tree delegates, panel manages buttons + worker) ────────────

    def _start_update(self, files_to_add: list, paths_to_remove: list) -> None:
        if not self._current_path:
            return
        if not paths_to_remove and not files_to_add:
            self._tree_widget.exit_edit_mode()
            return
        self._log("─" * 60)
        self._log(
            f"Updating archive: removing {len(paths_to_remove)}, "
            f"adding {len(files_to_add)} file(s)…"
        )
        worker = UpdateWorker(
            self._current_path,
            files_to_add,
            paths_to_remove,
        )
        worker.result.connect(self._on_update_finished)
        worker.error.connect(self._on_update_error)
        worker.log_message.connect(self._log)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: setattr(self, "_update_worker", None))
        self._update_worker = worker
        self._set_busy(True)
        worker.start()

    def _on_update_finished(self, ok: bool) -> None:
        self._set_busy(False)
        self._tree_widget.exit_edit_mode()
        if ok:
            self._log("✓ Archive updated.")
            self.status_changed.emit("Archive updated")
            self._start_list()
        else:
            self._log("✗ Update failed.")
            self.status_changed.emit("Update failed")

    def _on_update_error(self, msg: str) -> None:
        self._set_busy(False)
        self._tree_widget.exit_edit_mode()
        self._log(f"✗ Update error: {msg}")
        self.status_changed.emit("Update error")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        has_path = bool(self._current_path)
        self._test_btn.setEnabled(not busy and has_path)
        self._extract_btn.setEnabled(not busy and self._preview_valid)
        self._edit_archive_btn.setEnabled(not busy and self._preview_valid)
        if busy:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setVisible(True)
        else:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(1)
            self._progress_bar.setVisible(False)

    def _log(self, text: str) -> None:
        self._log_edit.appendPlainText(text)
        self._log_last_lbl.setText(text[:70])
        if text.startswith("✗") and not self._log_edit.isVisible():
            self._toggle_log()

    def _prompt_for_password(self, message: str) -> str | None:
        """Modal password-entry dialog. Returns entered text, or None if cancelled."""
        dlg = PasswordPromptDialog(message, store=self._store, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.password()
        return None

    def _toggle_advanced(self, checked: bool) -> None:
        self._advanced_widget.setVisible(checked)
        self._advanced_toggle.setText("▾  Advanced" if checked else "▸  Advanced")

    def _toggle_log(self) -> None:
        visible = not self._log_edit.isVisible()
        self._log_edit.setVisible(visible)
        self._log_toggle_btn.setText("▾  Log" if visible else "▸  Log")

    def _cleanup_preview_tmpdir(self) -> None:
        if self._preview_tmpdir:
            shutil.rmtree(self._preview_tmpdir, ignore_errors=True)
            self._preview_tmpdir = None

    # ── Public action entry-points (called from menu bar) ─────────────────────

    def close_archive(self) -> None:
        self._clear_archive()

    def reload(self) -> None:
        if self._current_path:
            self._start_list()

    def extract(self) -> None:
        if self._preview_valid:
            self._start_extract()

    def test_integrity(self) -> None:
        if self._current_path:
            self._start_test()

    def apply_settings(self, settings: AppSettings) -> None:
        self._pwd_encoding_combo.set_codec(settings.default_password_encoding)
        self._filename_encoding_combo.set_codec(settings.default_filename_encoding)
        self._trash_after_extract.setChecked(settings.trash_after_extract)
        if settings.default_output_dir:
            self._output_path_edit.setText(settings.default_output_dir)

    def refresh_password_picker(self) -> None:
        self._pwd_picker.refresh()

    def handle_drop(self, path: str) -> None:
        self._set_archive_path(path)

    def _trash_archive(self) -> None:
        if not self._current_path:
            return
        if move_to_trash(self._current_path):
            self._log(f"  Moved to trash: {self._current_path}")
        else:
            self._log(f"  ⚠ Could not move to trash: {self._current_path}")

    def _run_filename_detection(self) -> None:
        if not self._current_path:
            return
        codec, confidence = detect_archive_encoding(self._current_path)
        if codec and confidence >= 0.5:
            self._filename_encoding_combo.set_detected(codec, confidence)
            self._log(
                f"  filename encoding detected: {codec.upper()} "
                f"({confidence:.0%} confidence)"
            )
