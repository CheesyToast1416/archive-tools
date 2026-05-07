from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from archivetools.config.passwords import get_password_store
from archivetools.config.settings import get_settings
from archivetools.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ArchiveTools")
    app.setApplicationDisplayName("ArchiveTools")
    app.setStyle("Fusion")

    settings = get_settings()
    store = get_password_store()

    from archivetools.gui.theme import apply_theme

    colors = apply_theme(app, settings.theme)

    window = MainWindow(settings, store, colors=colors)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
