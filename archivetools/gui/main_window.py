from __future__ import annotations

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from archivetools.gui.panels.batch_panel import BatchPanel
from archivetools.gui.panels.convert_panel import ConvertPanel
from archivetools.gui.panels.create_panel import CreatePanel
from archivetools.gui.panels.extract_panel import ExtractPanel
from archivetools.gui.panels.info_panel import InfoPanel


class MainWindow(QMainWindow):
    """Top-level window — tabbed coordinator; drag-drop delegated to active panel."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ArchiveTools")
        self.setMinimumSize(700, 700)
        self.setAcceptDrops(True)

        self._extract_panel = ExtractPanel()
        self._create_panel = CreatePanel()
        self._batch_panel = BatchPanel()
        self._convert_panel = ConvertPanel()
        self._info_panel = InfoPanel()

        self._tabs = QTabWidget()
        self._tabs.addTab(self._extract_panel, "Extract")
        self._tabs.addTab(self._create_panel, "Create")
        self._tabs.addTab(self._batch_panel, "Batch")
        self._tabs.addTab(self._convert_panel, "Convert")
        self._tabs.addTab(self._info_panel, "Info")
        self.setCentralWidget(self._tabs)

        self._extract_panel.status_changed.connect(self.statusBar().showMessage)
        self._create_panel.status_changed.connect(self.statusBar().showMessage)
        self._batch_panel.status_changed.connect(self.statusBar().showMessage)
        self._convert_panel.status_changed.connect(self.statusBar().showMessage)
        self._info_panel.status_changed.connect(self.statusBar().showMessage)
        self.statusBar().showMessage("Ready")

    # ── Drag-and-drop — delegate to the active panel ──────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls() and any(u.isLocalFile() for u in mime.urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            event.ignore()
            return
        active = self._tabs.currentWidget()
        if isinstance(active, BatchPanel):
            # Batch panel accepts multiple files at once
            for p in paths:
                active.handle_drop(p)
        elif hasattr(active, "handle_drop"):
            active.handle_drop(paths[0])
        event.acceptProposedAction()
