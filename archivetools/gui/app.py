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

    window = MainWindow(settings, store)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
