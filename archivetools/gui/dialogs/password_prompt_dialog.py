from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from archivetools.config.passwords import PasswordStore, get_or_create_store
from archivetools.gui.widgets.password_picker_btn import PasswordPickerButton


class PasswordPromptDialog(QDialog):
    """Modal password-entry dialog with eye-toggle and password-picker button."""

    def __init__(
        self,
        message: str,
        store: PasswordStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Password Required")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setMinimumWidth(380)
        layout.addWidget(msg_lbl)

        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(4)

        self._pwd_edit = QLineEdit()
        self._pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_edit.setPlaceholderText("Archive password")

        eye = QToolButton()
        eye.setCheckable(True)
        eye.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton))
        eye.setToolTip("Show / hide")

        def _toggle_eye(on: bool) -> None:
            self._pwd_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
            eye.setIcon(
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_DialogYesButton
                    if on
                    else QStyle.StandardPixmap.SP_DialogNoButton
                )
            )

        eye.toggled.connect(_toggle_eye)

        picker = PasswordPickerButton(get_or_create_store(store))
        picker.password_selected.connect(self._pwd_edit.setText)

        pwd_row.addWidget(self._pwd_edit)
        pwd_row.addWidget(eye)
        pwd_row.addWidget(picker)
        layout.addLayout(pwd_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._pwd_edit.returnPressed.connect(self.accept)
        self._pwd_edit.setFocus()
        self.adjustSize()

    def password(self) -> str:
        """Return the entered password. Call after ``exec()`` returns Accepted."""
        return self._pwd_edit.text()
