from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from archivetools.gui.theme import LIGHT, ThemeColors


class ArchiveTreeWidget(QWidget):
    """
    Archive contents tree with optional edit-mode (add/remove entries).

    Signals
    -------
    entry_selected(str):
        Full archive path of the clicked leaf file.  Empty string for directories.
    edit_mode_changed(bool):
        True when edit mode is entered, False when exited.  The parent panel uses
        this to show/hide its action buttons.
    entries_modified(list, list):
        Emitted by ``save_edits()`` with ``(files_to_add, paths_to_remove)``.
    status_message(str):
        Informational text for the parent's log/status bar.
    """

    entry_selected = Signal(str)
    edit_mode_changed = Signal(bool)
    entries_modified = Signal(list, list)
    status_message = Signal(str)

    def __init__(
        self,
        colors: ThemeColors | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._colors: ThemeColors = colors or LIGHT
        self._edit_mode = False
        self._edit_remove: set[str] = set()
        self._edit_add: list[str] = []
        self._build_ui()
        self.set_theme(self._colors)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        header = QHBoxLayout()
        self._header_lbl = QLabel("CONTENTS")
        self._count_lbl = QLabel("")
        header.addWidget(self._header_lbl)
        header.addWidget(self._count_lbl)
        header.addStretch()
        vbox.addLayout(header)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(1)
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSortingEnabled(False)
        self._tree.currentItemChanged.connect(self._on_item_changed)
        vbox.addWidget(self._tree, stretch=1)

    # ── Public interface ──────────────────────────────────────────────────────

    def populate(self, names: list[str]) -> None:
        """Build the tree from a flat list of archive entry paths."""
        self._tree.clear()
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
                self._tree.addTopLevelItem(item)
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
                self._tree.addTopLevelItem(entry)
            else:
                parent_path = name[:sep] + "/"
                _get_or_create_folder(parent_path).addChild(entry)

        root = self._tree.invisibleRootItem()
        if root.childCount() <= 50:
            self._tree.expandAll()
        else:
            for i in range(root.childCount()):
                root.child(i).setExpanded(True)

        self._count_lbl.setText(f"  {len(names)} entries")

    def clear(self) -> None:
        """Clear the tree and reset state."""
        if self._edit_mode:
            self.exit_edit_mode()
        self._tree.clear()
        self._count_lbl.setText("")

    def current_entry(self) -> str | None:
        """Return the full archive path of the currently selected item, or None."""
        item = self._tree.currentItem()
        if item is None:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole) or None

    # ── Edit mode ─────────────────────────────────────────────────────────────

    def enter_edit_mode(self) -> None:
        if self._edit_mode:
            return
        self._edit_mode = True
        self._edit_remove.clear()
        self._edit_add.clear()
        self._tree.setFocus()
        self._tree.keyPressEvent = self._edit_key_press  # type: ignore[method-assign]
        self._tree.setAcceptDrops(True)
        self._tree.dragEnterEvent = self._edit_drag_enter  # type: ignore[method-assign]
        self._tree.dropEvent = self._edit_drop  # type: ignore[method-assign]
        self.edit_mode_changed.emit(True)
        self.status_message.emit(
            "Edit mode — Delete: remove selected  |  drag files here: add"
        )

    def exit_edit_mode(self) -> None:
        if not self._edit_mode:
            return
        self._edit_mode = False
        self._edit_remove.clear()
        self._edit_add.clear()
        self._restore_colors()
        try:
            del self._tree.keyPressEvent  # type: ignore[misc]
            del self._tree.dragEnterEvent  # type: ignore[misc]
            del self._tree.dropEvent  # type: ignore[misc]
        except AttributeError:
            pass
        self._tree.setAcceptDrops(False)
        self.edit_mode_changed.emit(False)

    def browse_add(self) -> None:
        """Open a file dialog and stage selected files for addition."""
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Files to Archive", "")
        if paths:
            self._add_files(paths)

    def save_edits(self) -> None:
        """Emit ``entries_modified`` with current staged changes."""
        self.entries_modified.emit(list(self._edit_add), list(self._edit_remove))

    def is_in_edit_mode(self) -> bool:
        return self._edit_mode

    # ── Theme ─────────────────────────────────────────────────────────────────

    def set_theme(self, c: ThemeColors) -> None:
        self._colors = c
        self._header_lbl.setStyleSheet(
            f"color:{c['text_dim']};font-size:10px;font-weight:bold;letter-spacing:1px;"
        )
        self._count_lbl.setStyleSheet(f"color:{c['text_dim']};font-size:10px;")

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_item_changed(
        self, current: QTreeWidgetItem | None, _prev: QTreeWidgetItem | None
    ) -> None:
        if current is None:
            self.entry_selected.emit("")
            return
        full_path: str = current.data(0, Qt.ItemDataRole.UserRole) or ""
        self.entry_selected.emit(full_path)

    def _edit_key_press(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._mark_selected_for_removal()
        else:
            QTreeWidget.keyPressEvent(self._tree, event)

    def _edit_drag_enter(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _edit_drop(self, event) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._add_files(paths)
        event.acceptProposedAction()

    def _add_files(self, paths: list[str]) -> None:
        file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        green = QColor("#006600")
        for path in paths:
            if path not in self._edit_add:
                self._edit_add.append(path)
                item = QTreeWidgetItem([f"+ {os.path.basename(path)}"])
                item.setIcon(0, file_icon)
                item.setForeground(0, green)
                item.setData(0, Qt.ItemDataRole.UserRole, None)
                self._tree.addTopLevelItem(item)

    def _mark_selected_for_removal(self) -> None:
        strike_font = QFont()
        strike_font.setStrikeOut(True)
        red = QColor("#CC0000")
        for item in self._tree.selectedItems():
            full_path: str = item.data(0, Qt.ItemDataRole.UserRole) or ""
            if full_path and full_path not in self._edit_remove:
                self._mark_item_recursive(item, strike_font, red, full_path)

    def _mark_item_recursive(
        self, item: QTreeWidgetItem, font: QFont, color: QColor, path: str
    ) -> None:
        if path:
            self._edit_remove.add(path)
        item.setFont(0, font)
        item.setForeground(0, color)
        for i in range(item.childCount()):
            child = item.child(i)
            child_path: str = child.data(0, Qt.ItemDataRole.UserRole) or ""
            self._mark_item_recursive(child, font, color, child_path)

    def _restore_colors(self) -> None:
        normal_font = QFont()
        default_color = self._tree.palette().color(self._tree.foregroundRole())

        def _restore(item: QTreeWidgetItem) -> None:
            item.setFont(0, normal_font)
            item.setForeground(0, default_color)
            for i in range(item.childCount()):
                _restore(item.child(i))

        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            _restore(root.child(i))
