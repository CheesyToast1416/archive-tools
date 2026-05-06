from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QThread, Signal

from archivetools.core import extract_cjk, list_cjk
from archivetools.gui.log_handler import GuiLogHandler

_CORE_LOGGER = "archivetools.core"


class _BaseWorker(QThread):
    error = Signal(str)
    log_message = Signal(str)

    def _install_log_handler(self) -> GuiLogHandler:
        handler = GuiLogHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        handler.message.connect(self.log_message)
        logging.getLogger(_CORE_LOGGER).addHandler(handler)
        return handler

    def _remove_log_handler(self, handler: GuiLogHandler) -> None:
        logging.getLogger(_CORE_LOGGER).removeHandler(handler)


class ListWorker(_BaseWorker):
    """Calls list_cjk() in a background thread and emits results via signals."""

    # Named 'result' (not 'finished') so QThread's built-in finished signal remains
    # accessible for lifecycle management (deleteLater, etc.).
    result = Signal(bool, str, list)

    def __init__(
        self,
        archive_path: str,
        password: str,
        filename_encoding: Optional[str],
        password_encoding: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._password = password
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok, enc, names = list_cjk(
                self._archive_path, self._password,
                self._filename_encoding, self._password_encoding,
            )
            self.result.emit(ok, enc or "", names)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


class ExtractionWorker(_BaseWorker):
    """Calls extract_cjk() in a background thread and emits results via signals."""

    result = Signal(bool, str)

    def __init__(
        self,
        archive_path: str,
        password: str,
        output_dir: str,
        filename_encoding: Optional[str],
        password_encoding: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._password = password
        self._output_dir = output_dir or None
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok, enc = extract_cjk(
                self._archive_path,
                self._password,
                self._output_dir,
                filename_encoding=self._filename_encoding,
                password_encoding=self._password_encoding,
            )
            self.result.emit(ok, enc or "")
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)
