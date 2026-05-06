from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class ArchivePickerWidget(QWidget):
    """
    A QLineEdit + Browse button combination for selecting a file path.

    Supports drag-and-drop of a single local file.
    Set ``save_mode=True`` for a "Save As" dialog (used by the Create panel).
    """

    path_changed = Signal(str)

    def __init__(
        self,
        placeholder: str = "",
        file_filter: str = "All files (*)",
        save_mode: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._file_filter = file_filter
        self._save_mode = save_mode
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.textChanged.connect(self.path_changed)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)

        layout.addWidget(self._edit)
        layout.addWidget(browse_btn)

    @property
    def path(self) -> str:
        return self._edit.text().strip()

    def set_path(self, path: str) -> None:
        self._edit.setText(path)

    def clear(self) -> None:
        self._edit.clear()

    def _browse(self) -> None:
        if self._save_mode:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Archive", "", self._file_filter
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open Archive", "", self._file_filter
            )
        if path:
            self.set_path(path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls() and len(mime.urls()) == 1 and mime.urls()[0].isLocalFile():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        self.set_path(event.mimeData().urls()[0].toLocalFile())
        event.acceptProposedAction()
