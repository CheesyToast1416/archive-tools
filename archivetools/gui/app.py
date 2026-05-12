from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from archivetools.config.passwords import get_password_store
from archivetools.config.settings import get_settings
from archivetools.gui.main_window import MainWindow
from archivetools.gui.ui_state import get_ui_state


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ArchiveTools")
    app.setApplicationDisplayName("ArchiveTools")
    app.setStyle("Fusion")

    settings = get_settings()
    ui_state = get_ui_state()
    store = get_password_store()

    from archivetools.gui.theme import apply_theme

    colors = apply_theme(app, ui_state.theme)

    window = MainWindow(settings, store, ui_state=ui_state, colors=colors)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
