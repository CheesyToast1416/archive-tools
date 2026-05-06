from __future__ import annotations

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from archivetools.gui.panels.convert_panel import ConvertPanel
from archivetools.gui.panels.create_panel import CreatePanel
from archivetools.gui.panels.extract_panel import ExtractPanel
from archivetools.gui.panels.info_panel import InfoPanel


class MainWindow(QMainWindow):
    """
    Top-level window.  Owns a QTabWidget with three panels:
      • Extract — full CJK-aware extraction UI
      • Create  — archive creation (stub, next release)
      • Info    — archive metadata viewer (stub, next release)
    Drag-and-drop is delegated to the active panel.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ArchiveTools")
        self.setMinimumSize(700, 680)
        self.setAcceptDrops(True)

        self._extract_panel = ExtractPanel()
        self._create_panel = CreatePanel()
        self._convert_panel = ConvertPanel()
        self._info_panel = InfoPanel()

        self._tabs = QTabWidget()
        self._tabs.addTab(self._extract_panel, "Extract")
        self._tabs.addTab(self._create_panel, "Create")
        self._tabs.addTab(self._convert_panel, "Convert")
        self._tabs.addTab(self._info_panel, "Info")
        self.setCentralWidget(self._tabs)

        self._extract_panel.status_changed.connect(self.statusBar().showMessage)
        self._create_panel.status_changed.connect(self.statusBar().showMessage)
        self._convert_panel.status_changed.connect(self.statusBar().showMessage)
        self._info_panel.status_changed.connect(self.statusBar().showMessage)
        self.statusBar().showMessage("Ready")

    # ── Drag-and-drop — delegate to the active panel ──────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls() and len(mime.urls()) == 1 and mime.urls()[0].isLocalFile():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        path = event.mimeData().urls()[0].toLocalFile()
        active = self._tabs.currentWidget()
        if hasattr(active, "handle_drop"):
            active.handle_drop(path)
        event.acceptProposedAction()
