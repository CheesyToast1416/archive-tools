from __future__ import annotations

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from archivetools.config.passwords import PasswordStore
from archivetools.config.settings import AppSettings
from archivetools.gui.dialogs.settings_dialog import SettingsDialog
from archivetools.gui.panels.batch_panel import BatchPanel
from archivetools.gui.panels.convert_panel import ConvertPanel
from archivetools.gui.panels.create_panel import CreatePanel
from archivetools.gui.panels.extract_panel import ExtractPanel
from archivetools.gui.panels.recent_panel import RecentPanel
from archivetools.gui.theme import LIGHT, ThemeColors, apply_theme, resolve
from archivetools.gui.widgets.sidebar import Sidebar

_NAV_RECENT = 0
_NAV_EXTRACT = 1
_NAV_CREATE = 2
_NAV_BATCH = 3
_NAV_CONVERT = 4


class MainWindow(QMainWindow):
    """Top-level window — sidebar navigation, stacked content panels."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        store: PasswordStore | None = None,
        colors: ThemeColors | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings or AppSettings()
        self._store = store
        self._colors: ThemeColors = colors or LIGHT

        self.setWindowTitle("ArchiveTools")
        self.setMinimumSize(780, 620)
        self.setAcceptDrops(True)

        if self._settings.window_geometry:
            self.restoreGeometry(
                QByteArray.fromBase64(self._settings.window_geometry.encode())
            )

        self._build_ui()
        self._build_menu()
        self._wire_signals()

        nav = max(0, min(self._settings.active_nav, _NAV_CONVERT))
        self._sidebar.set_active(nav)
        self._stack.setCurrentIndex(nav)

        self._recent_panel.refresh(self._settings.recent_archives)

        self.statusBar().showMessage("Ready")

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        c = self._colors

        self._recent_panel = RecentPanel(c)
        self._extract_panel = ExtractPanel(self._settings, self._store, colors=c)
        self._create_panel = CreatePanel(self._settings, self._store, colors=c)
        self._batch_panel = BatchPanel(self._settings, self._store, colors=c)
        self._convert_panel = ConvertPanel(self._settings, self._store, colors=c)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._recent_panel)  # 0
        self._stack.addWidget(self._extract_panel)  # 1
        self._stack.addWidget(self._create_panel)  # 2
        self._stack.addWidget(self._batch_panel)  # 3
        self._stack.addWidget(self._convert_panel)  # 4
        # Info panel is accessible from Extract's ⓘ pane; not a standalone nav item

        self._sidebar = Sidebar(c)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._sidebar)
        body_layout.addWidget(self._stack, stretch=1)
        self.setCentralWidget(body)

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

    def _wire_signals(self) -> None:
        self._sidebar.page_changed.connect(self._stack.setCurrentIndex)
        self._sidebar.settings_clicked.connect(self._open_settings)
        self._sidebar.theme_toggled.connect(self._on_theme_toggled)

        for panel in (
            self._extract_panel,
            self._create_panel,
            self._batch_panel,
            self._convert_panel,
        ):
            panel.status_changed.connect(self.statusBar().showMessage)

        self._recent_panel.open_archive.connect(self._open_from_recent)
        self._extract_panel.archive_opened.connect(self._add_recent)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _on_theme_toggled(self) -> None:
        current = resolve(self._settings.theme)
        new_name = "light" if current["is_dark"] else "dark"
        self._settings.theme = new_name
        self._settings.save()
        app = QApplication.instance()
        colors = apply_theme(app, new_name)
        self.set_theme(colors)

    def set_theme(self, colors: ThemeColors) -> None:
        self._colors = colors
        self._sidebar.set_theme(colors)
        self._recent_panel.set_theme(colors)
        self._extract_panel.set_theme(colors)
        self._create_panel.set_theme(colors)
        self._batch_panel.set_theme(colors)
        self._convert_panel.set_theme(colors)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, store=self._store, parent=self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.store_changed.connect(self._on_store_changed)
        dlg.exec()

    def _open_from_recent(self, path: str) -> None:
        self._extract_panel.handle_drop(path)
        self._sidebar.set_active(_NAV_EXTRACT)
        self._stack.setCurrentIndex(_NAV_EXTRACT)
        self._add_recent(path)

    def _add_recent(self, path: str) -> None:
        if not path:
            return
        recents: list[str] = list(self._settings.recent_archives)
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        self._settings.recent_archives = recents[:15]
        self._settings.save()
        self._recent_panel.refresh(self._settings.recent_archives)

    def _on_settings_changed(self) -> None:
        # Re-apply theme if it changed via the Settings dialog
        new_colors = apply_theme(QApplication.instance(), self._settings.theme)
        if new_colors is not self._colors:
            self.set_theme(new_colors)
        for panel in (
            self._extract_panel,
            self._create_panel,
            self._batch_panel,
            self._convert_panel,
        ):
            panel.apply_settings(self._settings)

    def _on_store_changed(self) -> None:
        for panel in (
            self._extract_panel,
            self._create_panel,
            self._batch_panel,
            self._convert_panel,
        ):
            if hasattr(panel, "refresh_password_picker"):
                panel.refresh_password_picker()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        self._settings.active_nav = self._sidebar.current_index()
        self._settings.window_geometry = self.saveGeometry().toBase64().data().decode()
        self._settings.save()
        super().closeEvent(event)

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
        active = self._stack.currentWidget()
        if isinstance(active, BatchPanel):
            for p in paths:
                active.handle_drop(p)
        elif hasattr(active, "handle_drop"):
            active.handle_drop(paths[0])
        elif isinstance(active, RecentPanel):
            self._open_from_recent(paths[0])
        event.acceptProposedAction()
