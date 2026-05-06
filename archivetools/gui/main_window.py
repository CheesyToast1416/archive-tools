from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from archivetools.config.passwords import PasswordStore
from archivetools.config.settings import AppSettings
from archivetools.gui.dialogs.settings_dialog import SettingsDialog
from archivetools.gui.panels.batch_panel import BatchPanel
from archivetools.gui.panels.convert_panel import ConvertPanel
from archivetools.gui.panels.create_panel import CreatePanel
from archivetools.gui.panels.extract_panel import ExtractPanel
from archivetools.gui.panels.info_panel import InfoPanel
from archivetools.gui.panels.passwords_panel import PasswordsPanel


class MainWindow(QMainWindow):
    """Top-level window — tabbed coordinator; drag-drop delegated to active panel."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        store: PasswordStore | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or AppSettings()
        self._store = store

        self.setWindowTitle("ArchiveTools")
        self.setMinimumSize(700, 700)
        self.setAcceptDrops(True)

        # Restore window geometry from settings
        if self._settings.window_geometry:
            self.restoreGeometry(
                QByteArray.fromBase64(self._settings.window_geometry.encode())
            )

        # Build panels (pass settings + store so they apply defaults)
        self._extract_panel = ExtractPanel(self._settings, self._store)
        self._create_panel = CreatePanel(self._settings, self._store)
        self._batch_panel = BatchPanel(self._settings, self._store)
        self._convert_panel = ConvertPanel(self._settings, self._store)
        self._info_panel = InfoPanel()
        self._passwords_panel = (
            PasswordsPanel(self._store) if self._store is not None else None
        )

        self._tabs = QTabWidget()
        self._tabs.addTab(self._extract_panel, "Extract")
        self._tabs.addTab(self._create_panel, "Create")
        self._tabs.addTab(self._batch_panel, "Batch")
        self._tabs.addTab(self._convert_panel, "Convert")
        self._tabs.addTab(self._info_panel, "Info")
        if self._passwords_panel is not None:
            self._tabs.addTab(self._passwords_panel, "Passwords")
        self.setCentralWidget(self._tabs)
        self._tabs.setCurrentIndex(
            min(self._settings.active_tab, self._tabs.count() - 1)
        )

        # Status bar
        for panel in (
            self._extract_panel,
            self._create_panel,
            self._batch_panel,
            self._convert_panel,
            self._info_panel,
        ):
            panel.status_changed.connect(self.statusBar().showMessage)
        self.statusBar().showMessage("Ready")

        # Wire passwords_panel.store_changed to refresh picker buttons in panels
        if self._passwords_panel is not None:
            self._passwords_panel.store_changed.connect(self._on_store_changed)

        # Menu bar
        self._build_menu()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        prefs = QAction("Preferences…", self)
        prefs.setShortcut("Ctrl+,")
        prefs.triggered.connect(self._open_settings)
        file_menu.addAction(prefs)

        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, parent=self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        self._settings.active_tab = self._tabs.currentIndex()
        self._settings.window_geometry = self.saveGeometry().toBase64().data().decode()
        self._settings.save()
        super().closeEvent(event)

    # ── Signals ───────────────────────────────────────────────────────────────

    def _on_settings_changed(self) -> None:
        """Propagate settings changes to panels that support live updates."""
        for panel in (
            self._extract_panel,
            self._create_panel,
            self._batch_panel,
            self._convert_panel,
        ):
            panel.apply_settings(self._settings)

    def _on_store_changed(self) -> None:
        """Rebuild password picker menus in all panels after a store mutation."""
        for panel in (
            self._extract_panel,
            self._create_panel,
            self._batch_panel,
            self._convert_panel,
        ):
            if hasattr(panel, "refresh_password_picker"):
                panel.refresh_password_picker()

    # ── Public ────────────────────────────────────────────────────────────────

    def switch_to_passwords_tab(self) -> None:
        if self._passwords_panel is not None:
            self._tabs.setCurrentWidget(self._passwords_panel)

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasUrls() and any(u.isLocalFile() for u in mime.urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            event.ignore()
            return
        active = self._tabs.currentWidget()
        if isinstance(active, BatchPanel):
            for p in paths:
                active.handle_drop(p)
        elif hasattr(active, "handle_drop"):
            active.handle_drop(paths[0])
        event.acceptProposedAction()
