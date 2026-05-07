from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordStore, get_password_store
from archivetools.config.settings import AppSettings
from archivetools.encoding.detect import (
    detect_rar_filename_encoding,
    detect_zip_filename_encoding,
)
from archivetools.gui.constants import ARCHIVE_FILTER as _ARCHIVE_FILTER
from archivetools.gui.theme import LIGHT, ThemeColors
from archivetools.gui.widgets.encoding_combo import EncodingComboBox
from archivetools.gui.widgets.password_picker_btn import PasswordPickerButton
from archivetools.gui.widgets.progress_dialog import ExtractionProgressDialog
from archivetools.gui.workers import (
    ExtractionWorker,
    InfoWorker,
    ListWorker,
    PreviewWorker,
    TestWorker,
    UpdateWorker,
)
from archivetools.utils.notifications import notify as _notify
from archivetools.utils.trash import move_to_trash

_MainWorker = ListWorker | ExtractionWorker | TestWorker

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico", ".tiff"}
_TEXT_EXTS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".css",
    ".html",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".log",
    ".sh",
    ".bash",
    ".diff",
    ".patch",
    ".rst",
    ".csv",
    ".c",
    ".h",
    ".cpp",
    ".java",
    ".rb",
    ".go",
    ".zsh",
    ".fish",
}

# Right-pane stack page indices
_RIGHT_PLACEHOLDER = 0
_RIGHT_IMAGE = 1
_RIGHT_TEXT = 2
_RIGHT_UNSUPPORTED = 3
_RIGHT_LOADING_PREVIEW = 4
_RIGHT_INFO = 5
_RIGHT_LOADING_INFO = 6


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
        self._preview_worker: PreviewWorker | None = None
        self._inspector_worker: InfoWorker | None = None
        self._update_worker: UpdateWorker | None = None
        self._preview_valid = False
        self._preview_names: list[str] = []
        self._preview_tmpdir: str | None = None
        self._archive_info_cache = None
        self._progress_dialog: ExtractionProgressDialog | None = None
        self._edit_mode = False
        self._edit_remove: set[str] = set()
        self._edit_add: list[str] = []
        self._current_path: str = ""
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

        # Slim indeterminate progress bar at very top
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setVisible(False)
        outer.addWidget(self._progress_bar)

        # Padded content area
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 12, 16, 10)
        cl.setSpacing(0)

        # Archive section (drop-zone ↔ archive bar)
        self._archive_section = QStackedWidget()
        self._drop_zone = _DropZone(self._colors)
        self._drop_zone.file_dropped.connect(self._set_archive_path)
        self._drop_zone.browse_clicked.connect(self._browse_archive)
        self._archive_section.addWidget(self._drop_zone)  # index 0
        self._archive_section.addWidget(self._build_archive_bar())  # index 1
        cl.addWidget(self._archive_section)
        cl.addSpacing(10)

        # Compact options strip (two rows, no borders)
        cl.addWidget(self._build_options_strip())
        cl.addSpacing(10)

        cl.addWidget(self._make_sep())
        cl.addSpacing(6)

        # Action bar
        cl.addWidget(self._build_action_bar())
        cl.addSpacing(6)

        cl.addWidget(self._make_sep())
        cl.addSpacing(8)

        # Main content: tree (left) | preview/info (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_tree_pane())
        splitter.addWidget(self._build_right_pane())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([370, 240])
        cl.addWidget(splitter, stretch=1)

        cl.addSpacing(6)

        # Collapsible log
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

    def _build_options_strip(self) -> QWidget:
        strip = QWidget()
        vbox = QVBoxLayout(strip)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        def _lbl(text: str) -> QLabel:
            lbl = QLabel(text)
            self._option_labels.append(lbl)
            return lbl

        # ── Row 1: password + encodings ─────────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password")
        self._password_edit.setFixedWidth(130)

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

        self._filename_encoding_combo = EncodingComboBox()
        self._filename_encoding_combo.setFixedWidth(160)
        self._pwd_encoding_combo = EncodingComboBox()
        self._pwd_encoding_combo.setFixedWidth(130)

        row1.addWidget(_lbl("Password:"))
        row1.addWidget(self._password_edit)
        row1.addWidget(self._eye_btn)
        row1.addWidget(self._pwd_picker)
        row1.addSpacing(12)
        row1.addWidget(_lbl("Filename enc:"))
        row1.addWidget(self._filename_encoding_combo)
        row1.addSpacing(12)
        row1.addWidget(_lbl("Pwd enc:"))
        row1.addWidget(self._pwd_encoding_combo)
        row1.addStretch()

        # ── Row 2: output dir + trash ────────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self._output_path_edit = QLineEdit()
        self._output_path_edit.setPlaceholderText(
            "Output directory (default: next to archive)"
        )

        output_browse = QToolButton()
        output_browse.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        output_browse.setToolTip("Choose output directory")
        output_browse.clicked.connect(self._browse_output)

        self._trash_after_extract = QCheckBox("Move archive to trash after extraction")
        self._trash_after_extract.setStyleSheet("font-size:12px;")

        row2.addWidget(_lbl("Output:"))
        row2.addWidget(self._output_path_edit, stretch=1)
        row2.addWidget(output_browse)
        row2.addSpacing(16)
        row2.addWidget(self._trash_after_extract)

        vbox.addLayout(row1)
        vbox.addLayout(row2)
        return strip

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Normal-mode buttons ───────────────────────────────────────────────
        self._load_btn = QPushButton("Load Contents")
        self._load_btn.setEnabled(False)
        self._load_btn.clicked.connect(self._start_list)

        self._test_btn = QPushButton("Test")
        self._test_btn.setEnabled(False)
        self._test_btn.clicked.connect(self._start_test)

        self._edit_archive_btn = QPushButton("Edit Archive")
        self._edit_archive_btn.setEnabled(False)
        self._edit_archive_btn.clicked.connect(self._enter_edit_mode)

        self._extract_btn = QPushButton("Extract")
        self._extract_btn.setEnabled(False)
        self._extract_btn.clicked.connect(self._start_extract)
        self._extract_btn.setStyleSheet(
            "QPushButton{background:#007AFF;color:white;border:none;"
            "border-radius:6px;padding:5px 16px;font-weight:600;}"
            "QPushButton:hover{background:#005CC8;}"
            "QPushButton:disabled{background:#C0C0C0;color:#EEEEEE;}"
        )

        # ── Edit-mode buttons (hidden by default) ─────────────────────────────
        self._edit_add_btn = QPushButton("Add Files…")
        self._edit_add_btn.clicked.connect(self._edit_browse_add)
        self._edit_add_btn.setVisible(False)

        self._edit_cancel_btn = QPushButton("Cancel")
        self._edit_cancel_btn.clicked.connect(self._exit_edit_mode)
        self._edit_cancel_btn.setVisible(False)

        self._edit_save_btn = QPushButton("Save")
        self._edit_save_btn.clicked.connect(self._start_update)
        self._edit_save_btn.setVisible(False)

        layout.addWidget(self._load_btn)
        layout.addWidget(self._test_btn)
        layout.addWidget(self._edit_archive_btn)
        layout.addWidget(self._edit_add_btn)
        layout.addStretch()
        layout.addWidget(self._edit_cancel_btn)
        layout.addWidget(self._edit_save_btn)
        layout.addWidget(self._extract_btn)
        return bar

    def _build_tree_pane(self) -> QWidget:
        pane = QWidget()
        vbox = QVBoxLayout(pane)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # Subtle header
        header = QHBoxLayout()
        self._contents_header_lbl = QLabel("CONTENTS")
        contents_lbl = self._contents_header_lbl
        self._entry_count_lbl = QLabel("")
        header.addWidget(contents_lbl)
        header.addWidget(self._entry_count_lbl)
        header.addStretch()

        self._contents_tree = QTreeWidget()
        self._contents_tree.setColumnCount(1)
        self._contents_tree.setHeaderHidden(True)
        self._contents_tree.setRootIsDecorated(True)
        self._contents_tree.setSortingEnabled(False)
        self._contents_tree.currentItemChanged.connect(self._on_tree_item_changed)

        vbox.addLayout(header)
        vbox.addWidget(self._contents_tree, stretch=1)
        return pane

    def _build_right_pane(self) -> QWidget:
        """Preview/Info pane with a two-button mode toggle."""
        pane = QWidget()
        vbox = QVBoxLayout(pane)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # Header: [Preview] [Info] toggle + entry filename
        header = QHBoxLayout()
        header.setSpacing(2)

        def _tab_btn(label: str) -> QPushButton:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setStyleSheet(
                "QPushButton{border:1px solid #CCCCCC;border-radius:4px;"
                "padding:3px 10px;font-size:12px;background:#F2F2F7;color:#555555;}"
                "QPushButton:checked{background:#1C1C1E;color:white;border-color:#1C1C1E;}"
            )
            return btn

        self._right_preview_btn = _tab_btn("Preview")
        self._right_preview_btn.setChecked(True)
        self._right_info_btn = _tab_btn("Info")

        self._right_mode_group = QButtonGroup(pane)
        self._right_mode_group.setExclusive(True)
        self._right_mode_group.addButton(self._right_preview_btn, 0)
        self._right_mode_group.addButton(self._right_info_btn, 1)
        self._right_mode_group.idClicked.connect(self._on_right_mode_changed)

        self._right_entry_lbl = QLabel("")
        self._right_entry_lbl.setStyleSheet("color:#888888;font-size:11px;")

        header.addWidget(self._right_preview_btn)
        header.addWidget(self._right_info_btn)
        header.addSpacing(8)
        header.addWidget(self._right_entry_lbl, stretch=1)

        # Stacked content
        self._right_stack = QStackedWidget()

        placeholder = QLabel("Select a file to preview")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._right_stack.addWidget(placeholder)  # 0 _RIGHT_PLACEHOLDER

        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._preview_img_label = QLabel()
        self._preview_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_scroll.setWidget(self._preview_img_label)
        self._right_stack.addWidget(self._preview_scroll)  # 1 _RIGHT_IMAGE

        self._preview_text = QPlainTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumBlockCount(5000)
        self._preview_text.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self._right_stack.addWidget(self._preview_text)  # 2 _RIGHT_TEXT

        unsupported = QLabel("No preview available")
        unsupported.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unsupported.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._right_stack.addWidget(unsupported)  # 3 _RIGHT_UNSUPPORTED

        loading_prev = QLabel("Loading preview…")
        loading_prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_prev.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._right_stack.addWidget(loading_prev)  # 4 _RIGHT_LOADING_PREVIEW

        self._right_stack.addWidget(self._build_info_widget())  # 5 _RIGHT_INFO

        loading_info = QLabel("Loading archive info…")
        loading_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_info.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._right_stack.addWidget(loading_info)  # 6 _RIGHT_LOADING_INFO

        vbox.addLayout(header)
        vbox.addWidget(self._right_stack, stretch=1)
        return pane

    def _build_info_widget(self) -> QWidget:
        """The archive-info page inside the right pane."""
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(4)

        self._info_title_lbl = QLabel("Archive Info")
        vbox.addWidget(self._info_title_lbl)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(4)
        form.setContentsMargins(0, 4, 0, 0)

        def _val() -> QLabel:
            return QLabel("—")

        self._info_format = _val()
        self._info_files = _val()
        self._info_compressed = _val()
        self._info_uncompressed = _val()
        self._info_ratio = _val()
        self._info_encrypted = _val()
        self._info_comment = _val()
        self._info_comment.setWordWrap(True)
        self._info_row_labels: list[QLabel] = []

        for label, widget in [
            ("Format:", self._info_format),
            ("Files:", self._info_files),
            ("Compressed:", self._info_compressed),
            ("Original:", self._info_uncompressed),
            ("Ratio:", self._info_ratio),
            ("Encrypted:", self._info_encrypted),
            ("Comment:", self._info_comment),
        ]:
            row_lbl = QLabel(label)
            self._info_row_labels.append(row_lbl)
            form.addRow(row_lbl, widget)

        vbox.addLayout(form)
        vbox.addStretch()
        return w

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
        # Option strip labels
        for lbl in self._option_labels:
            lbl.setStyleSheet(f"color:{c['text_secondary']};font-size:12px;")
        # Trash checkbox
        self._trash_after_extract.setStyleSheet(
            f"font-size:12px;color:{c['text_secondary']};"
        )
        # Tree header
        self._contents_header_lbl.setStyleSheet(
            f"color:{c['text_dim']};font-size:10px;"
            f"font-weight:bold;letter-spacing:1px;"
        )
        self._entry_count_lbl.setStyleSheet(f"color:{c['text_dim']};font-size:10px;")
        # Right pane toggle buttons
        for btn in (self._right_preview_btn, self._right_info_btn):
            btn.setStyleSheet(
                f"QPushButton{{border:1px solid {c['border']};border-radius:4px;"
                f"padding:3px 10px;font-size:12px;"
                f"background:{c['surface']};color:{c['text_secondary']};}}"
                f"QPushButton:checked{{"
                f"background:{c['text']};color:{c['surface']};border-color:{c['text']};}}"
            )
        self._right_entry_lbl.setStyleSheet(
            f"color:{c['text_secondary']};font-size:11px;"
        )
        # Extract (primary) button
        self._extract_btn.setStyleSheet(
            f"QPushButton{{background:{c['accent']};color:white;border:none;"
            f"border-radius:6px;padding:5px 16px;font-weight:600;}}"
            f"QPushButton:hover{{background:{c['accent_hover']};}}"
            f"QPushButton:disabled{{background:{c['accent_disabled_bg']};color:#EEEEEE;}}"
        )
        # Info pane
        self._info_title_lbl.setStyleSheet(
            f"font-weight:600;font-size:12px;color:{c['text']};"
        )
        for lbl in self._info_row_labels:
            lbl.setStyleSheet(f"color:{c['text_dim']};font-size:12px;")
        for lbl in (
            self._info_format,
            self._info_files,
            self._info_compressed,
            self._info_uncompressed,
            self._info_ratio,
            self._info_encrypted,
            self._info_comment,
        ):
            lbl.setStyleSheet(f"color:{c['text_secondary']};font-size:12px;")
        # Log
        self._log_toggle_btn.setStyleSheet(
            f"QPushButton{{text-align:left;color:{c['text_secondary']};font-size:12px;"
            f"padding:3px 0;border:none;}}"
            f"QPushButton:hover{{color:{c['text']};}}"
        )
        self._log_last_lbl.setStyleSheet(f"color:{c['text_dim']};font-size:11px;")
        # Right-pane placeholder/status labels (static pages)
        for page_idx in (
            _RIGHT_PLACEHOLDER,
            _RIGHT_UNSUPPORTED,
            _RIGHT_LOADING_PREVIEW,
            _RIGHT_LOADING_INFO,
        ):
            w = self._right_stack.widget(page_idx)
            if w:
                w.setStyleSheet(f"color:{c['text_dim']};font-size:12px;")

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
        has_path = bool(self._current_path)
        self._load_btn.setEnabled(has_path)
        self._test_btn.setEnabled(has_path)
        self._extract_btn.setEnabled(False)
        self._edit_archive_btn.setEnabled(False)
        self._preview_valid = False
        self._preview_names = []
        self._contents_tree.clear()
        self._entry_count_lbl.setText("")
        self._filename_encoding_combo.reset_detected()
        self._right_stack.setCurrentIndex(_RIGHT_PLACEHOLDER)
        self._right_entry_lbl.setText("")
        self._right_preview_btn.setChecked(True)
        self._cleanup_preview_tmpdir()
        self._archive_info_cache = None
        self._clear_info_labels()
        if self._edit_mode:
            self._exit_edit_mode()
        if has_path:
            self.archive_opened.emit(self._current_path)

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
        self._contents_tree.clear()
        self._entry_count_lbl.setText("")
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
            self._populate_tree(names)
            self._preview_valid = True
            self._preview_names = list(names)
            self._extract_btn.setEnabled(True)
            self._edit_archive_btn.setEnabled(True)
            self._entry_count_lbl.setText(f"  {len(names)} entries")
            self._log(
                f"✓ Preview ready — {len(names)} entries  (encoding: {enc or 'auto'})"
            )
            self.status_changed.emit(f"Preview: {len(names)} entries")
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

    def _on_tree_item_changed(
        self, current: QTreeWidgetItem | None, _prev: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            self._right_entry_lbl.setText("")
            if self._right_preview_btn.isChecked():
                self._right_stack.setCurrentIndex(_RIGHT_PLACEHOLDER)
            return
        full_path: str = current.data(0, Qt.ItemDataRole.UserRole) or ""
        if not full_path or full_path.endswith("/"):
            self._right_entry_lbl.setText("")
            if self._right_preview_btn.isChecked():
                self._right_stack.setCurrentIndex(_RIGHT_PLACEHOLDER)
            return
        self._right_entry_lbl.setText(os.path.basename(full_path))
        if self._right_preview_btn.isChecked() and self._worker is None:
            self._start_preview(full_path)

    def _on_right_mode_changed(self, mode_id: int) -> None:
        if mode_id == 1:  # Info mode
            if self._archive_info_cache is not None:
                self._right_stack.setCurrentIndex(_RIGHT_INFO)
            else:
                self._right_stack.setCurrentIndex(_RIGHT_LOADING_INFO)
                if self._current_path and self._inspector_worker is None:
                    self._inspector_worker = InfoWorker(self._current_path)
                    self._inspector_worker.result.connect(self._on_info_result)
                    self._inspector_worker.error.connect(self._on_info_error)
                    self._inspector_worker.finished.connect(
                        self._inspector_worker.deleteLater
                    )
                    self._inspector_worker.finished.connect(
                        lambda: setattr(self, "_inspector_worker", None)
                    )
                    self._inspector_worker.start()
        else:  # Preview mode
            current = self._contents_tree.currentItem()
            if current:
                full_path: str = current.data(0, Qt.ItemDataRole.UserRole) or ""
                if full_path and not full_path.endswith("/") and self._worker is None:
                    self._start_preview(full_path)
                    return
            self._right_stack.setCurrentIndex(_RIGHT_PLACEHOLDER)

    def _start_preview(self, entry_name: str) -> None:
        self._cleanup_preview_tmpdir()
        self._right_stack.setCurrentIndex(_RIGHT_LOADING_PREVIEW)

        if self._preview_worker is not None:
            self._preview_worker.finished.disconnect()
            self._preview_worker = None

        worker = PreviewWorker(
            self._current_path,
            entry_name,
            self._password_edit.text(),
            self._filename_encoding_combo.current_codec(),
            self._pwd_encoding_combo.current_codec(),
        )
        worker.result.connect(self._on_preview_result)
        worker.error.connect(self._on_preview_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: setattr(self, "_preview_worker", None))
        self._preview_worker = worker
        worker.start()

    def _on_preview_result(self, tmpdir: str, file_path: str) -> None:
        self._preview_tmpdir = tmpdir
        ext = os.path.splitext(file_path)[1].lower()

        if ext in _IMAGE_EXTS:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    800,
                    600,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_img_label.setPixmap(scaled)
                self._right_stack.setCurrentIndex(_RIGHT_IMAGE)
                return

        if ext in _TEXT_EXTS:
            try:
                with open(file_path, encoding="utf-8", errors="replace") as fh:
                    content = fh.read(100_000)
                self._preview_text.setPlainText(content)
                self._right_stack.setCurrentIndex(_RIGHT_TEXT)
                return
            except OSError:
                pass

        self._right_stack.setCurrentIndex(_RIGHT_UNSUPPORTED)

    def _on_preview_error(self, _msg: str) -> None:
        self._right_stack.setCurrentIndex(_RIGHT_UNSUPPORTED)

    # ── Info ──────────────────────────────────────────────────────────────────

    def _on_info_result(self, info) -> None:
        self._archive_info_cache = info

        def _fmt(n: int) -> str:
            if n < 0:
                return "—"
            for unit in ("B", "KB", "MB", "GB"):
                if n < 1024:
                    return f"{n:.1f} {unit}"
                n //= 1024  # type: ignore[assignment]
            return f"{n} TB"

        self._info_format.setText(info.format_name)
        self._info_files.setText(str(info.file_count))
        self._info_compressed.setText(_fmt(info.compressed_size))
        self._info_uncompressed.setText(_fmt(info.uncompressed_size))
        if info.compressed_size > 0 and info.uncompressed_size > 0:
            self._info_ratio.setText(
                f"{info.compressed_size / info.uncompressed_size:.1%}"
            )
        else:
            self._info_ratio.setText("—")
        self._info_encrypted.setText("Yes" if info.is_encrypted else "No")
        self._info_comment.setText(info.comment or "—")
        self._right_stack.setCurrentIndex(_RIGHT_INFO)

    def _on_info_error(self, msg: str) -> None:
        self._info_format.setText(f"Error: {msg[:40]}")
        self._right_stack.setCurrentIndex(_RIGHT_INFO)

    def _clear_info_labels(self) -> None:
        for lbl in (
            self._info_format,
            self._info_files,
            self._info_compressed,
            self._info_uncompressed,
            self._info_ratio,
            self._info_encrypted,
            self._info_comment,
        ):
            lbl.setText("—")

    # ── Edit mode ─────────────────────────────────────────────────────────────

    def _enter_edit_mode(self) -> None:
        self._edit_mode = True
        self._edit_remove.clear()
        self._edit_add.clear()
        self._load_btn.setVisible(False)
        self._test_btn.setVisible(False)
        self._extract_btn.setVisible(False)
        self._edit_archive_btn.setVisible(False)
        self._edit_add_btn.setVisible(True)
        self._edit_cancel_btn.setVisible(True)
        self._edit_save_btn.setVisible(True)
        self._contents_tree.setFocus()
        self._contents_tree.keyPressEvent = self._edit_tree_key_press  # type: ignore[method-assign]
        self._contents_tree.setAcceptDrops(True)
        self._contents_tree.dragEnterEvent = self._edit_drag_enter  # type: ignore[method-assign]
        self._contents_tree.dropEvent = self._edit_drop  # type: ignore[method-assign]
        self._log("Edit mode — Delete: remove selected  |  drag files here: add")

    def _exit_edit_mode(self) -> None:
        self._edit_mode = False
        self._edit_remove.clear()
        self._edit_add.clear()
        self._load_btn.setVisible(True)
        self._test_btn.setVisible(True)
        self._extract_btn.setVisible(True)
        self._edit_archive_btn.setVisible(True)
        self._edit_add_btn.setVisible(False)
        self._edit_cancel_btn.setVisible(False)
        self._edit_save_btn.setVisible(False)
        self._restore_tree_colors()
        del self._contents_tree.keyPressEvent  # type: ignore[misc]
        del self._contents_tree.dragEnterEvent  # type: ignore[misc]
        del self._contents_tree.dropEvent  # type: ignore[misc]
        self._contents_tree.setAcceptDrops(False)

    def _edit_tree_key_press(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._edit_mark_selected_for_removal()
        else:
            QTreeWidget.keyPressEvent(self._contents_tree, event)

    def _edit_drag_enter(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _edit_drop(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._edit_add_files(paths)
        event.acceptProposedAction()

    def _edit_browse_add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Files to Archive", "")
        if paths:
            self._edit_add_files(paths)

    def _edit_add_files(self, paths: list[str]) -> None:
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        green = QColor("#006600")
        for path in paths:
            if path not in self._edit_add:
                self._edit_add.append(path)
                item = QTreeWidgetItem([f"+ {os.path.basename(path)}"])
                item.setIcon(0, file_icon)
                item.setForeground(0, green)
                item.setData(0, Qt.ItemDataRole.UserRole, None)
                self._contents_tree.addTopLevelItem(item)

    def _edit_mark_selected_for_removal(self) -> None:
        strike_font = QFont()
        strike_font.setStrikeOut(True)
        red = QColor("#CC0000")
        for item in self._contents_tree.selectedItems():
            full_path: str = item.data(0, Qt.ItemDataRole.UserRole) or ""
            if full_path and full_path not in self._edit_remove:
                self._edit_mark_item_recursive(item, strike_font, red, full_path)

    def _edit_mark_item_recursive(
        self, item: QTreeWidgetItem, font: QFont, color: QColor, path: str
    ) -> None:
        if path:
            self._edit_remove.add(path)
        item.setFont(0, font)
        item.setForeground(0, color)
        for i in range(item.childCount()):
            child = item.child(i)
            child_path: str = child.data(0, Qt.ItemDataRole.UserRole) or ""
            self._edit_mark_item_recursive(child, font, color, child_path)

    def _restore_tree_colors(self) -> None:
        normal_font = QFont()
        default_color = self._contents_tree.palette().color(
            self._contents_tree.foregroundRole()
        )

        def _restore(item: QTreeWidgetItem) -> None:
            item.setFont(0, normal_font)
            item.setForeground(0, default_color)
            for i in range(item.childCount()):
                _restore(item.child(i))

        root = self._contents_tree.invisibleRootItem()
        for i in range(root.childCount()):
            _restore(root.child(i))

    def _start_update(self) -> None:
        if not self._current_path:
            return
        if not self._edit_remove and not self._edit_add:
            self._exit_edit_mode()
            return
        self._log("─" * 60)
        self._log(
            f"Updating archive: removing {len(self._edit_remove)}, "
            f"adding {len(self._edit_add)} file(s)…"
        )
        worker = UpdateWorker(
            self._current_path,
            list(self._edit_add),
            list(self._edit_remove),
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
        self._exit_edit_mode()
        if ok:
            self._log("✓ Archive updated.")
            self.status_changed.emit("Archive updated")
            self._start_list()
        else:
            self._log("✗ Update failed.")
            self.status_changed.emit("Update failed")

    def _on_update_error(self, msg: str) -> None:
        self._set_busy(False)
        self._exit_edit_mode()
        self._log(f"✗ Update error: {msg}")
        self.status_changed.emit("Update error")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        has_path = bool(self._current_path)
        self._load_btn.setEnabled(not busy and has_path)
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

    def _toggle_log(self) -> None:
        visible = not self._log_edit.isVisible()
        self._log_edit.setVisible(visible)
        self._log_toggle_btn.setText("▾  Log" if visible else "▸  Log")

    def _cleanup_preview_tmpdir(self) -> None:
        if self._preview_tmpdir:
            shutil.rmtree(self._preview_tmpdir, ignore_errors=True)
            self._preview_tmpdir = None

    def _populate_tree(self, names: list[str]) -> None:
        self._contents_tree.clear()
        dir_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)

        folder_items: dict[str, QTreeWidgetItem] = {}

        def _get_or_create_folder(path: str) -> QTreeWidgetItem:
            if path in folder_items:
                return folder_items[path]
            clean = path.rstrip("/")
            sep = clean.rfind("/")
            label = clean[sep + 1 :]
            item = QTreeWidgetItem([label])
            item.setIcon(0, dir_icon)
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            if sep == -1:
                self._contents_tree.addTopLevelItem(item)
            else:
                parent_path = clean[:sep] + "/"
                _get_or_create_folder(parent_path).addChild(item)
            folder_items[path] = item
            return item

        for name in names:
            if name.endswith("/"):
                _get_or_create_folder(name)
                continue
            sep = name.rfind("/")
            label = name[sep + 1 :] if sep != -1 else name
            entry = QTreeWidgetItem([label])
            entry.setIcon(0, file_icon)
            entry.setData(0, Qt.ItemDataRole.UserRole, name)
            if sep == -1:
                self._contents_tree.addTopLevelItem(entry)
            else:
                parent_path = name[:sep] + "/"
                _get_or_create_folder(parent_path).addChild(entry)

        root = self._contents_tree.invisibleRootItem()
        if root.childCount() <= 50:
            self._contents_tree.expandAll()
        else:
            for i in range(root.childCount()):
                root.child(i).setExpanded(True)

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
        archive = self._current_path
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
                f"  filename encoding detected: {codec.upper()} "
                f"({confidence:.0%} confidence)"
            )
