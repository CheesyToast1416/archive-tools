from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QToolButton, QWidget

from archivetools.config.passwords import PasswordStore


class PasswordPickerButton(QToolButton):
    """
    A small ``🔑 Saved`` button that pops a menu of named passwords.
    Emits ``password_selected(str)`` when the user picks one.
    Connect it to the adjacent password QLineEdit's ``setText`` slot.
    """

    password_selected = Signal(str)

    def __init__(self, store: PasswordStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self.setText("🔑 Saved")
        self.setToolTip("Insert a saved password")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._store.on_change(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the dropdown menu from the current store contents."""
        menu = QMenu(self)
        entries = self._store.entries()
        if not entries:
            act = menu.addAction("(no saved passwords)")
            act.setEnabled(False)
        else:
            for entry in entries:
                label = entry.label
                if entry.hint:
                    label += f"   [{entry.hint}]"
                act = menu.addAction(label)
                act.setData(entry.id)
                # Capture entry_id in default arg to avoid late-binding closure
                act.triggered.connect(
                    lambda checked=False, eid=entry.id: self._on_selected(eid)
                )
        menu.addSeparator()
        manage = menu.addAction("Manage passwords…")
        manage.triggered.connect(self._open_manager)
        self.setMenu(menu)

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_selected(self, entry_id: str) -> None:
        try:
            pwd = self._store.get_password(entry_id)
            self.password_selected.emit(pwd)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).warning("Could not retrieve password: %s", exc)

    def _open_manager(self) -> None:
        w = self.window()
        if hasattr(w, "switch_to_passwords_tab"):
            w.switch_to_passwords_tab()
