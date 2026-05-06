from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordEntry, PasswordStore

_COL_LABEL = 0
_COL_HINT = 1


class _PasswordEditDialog(QDialog):
    """Add or edit a password entry."""

    def __init__(
        self,
        entry: PasswordEntry | None = None,
        current_password: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Password" if entry is None else "Edit Password")
        self.setMinimumWidth(360)
        self._build_ui(entry, current_password)

    def _build_ui(self, entry: PasswordEntry | None, password: str) -> None:
        layout = QVBoxLayout(self)
        form_grp = QGroupBox()
        form = QFormLayout(form_grp)

        self._label_edit = QLineEdit(entry.label if entry else "")
        self._label_edit.setPlaceholderText("e.g.  Work backups, MyArchive.rar")
        form.addRow("Label:", self._label_edit)

        pwd_row = QWidget()
        pwd_layout = QHBoxLayout(pwd_row)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(4)
        self._pwd_edit = QLineEdit(password)
        self._pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_edit.setPlaceholderText("Archive password")
        eye = QToolButton()
        eye.setCheckable(True)
        eye.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton))
        eye.setToolTip("Show / hide password")
        eye.toggled.connect(
            lambda on: self._pwd_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        pwd_layout.addWidget(self._pwd_edit)
        pwd_layout.addWidget(eye)
        form.addRow("Password:", pwd_row)

        self._hint_edit = QLineEdit(entry.hint if entry else "")
        self._hint_edit.setPlaceholderText("Optional non-secret reminder")
        form.addRow("Hint:", self._hint_edit)

        layout.addWidget(form_grp)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate_and_accept(self) -> None:
        if not self._label_edit.text().strip():
            self._label_edit.setFocus()
            return
        if not self._pwd_edit.text():
            self._pwd_edit.setFocus()
            return
        self.accept()

    def result_values(self) -> tuple[str, str, str]:
        """Returns ``(label, password, hint)``."""
        return (
            self._label_edit.text().strip(),
            self._pwd_edit.text(),
            self._hint_edit.text().strip(),
        )


class PasswordsPanel(QWidget):
    """6th tab — manage named passwords for quick insertion into archive panels."""

    store_changed = Signal()  # emitted after every add / edit / delete

    def __init__(self, store: PasswordStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._build_ui()
        self._refresh()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Warning banner (hidden when keyring is available)
        self._warn_lbl = QLabel(
            "⚠  OS keyring unavailable — passwords are stored with local "
            "encryption (AES-GCM) derived from your machine identity.\n"
            "This is less secure than the OS keyring.  "
            "Do not use on shared systems."
        )
        self._warn_lbl.setWordWrap(True)
        self._warn_lbl.setStyleSheet(
            "background:#fff3cd;padding:6px;border-radius:4px;"
        )
        self._warn_lbl.setVisible(not self._store.keyring_available)
        outer.addWidget(self._warn_lbl)

        outer.addWidget(self._build_table_group(), stretch=1)
        outer.addWidget(self._build_buttons_row())

    def _build_table_group(self) -> QGroupBox:
        box = QGroupBox("Saved passwords")
        layout = QVBoxLayout(box)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Label", "Hint"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_LABEL, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_HINT, QHeaderView.ResizeMode.Stretch
        )
        self._table.doubleClicked.connect(self._edit_selected)
        layout.addWidget(self._table)
        return box

    def _build_buttons_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_add = QPushButton("Add…")
        btn_edit = QPushButton("Edit…")
        btn_del = QPushButton("Delete")
        btn_add.clicked.connect(self._add)
        btn_edit.clicked.connect(self._edit_selected)
        btn_del.clicked.connect(self._delete_selected)

        layout.addWidget(btn_add)
        layout.addWidget(btn_edit)
        layout.addWidget(btn_del)
        layout.addStretch()
        return row

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _add(self) -> None:
        dlg = _PasswordEditDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        label, password, hint = dlg.result_values()
        self._store.add(label, password, hint)
        self._refresh()
        self.store_changed.emit()

    def _edit_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        entry = self._store.entries()[row]
        try:
            current_pwd = self._store.get_password(entry.id)
        except Exception:  # noqa: BLE001
            current_pwd = ""
        dlg = _PasswordEditDialog(
            entry=entry, current_password=current_pwd, parent=self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        label, password, hint = dlg.result_values()
        self._store.update(entry.id, label=label, password=password, hint=hint)
        self._refresh()
        self.store_changed.emit()

    def _delete_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        entry = self._store.entries()[row]
        self._store.delete(entry.id)
        self._refresh()
        self.store_changed.emit()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        entries = self._store.entries()
        self._table.setRowCount(len(entries))
        for r, entry in enumerate(entries):
            self._table.setItem(r, _COL_LABEL, QTableWidgetItem(entry.label))
            hint_item = QTableWidgetItem(entry.hint)
            hint_item.setForeground(Qt.GlobalColor.gray)
            self._table.setItem(r, _COL_HINT, hint_item)
