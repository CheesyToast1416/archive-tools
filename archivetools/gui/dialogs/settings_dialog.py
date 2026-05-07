from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordStore
from archivetools.config.settings import AppSettings
from archivetools.gui.widgets.archive_picker import ArchivePickerWidget
from archivetools.gui.widgets.encoding_combo import EncodingComboBox


class SettingsDialog(QDialog):
    """Modal preferences dialog. Emits ``settings_changed`` after Apply/OK."""

    settings_changed = Signal()
    store_changed = Signal()  # re-emitted from the embedded PasswordsPanel

    def __init__(
        self,
        settings: AppSettings,
        store: PasswordStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._store = store
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(460)
        self._build_ui()
        self._load_from_settings()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_extraction_tab(), "Extraction")
        tabs.addTab(self._build_creation_tab(), "Creation & Batch")
        tabs.addTab(self._build_encoding_tab(), "Encoding Defaults")
        if self._store is not None:
            tabs.addTab(self._build_passwords_tab(), "Passwords")
        outer.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply,
        )
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        outer.addWidget(btns)

    def _build_extraction_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        behaviour = QGroupBox("Behaviour")
        form = QFormLayout(behaviour)
        self._smart_extraction = QCheckBox(
            "Smart destination (auto-wrap exploding archives)"
        )
        self._trash_extract = QCheckBox(
            "Move archive to trash after successful extraction"
        )
        form.addRow("", self._smart_extraction)
        form.addRow("", self._trash_extract)
        layout.addWidget(behaviour)

        dest = QGroupBox("Default output directory")
        dest_form = QFormLayout(dest)
        self._default_output_dir = ArchivePickerWidget(
            placeholder="Same folder as archive (default)", file_filter=""
        )
        browse_btn = self._default_output_dir.findChild(
            __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton
        )
        if browse_btn:
            browse_btn.clicked.disconnect()
            browse_btn.clicked.connect(self._browse_output_dir)
        dest_form.addRow("Directory:", self._default_output_dir)
        layout.addWidget(dest)

        layout.addStretch()
        return tab

    def _build_creation_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        grp = QGroupBox("Post-operation")
        form = QFormLayout(grp)
        self._trash_create = QCheckBox(
            "Move source files/folders to trash after successful creation"
        )
        self._trash_batch = QCheckBox(
            "Move archives to trash after successful batch extraction"
        )
        form.addRow("", self._trash_create)
        form.addRow("", self._trash_batch)
        layout.addWidget(grp)

        notif_grp = QGroupBox("Notifications")
        notif_form = QFormLayout(notif_grp)
        self._notifications_enabled = QCheckBox(
            "Show desktop notifications on completion"
        )
        notif_form.addRow("", self._notifications_enabled)
        layout.addWidget(notif_grp)

        appear_grp = QGroupBox("Appearance")
        appear_form = QFormLayout(appear_grp)
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Follow system", "system")
        self._theme_combo.addItem("Light", "light")
        self._theme_combo.addItem("Dark", "dark")
        appear_form.addRow("Theme:", self._theme_combo)
        layout.addWidget(appear_grp)
        layout.addStretch()
        return tab

    def _build_passwords_tab(self) -> QWidget:
        from archivetools.gui.panels.passwords_panel import PasswordsPanel

        panel = PasswordsPanel(self._store)  # type: ignore[arg-type]
        panel.store_changed.connect(self.store_changed)
        return panel

    def _build_encoding_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        grp = QGroupBox("Default encodings applied to new panels")
        form = QFormLayout(grp)
        self._pwd_enc = EncodingComboBox()
        self._fname_enc = EncodingComboBox()
        form.addRow("Password encoding:", self._pwd_enc)
        form.addRow("Filename encoding:", self._fname_enc)
        note = QLabel(
            "These defaults are applied when a panel is first opened.\n"
            "You can override them per-archive in each panel."
        )
        note.setWordWrap(True)
        form.addRow("", note)
        layout.addWidget(grp)
        layout.addStretch()
        return tab

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Default Output Directory")
        if path:
            self._default_output_dir.set_path(path)

    def _on_ok(self) -> None:
        self._apply()
        self.accept()

    def _apply(self) -> None:
        s = self._settings
        s.smart_extraction = self._smart_extraction.isChecked()
        s.trash_after_extract = self._trash_extract.isChecked()
        s.default_output_dir = self._default_output_dir.path
        s.trash_after_create = self._trash_create.isChecked()
        s.trash_after_batch = self._trash_batch.isChecked()
        s.notifications_enabled = self._notifications_enabled.isChecked()
        s.theme = self._theme_combo.currentData()
        s.default_password_encoding = self._pwd_enc.current_codec() or ""
        s.default_filename_encoding = self._fname_enc.current_codec() or ""
        s.save()
        self.settings_changed.emit()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_from_settings(self) -> None:
        s = self._settings
        self._smart_extraction.setChecked(s.smart_extraction)
        self._trash_extract.setChecked(s.trash_after_extract)
        self._default_output_dir.set_path(s.default_output_dir)
        self._trash_create.setChecked(s.trash_after_create)
        self._trash_batch.setChecked(s.trash_after_batch)
        self._notifications_enabled.setChecked(s.notifications_enabled)
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == s.theme:
                self._theme_combo.setCurrentIndex(i)
                break
        self._pwd_enc.set_codec(s.default_password_encoding)
        self._fname_enc.set_codec(s.default_filename_encoding)
